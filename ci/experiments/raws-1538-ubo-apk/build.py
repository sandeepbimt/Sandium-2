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

BASE = 'a274d3f2e250aad22c8ca4309ba75841f9db65dd'
BRANCH = 'experiment/raws-1538-ubo-apk'
JOB = 'raws-1538-ubo-apk'
RECIPE = '4056f5936653bdc9a540e1c42fadd77e56680aaf519f3b38736ebcac9d617156'
PATCH = 'a1f1ebc640782583b4d45780d2184969e57a68da82ff0fd113a7b055558b73bc'
WORK = ROOT/'work/source'
ART = ROOT/'artifacts'


def git(cwd, *args):
    return subprocess.check_output(['git', '-C', str(cwd), *args], text=True).strip()


def gate():
    if (os.environ.get('CIRCLE_BRANCH'), os.environ.get('CIRCLE_JOB'),
        os.environ.get('CIRCLE_PROJECT_REPONAME')) != (BRANCH, JOB, 'Sandium-2'):
        raise ValueError('Wrong project, branch, or job')
    if any(k.startswith('RAWS_') and any(t in k for t in ('KEYSTORE','KEY_PASSWORD','SIGNING'))
           for k in os.environ):
        raise ValueError('Experiment must not receive RawS signing credentials')
    head = git(ROOT,'rev-parse','HEAD')
    if head != os.environ.get('CIRCLE_SHA1') or git(ROOT,'rev-parse','HEAD^') != BASE:
        raise ValueError('Experimental build must be one commit on exact #1538')
    if fingerprint() != ro.FINGERPRINT or ro.full.fresh():
        raise ValueError('Unexpected baseline fingerprint or fresh seed')
    if ro.active_feature().identity != RECIPE:
        raise ValueError('Corrected #1538 recipe required')
    if file_sha(KIT/'pinned-ubo.patch') != PATCH:
        raise ValueError('Wrong reviewed package-admission patch')
    ro.full.D.gate()


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
    run_logged(['timeout','--kill-after=30s','5m',str(depot/'gn'),'gen',str(out),
                '--fail-on-unused-args'],ART/'gn.log',phase='ubo-gn',cwd=src,env=env,check=True)
    budget=min(1500,int(3300-(time.time()-d.c.read(d.STATE/'job-start.json')['epoch'])-150))
    if budget < 120:
        raise ValueError('Insufficient compile budget after setup; GN generation passed')
    run_logged(remote_command(out,str(ART/'metrics.json'),'chrome_public_apk',budget),
               ART/'compile.log',phase='ubo-apk',cwd=src,env=env,check=True)
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
    shutil.copyfile(apk,ART/'RawS-1538-uBO-MV2-test.apk')
    (ART/'apk-receipt.json').write_text(json.dumps({
        'checkout':git(ROOT,'rev-parse','HEAD'),'base':BASE,'recipe_sha256':RECIPE,
        'experimental_patch_sha256':PATCH,'apk_sha256':file_sha(apk),
        'apk_signature_verified':True,'android_runtime_verified':False,
        'official_release':False,'regular_update':False,
    }, indent=2)+'\n')


if __name__ == '__main__':
    gate()
    d=ro.full.D
    d.operation_budget=1100
    actions={'select':select,'restore':ro.full.f.restore_base,
             'finish':ro.full.f.restore_finish,'compile':compile_apk}
    actions[sys.argv[1]]()
