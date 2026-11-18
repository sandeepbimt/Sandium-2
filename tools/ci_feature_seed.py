#!/usr/bin/env python3
"""Explicit feature-seed job phases; no cache network operations or CI triggers."""
import argparse,json,os,time
from pathlib import Path
from raw import ROOT
from ci_compile import fingerprint
from native_features import load_manifest
from baseline_seed import transition
from feature_seed_callbacks import SeedCallbacks

BRANCH='raw-sandium/native-ui158'
def gate():
    if (os.environ.get('CIRCLE_BRANCH')!=BRANCH
            or os.environ.get('RAWS_NATIVE_FEATURE_SEED')!='true'
            or os.environ.get('RAWS_STAGE')!='1'
            or os.environ.get('CIRCLE_PROJECT_REPONAME')!='Sandium-2'
            or not load_manifest(ROOT)):
        raise ValueError('Explicit native-feature seed job required')

def original_epoch():
    value=float(os.environ['RAWS_FEATURE_JOB_STARTED_EPOCH'])
    if not 0 <= time.time()-value < 3300:raise ValueError('Invalid/expired original feature job clock')
    return value

def prepare_transition(baseline_checkout):
    gate();started=original_epoch()
    callbacks=SeedCallbacks(ROOT,baseline_checkout)
    result=transition(ROOT,fingerprint(),**callbacks.callbacks())
    state=ROOT/'.checkpoint-state'
    if state.exists():raise ValueError('Old checkpoint metadata survived transition')
    state.mkdir()
    (state/'job-start.json').write_text(json.dumps({'epoch':started})+'\n')
    # No fresh flag, selected old receipt, restored proof, head or completion flag.
    handoff=ROOT/'handoff/stage1';handoff.mkdir(parents=True)
    (handoff/'state.json').write_text(json.dumps({'status':'prepared','fingerprint':fingerprint(),
        'apk_produced':False,'apk_verified':False,'compilation_attempted':False})+'\n')
    return result

def exact_prepared(receipt):
    import ci_full as c
    payload=c.D.valid(receipt)
    if (payload.get('apk_verified') is not False
            or payload.get('source')!=os.environ.get('CIRCLE_SHA1')
            or payload.get('workflow')!=os.environ.get('CIRCLE_WORKFLOW_ID')
            or payload.get('pipeline')!=int(os.environ['RAWS_PIPELINE_NUMBER'])
            or payload.get('stage')!=1 or payload['plan']['layers']):
        raise ValueError('Exact same-workflow prepared full feature receipt required')
    return payload

def exact_resume(receipt):
    import re
    import ci_full as c
    expected=os.environ.get('RAWS_NATIVE_RESUME_RECEIPT_ID','')
    key=os.environ.get('RAWS_NATIVE_RESUME_CACHE_KEY','')
    if not re.fullmatch('[0-9a-f]{64}',expected) or not key.startswith('raws-native-progress-v1-') or any(x.isspace() for x in key):
        raise ValueError('Explicit exact resume identity/key required')
    payload=c.D.valid(receipt)
    if (receipt['id']!=expected or payload.get('source')!=os.environ['CIRCLE_SHA1']
            or payload.get('stage') not in (1,2,3,4,5)
            or payload.get('apk_verified') is not False):
        raise ValueError('Wrong same-recipe resume receipt')
    return payload

def preserve_clock():
    import ci_full as c
    value={'epoch':original_epoch()}
    c.D.STATE.mkdir(exist_ok=True)
    path=c.D.STATE/'job-start.json'
    if path.exists():
        if c.D.c.read(path)!=value:raise ValueError('Fresh validator clock was reset')
    else:c.D.c.save(path,value)

def select_prepared():
    import ci_full as c
    received=ROOT/'.feature-seed-checkpoint'
    receipt=c.D.c.read(received/'receipt.json');exact_prepared(receipt)
    if c.D.c.read(received/'readback-proof.json')!={'candidate':receipt['id']}:
        raise ValueError('Missing exact prepared archive readback')
    if c.D.HEAD.exists():raise ValueError('Prepared validation must not inherit a normal head')
    preserve_clock()
    previous=c.D.HEAD
    try:
        c.D.HEAD=received/'receipt.json';c.D.select(precheck=True)
    finally:c.D.HEAD=previous

def select_resume():
    import ci_full as c
    path=ROOT/'.raws-final-progress/receipt.json'
    receipt=c.D.c.read(path);exact_resume(receipt)
    if c.D.HEAD.exists():raise ValueError('Resume validation must not inherit a normal head')
    preserve_clock();previous=c.D.HEAD
    try:
        c.D.HEAD=path;c.D.select(precheck=True)
    finally:c.D.HEAD=previous

def _verify_prepared_owned(resume=False):
    import ci_full as c
    from raw import lock,verify
    from ci_official import verify_official
    from ci_remote import verify_graph_outputs
    from native_features import verify_applied
    import subprocess
    c.D.verify_restored()
    receipt=c.D.c.read(c.D.STATE/'selected.json');payload=exact_resume(receipt) if resume else exact_prepared(receipt)
    if not resume and (payload.get('apk_verified') is not False or payload['plan']['layers']):
        raise ValueError('Prepared validator cannot accept a completed/partial-chain seed')
    src=ROOT/'work/source/src';depot=ROOT/'work/source/depot_tools';out=src/'out/RawSandium'
    data=lock();verify(src,data)
    if subprocess.check_output(['git','-C',str(depot),'rev-parse','HEAD'],text=True).strip()!=data['depot_tools']['revision']:
        raise ValueError('Wrong restored depot_tools pin')
    if subprocess.check_output(['git','-C',str(depot),'diff','HEAD','--name-only'],text=True).strip():
        raise ValueError('Modified restored depot_tools')
    if (out/'args.gn').read_bytes()!=(ROOT/'ci/args.gn').read_bytes():raise ValueError('Wrong feature GN arguments')
    apk=out/'apks/ChromePublic.apk'
    if not resume and apk.exists():raise ValueError('Prepared feature archive retained old APK')
    if resume and payload['apk_verified']:
        from ci_compile import file_sha
        if not apk.is_file() or file_sha(apk)!=payload.get('apk_sha256'):raise ValueError('Resumed APK bytes differ from receipt')
    artifacts=ROOT/'artifacts/feature-seed-fresh';artifacts.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,PATH=str(depot)+os.pathsep+os.environ.get('PATH',''),DEPOT_TOOLS_UPDATE='0')
    official=verify_official(src,depot,out,env,artifacts,'fresh-feature')
    verify_graph_outputs(src,depot,out,env,artifacts,'fresh-feature')
    c.D.c.save(ROOT/'.feature-seed-validation.json',{'receipt':receipt['id'],
        'scope':payload['scope'],'workflow':os.environ['CIRCLE_WORKFLOW_ID'],
        'job':os.environ['CIRCLE_BUILD_NUM'],'feature_hashes':verify_applied(src,ROOT).hashes,
        'official':official,'apk_verified':False,'resume':resume})

def verify_prepared(resume=False):
    import sys
    from feature_seed_callbacks import run_owned
    started=original_epoch()
    remaining=3300-(time.time()-started)-120
    if remaining<120:raise ValueError('Insufficient fresh verification deadline')
    command=[sys.executable,'-I','-c',
        "import sys;sys.path.insert(0,sys.argv[1]);import ci_feature_seed as m;m.gate();m._verify_prepared_owned(sys.argv[2]=='resume')",
        str(ROOT/'tools'),'resume' if resume else 'prepared']
    completed=run_owned(command,env=dict(os.environ),cwd=ROOT,timeout=min(600,remaining))
    artifacts=ROOT/'artifacts/feature-seed-fresh';artifacts.mkdir(parents=True,exist_ok=True)
    (artifacts/'validation-stdout.log').write_text(completed.stdout)
    (artifacts/'validation-stderr.log').write_text(completed.stderr)

def promote_prepared(resume=False):
    import ci_full as c
    c.D.verify_restored()
    receipt=c.D.c.read(c.D.STATE/'selected.json');payload=exact_resume(receipt) if resume else exact_prepared(receipt)
    proof=c.D.c.read(ROOT/'.feature-seed-validation.json')
    if (proof.get('receipt')!=receipt['id'] or proof.get('scope')!=payload['scope']
            or proof.get('workflow')!=os.environ['CIRCLE_WORKFLOW_ID']
            or proof.get('job')!=os.environ['CIRCLE_BUILD_NUM'] or proof.get('apk_verified') is not False
            or proof.get('resume',False)!=resume):
        raise ValueError('Missing fresh-worker feature verification')
    if c.D.HEAD.exists():raise ValueError('Feature bootstrap cannot replace an accepted head')
    c.D.c.save(c.D.HEAD,receipt)  # New scope only, after exact restore and source/GN validation.

def completed_handoff():
    from raw import require_build_scope
    import ci_final_archive as final
    import subprocess
    require_build_scope()
    value=final.state()
    if value.get('status')=='slice_expired':
        # Verified partial progress was saved/read back before this phase.
        receipt=final.c.D.c.read(final.PROGRESS/'receipt.json');payload=final.c.D.valid(receipt)
        if (payload.get('source')!=os.environ['CIRCLE_SHA1']
                or payload.get('workflow')!=os.environ['CIRCLE_WORKFLOW_ID']
                or payload.get('pipeline')!=int(os.environ['RAWS_PIPELINE_NUMBER'])
                or payload.get('stage')!=int(os.environ['RAWS_STAGE'])
                or payload.get('apk_verified') is not False):
            raise ValueError('Unverified partial feature progress')
        subprocess.run(['circleci-agent','step','halt'],check=True)
        return
    final.require_done()
    receipt=final.c.D.c.read(final.PROGRESS/'receipt.json');payload=final.c.D.valid(receipt)
    if (payload.get('source')!=os.environ['CIRCLE_SHA1']
            or payload.get('workflow')!=os.environ['CIRCLE_WORKFLOW_ID']
            or payload.get('pipeline')!=int(os.environ['RAWS_PIPELINE_NUMBER'])
            or payload.get('stage')!=int(os.environ['RAWS_STAGE'])
            or payload.get('apk_verified') is not True
            or payload.get('apk_sha256')!=value.get('apk_sha256')):
        raise ValueError('Exact completed feature progress required')
    if final.c.D.c.read(final.c.D.STATE/'readback-proof.json')!={'candidate':receipt['id']}:
        raise ValueError('Completed handoff lacks exact progress readback')

def run(phase,baseline_checkout=None):
    if phase=='completed-handoff':return completed_handoff()
    gate();original_epoch()
    if phase=='transition':return prepare_transition(baseline_checkout)
    if phase in ('select-resume','verify-resume','promote-resume'):
        return {'select-resume':select_resume,'verify-resume':lambda:verify_prepared(True),
                'promote-resume':lambda:promote_prepared(True)}[phase]()
    if phase in ('select-prepared','verify-prepared','promote-prepared'):
        return {'select-prepared':select_prepared,'verify-prepared':verify_prepared,
                'promote-prepared':promote_prepared}[phase]()
    import feature_seed_checkpoint as checkpoint
    {'capture':checkpoint.capture,'clear-readback':checkpoint.clear_for_readback,
     'accept-readback':checkpoint.accept_readback}[phase]()

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('phase',choices=('transition','capture','clear-readback','accept-readback','select-prepared','verify-prepared','promote-prepared','completed-handoff','select-resume','verify-resume','promote-resume'))
    parser.add_argument('--baseline-checkout',type=Path)
    args=parser.parse_args()
    if args.phase=='transition' and args.baseline_checkout is None:parser.error('baseline checkout required')
    run(args.phase,args.baseline_checkout)
