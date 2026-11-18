"""First native-feature checkpoint is always a new full base, never a seed delta.

Native cache save/restore is external to this tool. Publication is deliberately
separate from capture and requires exact archive readback. No normal head is
modified here; a future fresh-worker validator may promote the returned receipt.
"""
import hashlib,json,os,shutil,sys,time
from pathlib import Path
import ci_full as c
from ci_compile import fingerprint,file_sha
from raw import lock,verify
from final_archive_proof import verify_archived_apk
ROOT=c.ROOT
STATE=ROOT/'.feature-seed-checkpoint'

def admission():
    value=c.D.c.read(ROOT/'.baseline-seed/admission.json')
    from baseline_seed import RECEIPT,BASELINE_FINGERPRINT
    if (value.get('status')!='feature-inputs-ready'
            or value.get('baseline_receipt')!=RECEIPT
            or value.get('baseline_fingerprint')!=BASELINE_FINGERPRINT
            or value.get('feature_fingerprint')!=fingerprint()
            or value.get('apk_verified') is not False
            or value.get('checkpoint_accepted') is not False):
        raise ValueError('Exact inputs-ready seed admission required')
    from native_features import load_manifest
    if not load_manifest(ROOT):raise ValueError('Feature checkpoint requires explicit enabled recipe')
    verify(ROOT/'work/source/src',lock())
    return value

def budget(minimum=300, reserve=120):
    started=c.D.c.read(c.D.STATE/'job-start.json')['epoch']
    remaining=int(3300-(time.time()-started))
    if remaining<minimum:raise ValueError('Insufficient safe full checkpoint budget')
    c.D.operation_budget=min(1500,remaining-reserve)
    return c.D.operation_budget

def capture():
    admission();c.D.gate();budget(minimum=1620, reserve=840)
    if c.D.HEAD.exists() or (c.D.STATE/'selected.json').exists():
        raise ValueError('First feature base cannot inherit an accepted/selected head')
    value=c.D.c.read(ROOT/'handoff/stage1/state.json')
    if value.get('fingerprint')!=fingerprint() or value.get('status') not in ('prepared','done','slice_expired'):
        raise ValueError('Only verified prepared input or compile completion/timeslice may be checkpointed')
    if value['status']=='prepared':
        proof=c.D.c.read(ROOT/'artifacts/feature-seed/verify-proof.json')
        if proof.get('phase')!='verify' or proof.get('fingerprint')!=fingerprint():
            raise ValueError('Prepared snapshot requires actual feature verification proof')
    done=value['status']=='done'
    if done:
        if not all(value.get(x) is True for x in ('apk_verified','apk_signature_verified','apk_zip_verified')):
            raise ValueError('Incomplete APK verification')
        if file_sha(ROOT/'work/source/src/out/RawSandium/apks/ChromePublic.apk')!=value.get('apk_sha256'):
            raise ValueError('Produced APK identity mismatch')
    meta=ROOT/'work/source/.sandium';meta.mkdir(exist_ok=True)
    (meta/'checkpoint-manifest.txt').write_text('PRODUCT=RawS\nCOMPATIBILITY='+c.D.c.COMPAT+'\n')
    c.f.cli.run_bounded([sys.executable,'-u',str(c.D.LEGACY),'archive','--root',str(ROOT),'--workers','8'],budget(minimum=1620, reserve=840)-10)
    budget(minimum=900, reserve=840)  # Recalculate after archive, never reuse its old allowance.
    c.D.seed_capture()  # New feature scope; explicit seed flag is required, no fake fresh marker.
    candidate=c.D.c.read(c.D.STATE/'candidate.json')
    if candidate['payload']['plan']['layers']:raise ValueError('First feature checkpoint must be full')
    candidate['payload'].update(apk_verified=done,apk_sha256=value.get('apk_sha256') if done else None,
                                provenance='new full native-feature base after exact baseline transition')
    candidate['id']=c.bridge.digest(c.bridge.encode(candidate['payload']))
    STATE.mkdir(exist_ok=True)
    c.D.c.save(STATE/'candidate.json',candidate)
    (STATE/'base.key').write_text(candidate['payload']['plan']['base']['key'])

def clear_for_readback():
    candidate=c.D.c.read(STATE/'candidate.json');c.D.valid(candidate)
    c.D.c.save(STATE/'required.json',{'candidate':candidate['id']})
    for path in (ROOT/c.D.MANIFEST,ROOT/c.D.SHARDS):
        if path.is_symlink():raise ValueError('Symlink archive input')
        if path.is_dir():shutil.rmtree(path)
        else:path.unlink(missing_ok=True)

def accept_readback():
    candidate=c.D.c.read(STATE/'candidate.json');payload=c.D.valid(candidate)
    if c.D.c.read(STATE/'required.json')!={'candidate':candidate['id']}:
        raise ValueError('Missing exact remote readback requirement')
    raw=(ROOT/c.D.MANIFEST).read_bytes();base=payload['plan']['base']
    if payload['plan']['layers'] or c.bridge.base_id(raw)!=base['id'] or hashlib.sha256(raw).hexdigest()!=base['manifest_sha256']:
        raise ValueError('Wrong restored full feature archive')
    c.f.cli.run_bounded([sys.executable,'-u',str(c.D.LEGACY),'verify','--root',str(ROOT)],budget()-10)
    if payload['apk_verified']:
        proof=verify_archived_apk(json.loads(raw),ROOT/c.D.SHARDS,payload['apk_sha256'],budget()-10)
        c.D.c.save(STATE/'archived-apk-proof.json',proof)
    c.D.c.save(STATE/'readback-proof.json',{'candidate':candidate['id']})
    c.D.c.save(STATE/'receipt.json',candidate)
    # Not a normal head or completion marker. Fresh-worker validation is still mandatory.
