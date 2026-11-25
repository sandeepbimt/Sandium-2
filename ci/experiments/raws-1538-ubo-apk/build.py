"""Read-only baseline restore and bounded isolated ARM64 APK compile."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[2]
sys.path[:0] = [str(ROOT/'tools'), str(KIT)]
from ci_compile import fingerprint, file_sha, install_host_and_hooks
from ci_remote import bootstrap_depot, configure, remote_command, run_logged
import ci_restore_only as ro
from ci_prepare_raws_engine import prepare as stage_engine
from prepare import prepare as desktop_prepare, OUTPUT, safe_path
from raw import lock
import slice_state

BASE = 'a274d3f2e250aad22c8ca4309ba75841f9db65dd'
BRANCH = 'experiment/raws-1538-ubo-apk'
JOB = 'raws-1538-ubo-apk'
RECIPE = 'ba0755150c15aba8ed53278aef717dcace3239235e7f6ae352fd74b768d79774'
PATCH = '98711eb0f37e3111af828ca27bd7779946b3794433c7dcca3325c966c6c3d9b8'
WORK = ROOT/'work/source'
ART = ROOT/'artifacts'
HANDOFF = ROOT/'.ubo-slices'
COMPLETED = ROOT/'.ubo-completed'
APK_NAME = 'RawS-1538-uBO-MV2-test.apk'
LAST = 4

def slice_index():
    n=int(os.environ['RAWS_UBO_SLICE'])
    if n not in range(1,LAST+1):
        raise ValueError('Invalid experiment slice')
    return n

def slice_identity(n):
    return dict(schema=3, stage=n, workflow=os.environ['CIRCLE_WORKFLOW_ID'],
                checkout=os.environ['CIRCLE_SHA1'], base=BASE, recipe=RECIPE, patch=PATCH,
                args_fragment=file_sha(KIT/'args.gn.fragment'))


def git(cwd, *args):
    return subprocess.check_output(['git', '-C', str(cwd), *args], text=True).strip()


def gate():
    if (os.environ.get('CIRCLE_BRANCH'), os.environ.get('CIRCLE_JOB'),
        os.environ.get('CIRCLE_PROJECT_REPONAME')) not in (
            (BRANCH, JOB, 'Sandium-2'),
            (BRANCH, f'{JOB}-{slice_index()}', 'Sandium-2')):
        raise ValueError('Wrong project, branch, or job')
    if any(k.startswith('RAWS_') and any(t in k for t in ('KEYSTORE','KEY_PASSWORD','SIGNING'))
           for k in os.environ):
        raise ValueError('Experiment must not receive RawS signing credentials')
    head = git(ROOT,'rev-parse','HEAD')
    parent = '56ac4f20c2dc806285c77568a552f46e5395a2fb'
    if (head != os.environ.get('CIRCLE_SHA1') or git(ROOT,'rev-parse','HEAD^') != parent
            or git(ROOT,'rev-parse','HEAD^^^^^') != BASE):
        raise ValueError('Expected exact #1543 experiment as the candidate parent')
    if fingerprint() != ro.FINGERPRINT or ro.full.fresh():
        raise ValueError('Unexpected baseline fingerprint or fresh seed')
    if ro.active_feature().identity != RECIPE:
        raise ValueError('Corrected #1538 recipe required')
    if file_sha(KIT/'pinned-ubo.patch') != PATCH:
        raise ValueError('Wrong reviewed package-admission patch')
    ro.full.D.gate()


def completed_identity(checkout, args):
    return dict(schema=1, checkout=checkout, base=BASE,
                target='chrome_public_apk', output=OUTPUT.parent.name,
                args_sha256=hashlib.sha256(args).hexdigest())


def verify_completed_seed():
    producer = os.environ.get('RAWS_UBO_COMPLETED_SEED','')
    if (not re.fullmatch(r'[0-9a-f]{40}', producer)
            or producer == os.environ['CIRCLE_SHA1']
            or subprocess.run(['git','-C',str(ROOT),'merge-base','--is-ancestor',
                               producer,os.environ['CIRCLE_SHA1']],check=False).returncode):
        raise ValueError('Completed seed must be an exact ancestor commit')
    return producer


def save_completed():
    n = slice_index()
    proof = slice_state.receipt_at(HANDOFF/f'stage-{n}',slice_identity(n))
    if proof['status'] == 'slice_expired':
        # Its partial output has already been persisted to this workflow.
        subprocess.run(['circleci-agent','step','halt'],check=True)
        return
    if proof['status'] != 'done':
        raise ValueError('Refusing a completed archive without a finished compile')
    apk = ART/APK_NAME
    apk_receipt = ART/'apk-receipt.json'
    if apk_receipt.is_symlink() or not apk_receipt.is_file():
        raise ValueError('Missing verified APK receipt')
    receipt = json.loads(apk_receipt.read_text())
    if (apk.is_symlink() or not apk.is_file() or
            receipt.get('apk_signature_verified') is not True or
            receipt.get('official_release') is not False or
            receipt.get('checkout') != os.environ['CIRCLE_SHA1'] or
            receipt.get('base') != BASE or receipt.get('recipe_sha256') != RECIPE or
            receipt.get('experimental_patch_sha256') != PATCH or
            receipt.get('apk_sha256') != file_sha(apk)):
        raise ValueError('Completed checkpoint APK provenance mismatch')
    out = (WORK/'src'/OUTPUT).parent
    # The verified slice wrote the effective GN-args digest and same output
    # path as the APK. Required before publishing cross-workflow cache.
    if out.as_posix() != proof.get('output_dir'):
        raise ValueError('Completed checkpoint output path mismatch')
    built = out/'apks/ChromePublic.apk'
    if built.is_symlink() or not built.is_file() or file_sha(built) != receipt['apk_sha256']:
        raise ValueError('Compile output diverged from published APK')
    args = (out/'args.gn').read_bytes()
    if hashlib.sha256(args).hexdigest() != proof.get('args_sha256'):
        raise ValueError('Completed checkpoint arguments mismatch')
    if COMPLETED.exists() or COMPLETED.is_symlink():
        # Slice 1 may have restored a previous archive into this location.
        if not os.environ.get('RAWS_UBO_COMPLETED_SEED') or n != 1 or COMPLETED.is_symlink():
            raise ValueError('Unexpected existing completed archive')
        import shutil
        shutil.rmtree(COMPLETED)
    identity = completed_identity(os.environ['CIRCLE_SHA1'], args)
    identity.update(recipe=RECIPE, patch=PATCH, apk_sha256=receipt['apk_sha256'])
    slice_state.save(out,COMPLETED,identity,'compiled_apk',WORK)
    print('RAWS_COMPLETED_CHECKPOINT_ARCHIVED='+os.environ['CIRCLE_SHA1'],flush=True)


def already_done():
    n=slice_index()
    if n == 1:
        return False
    # A preceding job may have halted because an even earlier job built the APK.
    for i in range(n-1,0,-1):
        folder=HANDOFF/f'stage-{i}'
        if (folder/'receipt.json').is_file():
            receipt=slice_state.receipt_at(folder,slice_identity(i))
            if receipt['status']=='done':
                return True
            if i != n-1:
                raise ValueError('Immediate prior slice lost its handoff')
            return False
    raise ValueError('No prior slice receipt')


def select():
    receipt = ro.FINAL/'receipt.json'
    if receipt.is_symlink() or not receipt.is_file() or file_sha(receipt) != ro.RECEIPT_SHA:
        raise ValueError('Exact verified RawS #1396 receipt is unavailable')
    d = ro.full.D
    ro.check_receipt(d.c.read(receipt))
    raw_proof = d.c.read(ro.FINAL/'archived-apk-proof.json')
    if raw_proof.get('sha256') != ro.OLD_APK or not raw_proof.get('bytes', 0):
        raise ValueError('Archived APK receipt missing or not valid')
    d.HEAD = receipt
    d.select(precheck=True)


def check_pins(src, field):
    for name, entry in json.loads((KIT/'pins.json').read_text()).items():
        p=safe_path(src,name)
        actual=file_sha(p) if p.is_file() else None
        if actual != entry[field]:
            raise ValueError(f'uBlock patch {field} mismatch: {name}')


def compile_apk():
    d=ro.full.D
    from ci_restore_probe import validate_restore
    selected=d.c.read(d.STATE/'selected.json')
    ro.check_receipt(selected)
    validate_restore(selected,d.c.read(d.STATE/'restored-proof.json'))
    if file_sha(WORK/'src/out/RawSandium/apks/ChromePublic.apk') != ro.OLD_APK:
        raise ValueError('Wrong baseline APK')
    ready=d.c.read(WORK/'source-ready.json')
    if not ready.get('ready') or ready.get('lock_sha256') != file_sha(ROOT/'upstream.lock.json'):
        raise ValueError('Wrong baseline source receipt')
    src=WORK/'src'
    depot=WORK/'depot_tools'
    ART.mkdir(exist_ok=True)
    feature=ro.active_feature()
    data=lock()
    if git(depot,'rev-parse','HEAD') != data['depot_tools']['revision']:
        raise ValueError('Wrong depot_tools revision')
    stage_engine()
    from restore_only_port1442 import prepare_stage
    prepare_stage(ROOT/'.raws-staged-engine',feature)
    feature.apply(src,data)
    check_pins(src,'before')
    git(src,'apply','--check',str(KIT/'pinned-ubo.patch'))
    args=desktop_prepare(src,(ROOT/'ci/args.gn').read_bytes(),apply=True)
    git(src,'apply','--whitespace=error',str(KIT/'pinned-ubo.patch'))
    check_pins(src,'after')
    feature_pins=json.loads((KIT/'inputs.json').read_text())['paths']
    for name,pins in feature_pins.items():
        if file_sha(safe_path(src,name)) != pins['after']:
            raise ValueError('Wrong Afterbird postimage: '+name)
    if (src/OUTPUT).read_bytes() != args:
        raise ValueError('Unexpected experimental build args')
    env=dict(os.environ, PATH=str(depot)+os.pathsep+os.environ['PATH'], DEPOT_TOOLS_UPDATE='0')
    install_host_and_hooks(1,env,ART)
    env=bootstrap_depot(depot,data['depot_tools']['revision'],env,ART,1)
    env,_=configure(src,depot,env)
    out=(src/OUTPUT).parent
    n=slice_index()
    if n>1:
        previous=HANDOFF/f'stage-{n-1}'
        proof=slice_state.receipt_at(previous,slice_identity(n-1))
        slice_state.restore(out,previous,proof,args,WORK)
        print(f'RESTORED_EXPERIMENT_SLICE={n-1}',flush=True)
    elif os.environ.get('RAWS_UBO_COMPLETED_SEED'):
        producer = verify_completed_seed()
        proof = slice_state.receipt_at(COMPLETED,completed_identity(producer,args))
        if proof['status'] != 'compiled_apk':
            raise ValueError('Requested seed is not a completed compile')
        slice_state.restore(out,COMPLETED,proof,args,WORK)
        # Clear the input archive once restored; it should never be re-saved
        # as an output of the current commit.
        import shutil
        shutil.rmtree(COMPLETED)
        print(f'RESTORED_COMPLETED_EXPERIMENT={producer}',flush=True)
    run_logged(['timeout','--kill-after=30s','5m',str(depot/'gn'),'gen',str(out),
                '--fail-on-unused-args'],ART/'gn.log',phase='ubo-gn',cwd=src,env=env,check=True)
    budget=min(1380,int(3300-(time.time()-d.c.read(d.STATE/'job-start.json')['epoch'])-850))
    if budget < 120:
        raise ValueError('Insufficient compile budget after setup; GN generation passed')
    result=run_logged(remote_command(out,str(ART/'metrics.json'),'chrome_public_apk',budget),
                      ART/'compile.log',phase='ubo-apk',cwd=src,env=env)
    target=HANDOFF/f'stage-{n}'
    if result.returncode == 124:
        if n == LAST:
            raise ValueError('Final isolated slice expired before a verified APK')
        text=(ART/'compile.log').read_text()
        if not re.search(r'\d+ done, 0 failed, [1-9]\d* remaining',text):
            raise ValueError('Cannot prove a clean time limit interruption')
        slice_state.save(out,target,slice_identity(n),'slice_expired',WORK)
        print(f'SAVED_EXPERIMENT_SLICE={n}',flush=True)
        return
    result.check_returncode()
    apk=out/'apks/ChromePublic.apk'
    import zipfile
    with zipfile.ZipFile(apk) as z:
        if z.testzip() or 'AndroidManifest.xml' not in z.namelist():
            raise ValueError('Bad generated APK')
        abis={n.split('/')[1] for n in z.namelist() if n.startswith('lib/') and n.endswith('.so')}
    if abis != {'arm64-v8a'}:
        raise ValueError('Not a single-ABI Android test APK')
    sdk=sorted((src/'third_party/android_sdk/public/build-tools').glob('*/apksigner'))[-1].parent
    subprocess.run([str(sdk/'apksigner'),'verify',str(apk)],check=True,timeout=120)
    badging=subprocess.check_output([str(sdk/'aapt2'),'dump','badging',str(apk)],text=True,timeout=120)
    if not re.search(r"^package: name='io.github.sandeepbimt.raws'",badging,re.M):
        raise ValueError('Wrong package identity')
    import shutil
    shutil.copyfile(apk,ART/APK_NAME)
    (ART/'apk-receipt.json').write_text(json.dumps({
        'checkout':git(ROOT,'rev-parse','HEAD'),'base':BASE,'recipe_sha256':RECIPE,
        'experimental_patch_sha256':PATCH,'apk_sha256':file_sha(apk),
        'apk_signature_verified':True,'android_runtime_verified':False,
        'official_release':False,'regular_update':False,
    }, indent=2)+'\n')
    proof = slice_identity(n)
    proof.update(output_dir=out.as_posix(), args_sha256=hashlib.sha256(args).hexdigest())
    slice_state.save(out,target,proof,'done',WORK)


if __name__ == '__main__':
    gate()
    d=ro.full.D
    d.operation_budget=1100
    if sys.argv[1] == 'skip-if-done':
        if already_done():
            subprocess.run(['circleci-agent','step','halt'],check=True)
        raise SystemExit(0)
    actions={'select':select,'restore':ro.full.f.restore_base,
             'save-completed':save_completed,'verify-completed-seed':verify_completed_seed,
             'finish':ro.full.f.restore_finish,'compile':compile_apk}
    actions[sys.argv[1]]()
