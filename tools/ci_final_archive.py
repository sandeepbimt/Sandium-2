#!/usr/bin/env python3
"""Two-job one-off snapshot: isolated progress, then full completed-tree archive.

Does not alter the normal Full head. Native cache transport is performed by CI;
publication requires exact payload readback, not merely a successful save step.
"""
import json,os,shutil,sys,time
from pathlib import Path
import ci_full as c
from ci_compile import file_sha,fingerprint
from final_archive_proof import verify_archived_apk
ROOT=c.ROOT
FINAL=ROOT/'.raws-final-archive'
PROGRESS=ROOT/'.raws-final-progress'

def prepare(archive=False):
    continuation=PROGRESS/'receipt.json'
    if continuation.exists():
        payload=c.D.valid(c.D.c.read(continuation))
        if archive and not (payload.get('apk_verified') is True and payload.get('workflow')==os.environ['CIRCLE_WORKFLOW_ID'] and payload.get('source')==os.environ['CIRCLE_SHA1'] and payload.get('pipeline')==int(os.environ['RAWS_PIPELINE_NUMBER'])):
            raise ValueError('Archive requires exact same-workflow completed continuation')
        old=c.D.HEAD
        try:
            c.D.HEAD=continuation;c.D.select(precheck=True)
        finally:c.D.HEAD=old
    elif archive:raise ValueError('Missing exact completed continuation')
    elif c.D.HEAD.exists():c.D.select(precheck=True)
    else:c.prepare()

def prepare_probe():
    """Select only this workflow's remotely verified complete base, never layers."""
    receipt=FINAL/'receipt.json'
    if not receipt.is_file():raise ValueError('Missing exact final archive receipt')
    payload=c.D.valid(c.D.c.read(receipt))
    if not (payload.get('apk_verified') is True and payload.get('workflow')==os.environ['CIRCLE_WORKFLOW_ID'] and payload.get('source')==os.environ['CIRCLE_SHA1'] and payload.get('pipeline')==int(os.environ['RAWS_PIPELINE_NUMBER']) and payload['plan']['layers']==[] and payload['plan']['head']==payload['plan']['base']['id']):
        raise ValueError('Probe requires same-workflow completed full base without deltas')
    proof=c.D.c.read(FINAL/'archived-apk-proof.json')
    if proof.get('sha256')!=payload.get('apk_sha256') or not proof.get('bytes',0):raise ValueError('Missing archived APK proof')
    old=c.D.HEAD
    try:
        c.D.HEAD=receipt;c.D.select(precheck=True)
    finally:c.D.HEAD=old


def state():
    stage=int(os.environ.get('RAWS_STAGE','1'))
    if stage not in (1,2,3,4,5):raise ValueError('Invalid final progress stage')
    path=ROOT/'work/source/.sandium/final-build-state.json' if os.environ.get('RAWS_FINAL_PACK_ONLY')=='true' else ROOT/f'handoff/stage{stage}/state.json'
    value=c.D.c.read(path)
    if value.get('fingerprint')!=fingerprint():raise ValueError('Wrong progress fingerprint')
    return value

def require_done():
    if os.environ.get('RAWS_FINAL_ARCHIVE')!='true':raise ValueError('Explicit final archive opt-in required')
    value=state()
    if value.get('status')!='done':raise ValueError('Whole target must finish successfully before full archive')
    if not all(value.get(k) is True for k in ('apk_verified','apk_signature_verified','apk_zip_verified')):raise ValueError('APK checks incomplete')
    apk=ROOT/'work/source/src/out/RawSandium/apks/ChromePublic.apk'
    if file_sha(apk)!=value.get('apk_sha256'):raise ValueError('Final APK digest mismatch')
    return value

def progress_capture():
    value=state()
    if value.get('status') not in ('done','slice_expired'):raise ValueError('Failed compile is not resumable progress')
    if value['status']=='done':require_done()
    selected=c.D.c.read(c.D.STATE/'selected.json');c.D.valid(selected)
    # begin inventory was captured before compile. Persist proof inside captured tree.
    c.D.c.save(ROOT/'work/source/.sandium/final-build-state.json',value)
    c.f.capture()
    candidate=c.D.c.read(c.D.STATE/'candidate.json')
    candidate['payload'].update(apk_verified=value['status']=='done',provenance='isolated one-off compile progress',apk_sha256=value.get('apk_sha256'))
    candidate['id']=c.bridge.digest(c.bridge.encode(candidate['payload']))
    c.D.c.save(c.D.STATE/'candidate.json',candidate)
    FINAL.mkdir(exist_ok=True);c.D.c.save(FINAL/'progress-candidate.json',candidate)

def progress_publish():
    c.readback()
    candidate=c.D.c.read(c.D.STATE/'candidate.json');c.D.valid(candidate)
    if c.D.c.read(c.D.STATE/'readback-proof.json')!={'candidate':candidate['id']}:raise ValueError('Missing independent progress readback proof')
    c.D.c.save(PROGRESS/'receipt.json',candidate)
    print('RAWS_FINAL_PROGRESS_REMOTE_READBACK_VERIFIED',candidate['id'],flush=True)

def progress_final():
    if state().get('status')=='slice_expired':raise ValueError('Incomplete full archive: verified incremental progress retained independently; resume one-off job')
    require_done()

def capture():
    c.D.verify_restored()
    value=require_done()
    selected=c.D.c.read(c.D.STATE/'selected.json');payload=c.D.valid(selected)
    if payload.get('apk_sha256')!=value['apk_sha256'] or payload.get('apk_verified') is not True:raise ValueError('Restored APK proof not bound to selected completed receipt')
    c.f.cli.quiesce(c.D.LEGACY,ROOT/'work/source')
    c.f.cli.run_bounded([sys.executable,'-u',str(c.D.LEGACY),'archive','--root',str(ROOT),'--workers','8'],c.D.operation_budget-10)
    c.f.cli.run_bounded([sys.executable,'-u',str(c.D.LEGACY),'verify','--root',str(ROOT)],c.D.operation_budget-10)
    raw=(ROOT/c.D.MANIFEST).read_bytes();manifest=json.loads(raw)
    if len(manifest['shards'])!=8:raise ValueError('Expected complete eight-shard archive')
    ident=c.bridge.base_id(raw)
    base=dict(id=ident,manifest_sha256=c.bridge.digest(raw),key=c.D.new_key('final-base',ident),expires_at=int(time.time())+14*86400,archive_bytes=sum(x['size_bytes'] for x in manifest['shards']))
    payload=dict(kind=c.D.KIND,scope=c.D.c.scope(),compatibility=c.D.c.COMPAT,source=os.environ['CIRCLE_SHA1'],pipeline=int(os.environ['RAWS_PIPELINE_NUMBER']),workflow=os.environ['CIRCLE_WORKFLOW_ID'],stage=1,plan=dict(base=base,head=ident,layers=[]),apk_verified=True,apk_sha256=value['apk_sha256'],previous_receipt=selected['id'],provenance='completed follow-up workspace; not exact prior-job filesystem')
    FINAL.mkdir(exist_ok=True)
    c.D.c.save(FINAL/'candidate.json',dict(id=c.bridge.digest(c.bridge.encode(payload)),payload=payload))
    (FINAL/'base.key').write_text(base['key'])

def clear():
    candidate=c.D.c.read(FINAL/'candidate.json');c.D.valid(candidate)
    c.D.c.save(FINAL/'readback-required.json',{'candidate':candidate['id']})
    for path in (ROOT/c.D.MANIFEST,ROOT/c.D.SHARDS):
        if path.is_symlink() or path.is_file():path.unlink()
        elif path.is_dir():shutil.rmtree(path)

def verify_publish():
    candidate=c.D.c.read(FINAL/'candidate.json');payload=c.D.valid(candidate)
    if c.D.c.read(FINAL/'readback-required.json')!={'candidate':candidate['id']}:raise ValueError('Missing exact remote readback requirement')
    raw=(ROOT/c.D.MANIFEST).read_bytes()
    if c.bridge.base_id(raw)!=payload['plan']['base']['id'] or c.bridge.digest(raw)!=payload['plan']['base']['manifest_sha256']:raise ValueError('Remote full archive manifest mismatch')
    c.f.cli.run_bounded([sys.executable,'-u',str(c.D.LEGACY),'verify','--root',str(ROOT)],c.D.operation_budget-10)
    proof=verify_archived_apk(json.loads(raw),ROOT/c.D.SHARDS,payload['apk_sha256'],c.D.operation_budget-10)
    c.D.c.save(FINAL/'archived-apk-proof.json',proof)
    c.D.c.save(FINAL/'receipt.json',candidate)
    print('RAWS_FINAL_ARCHIVE_REMOTE_READBACK_VERIFIED',candidate['id'],flush=True)

def run(phase):
    c.gate()
    if os.environ.get('RAWS_FINAL_ARCHIVE')!='true':raise ValueError('Not a final archive job')
    remaining=3300-(time.time()-c.D.c.read(c.D.STATE/'job-start.json')['epoch'])
    c.D.operation_budget=min(1200,remaining-120)
    if c.D.operation_budget<60:raise ValueError('Insufficient final archive budget; accepted head untouched')
    actions={'prepare':prepare,'prepare-archive':lambda:prepare(True),'prepare-probe':prepare_probe,'progress-capture':progress_capture,'progress-clear':c.clear_readback,'progress-publish':progress_publish,'progress-final':progress_final,'capture':capture,'clear':clear,'verify-publish':verify_publish}
    with c.D.Watchdog(c.D.operation_budget,stall_seconds=c.D.operation_budget):actions[phase]()
if __name__=='__main__':run(sys.argv[1])
