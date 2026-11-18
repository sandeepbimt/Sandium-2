#!/usr/bin/env python3
"""Explicit same-recipe completed-progress recovery, without rewriting provenance.

Only a new full snapshot is published by the unchanged final archive helper.
The old progress receipt remains immutable, and never becomes a completion halt.
"""
import os,re,sys,time,subprocess
from pathlib import Path
import ci_full as c
import ci_feature_seed as seed
from ci_compile import fingerprint,verify_apk
ROOT=c.ROOT
PROOF=ROOT/'.feature-completed-resume/authorization.json'
RECEIPT=ROOT/'.raws-final-progress/receipt.json'

def exact(receipt):
    expected=os.environ.get('RAWS_NATIVE_RESUME_RECEIPT_ID','')
    key=os.environ.get('RAWS_NATIVE_RESUME_CACHE_KEY','')
    if not re.fullmatch('[0-9a-f]{64}',expected) or not re.fullmatch('raws-native-progress-v1-[A-Za-z0-9_-]+',key):
        raise ValueError('Exact completed progress selector required')
    p=c.D.valid(receipt)
    if (receipt['id']!=expected or p.get('source')!=os.environ['CIRCLE_SHA1']
            or p.get('scope')!=c.D.c.scope() or p.get('apk_verified') is not True
            or p.get('stage') not in (1,2,3,4,5)
            or not isinstance(p.get('pipeline'),int) or p['pipeline']>int(os.environ['RAWS_PIPELINE_NUMBER'])
            or not re.fullmatch('[0-9a-f]{64}',p.get('apk_sha256',''))):
        raise ValueError('Wrong completed same-recipe receipt')
    return p

def binding(receipt):
    p=exact(receipt)
    return dict(receipt=receipt['id'],scope=p['scope'],source=os.environ['CIRCLE_SHA1'],
                workflow=os.environ['CIRCLE_WORKFLOW_ID'],pipeline=int(os.environ['RAWS_PIPELINE_NUMBER']),
                fingerprint=fingerprint(),apk_sha256=p['apk_sha256'])

def select():
    exact(c.D.c.read(RECEIPT))
    if c.D.HEAD.exists():raise ValueError('Recovery cannot inherit a normal head')
    seed.preserve_clock();old=c.D.HEAD
    try:
        c.D.HEAD=RECEIPT;c.D.select(precheck=True)
    finally:c.D.HEAD=old

def verify_owned(pack=False):
    from raw import lock,verify
    from native_features import verify_applied
    from ci_official import verify_official
    from ci_remote import verify_graph_outputs
    import ci_final_archive as final
    c.D.verify_restored()
    receipt=c.D.c.read(c.D.STATE/'selected.json');p=exact(receipt)
    if receipt!=c.D.c.read(RECEIPT):raise ValueError('Selected recovery receipt mismatch')
    src=ROOT/'work/source/src';depot=ROOT/'work/source/depot_tools';out=src/'out/RawSandium'
    data=lock();verify(src,data)
    if subprocess.check_output(['git','-C',str(depot),'rev-parse','HEAD'],text=True).strip()!=data['depot_tools']['revision']:
        raise ValueError('Wrong recovery depot_tools pin')
    if subprocess.check_output(['git','-C',str(depot),'diff','HEAD','--name-only'],text=True).strip():
        raise ValueError('Modified recovery depot_tools')
    if (out/'args.gn').read_bytes()!=(ROOT/'ci/args.gn').read_bytes():raise ValueError('Wrong recovery GN arguments')
    env=dict(os.environ,PATH=str(depot)+os.pathsep+os.environ.get('PATH',''),DEPOT_TOOLS_UPDATE='0')
    artifacts=ROOT/'artifacts/completed-feature-recovery';artifacts.mkdir(parents=True,exist_ok=True)
    official=verify_official(src,depot,out,env,artifacts,'recovery')
    verify_graph_outputs(src,depot,out,env,artifacts,'recovery')
    apk=verify_apk(out/'apks/ChromePublic.apk',src,env)
    if apk['apk_sha256']!=p['apk_sha256']:raise ValueError('Recovered APK differs from immutable receipt')
    # Existing build state was captured inside the verified chain, not fabricated.
    value=final.require_done()
    if value['apk_sha256']!=apk['apk_sha256']:raise ValueError('Recovered completed state differs')
    proof=dict(binding(receipt),job=os.environ['CIRCLE_BUILD_NUM'],apk_verified=True,
               feature_hashes=verify_applied(src,ROOT).hashes,official=official,apk=apk)
    c.D.c.save(ROOT/('.feature-completed-pack.json' if pack else '.feature-completed-verified.json'),proof)

def verify(pack=False):
    from feature_seed_callbacks import run_owned
    remaining=3300-(time.time()-seed.original_epoch())-120
    if remaining<120:raise ValueError('Insufficient recovery verification deadline')
    command=[sys.executable,'-I','-c',
        "import sys;sys.path.insert(0,sys.argv[1]);import completed_feature_resume as m;m.seed.gate();m.verify_owned(sys.argv[2]=='pack')",str(ROOT/'tools'),'pack' if pack else 'validator']
    result=run_owned(command,env=dict(os.environ),cwd=ROOT,timeout=min(600,remaining))
    artifacts=ROOT/'artifacts/completed-feature-recovery';artifacts.mkdir(parents=True,exist_ok=True)
    (artifacts/('pack.log' if pack else 'validator.log')).write_text(result.stdout+'\n'+result.stderr)

def validate_proof(proof,receipt,same_job):
    expected=binding(receipt)
    if any(proof.get(k)!=v for k,v in expected.items()) or proof.get('apk_verified') is not True:
        raise ValueError('Missing exact current-workflow recovery authorization')
    job=proof.get('job')
    if not isinstance(job,str) or not job or ((job==os.environ['CIRCLE_BUILD_NUM'])!=same_job):
        raise ValueError('Recovery proof must match required fresh-worker boundary')
    if proof.get('apk',{}).get('apk_sha256')!=expected['apk_sha256'] or not all(proof.get('apk',{}).get(k) is True for k in ('apk_verified','apk_signature_verified','apk_zip_verified')):
        raise ValueError('Missing actual signature/ZIP/hash proof')

def authorize():
    c.D.verify_restored();receipt=c.D.c.read(c.D.STATE/'selected.json')
    proof=c.D.c.read(ROOT/'.feature-completed-verified.json');validate_proof(proof,receipt,True)
    if receipt!=c.D.c.read(RECEIPT):raise ValueError('Recovery receipt changed after verification')
    c.D.c.save(PROOF,proof)

def prepare():
    receipt=c.D.c.read(RECEIPT);validate_proof(c.D.c.read(PROOF),receipt,False)
    select()

def run(phase):
    seed.gate();seed.original_epoch();c.gate()
    if os.environ.get('RAWS_FINAL_ARCHIVE')!='true' or os.environ.get('RAWS_FINAL_PACK_ONLY')!='true':
        raise ValueError('Explicit completed archive-only recovery required')
    {'select':select,'verify':verify,'authorize':authorize,'prepare':prepare,'verify-pack':lambda:verify(True)}[phase]()
if __name__=='__main__':run(sys.argv[1])
