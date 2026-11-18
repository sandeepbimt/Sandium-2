#!/usr/bin/env python3
"""Isolated Chromium bootstrap/build with fail-closed source identity checks."""
import argparse, hashlib, json, os, platform, re, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r'^[0-9a-f]{40}$')
def run(args, **kw):
    return subprocess.run(args, check=True, text=True, **kw)
def lock():
    value = json.loads((ROOT/'upstream.lock.json').read_text())
    assert SHA.fullmatch(value['chromium']['revision']), 'Invalid Chromium pin'
    assert value['cpu'] == 'arm64' and value['target'] == 'chrome_public_apk'
    return value
def workspace(path):
    p = Path(path).resolve()
    if p == ROOT or ROOT.is_relative_to(p):
        raise ValueError('Workspace cannot be project directory or its ancestor')
    marker = p/'.raw-sandium-workspace'
    if p.exists() and any(p.iterdir()) and not marker.is_file():
        raise ValueError('Refusing nonempty unowned workspace')
    p.mkdir(parents=True, exist_ok=True)
    marker.touch()
    return p
def preflight(path):
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise ValueError('Linux x86-64 build host required')
    p = Path(path).resolve()
    while not p.exists(): p = p.parent
    free = shutil.disk_usage(p).free
    if free < 100 * 1024**3:
        raise ValueError(f'Need 100 GiB free for clean Chromium build; have {free/1024**3:.1f} GiB')
    for binary in ('git','python3'):
        if not shutil.which(binary): raise ValueError(f'Missing {binary}')
def resolve_tools():
    data = lock()
    if data['depot_tools']['revision']:
        raise ValueError('depot_tools already pinned; upgrade through reviewed lock change')
    result = run(['git','ls-remote',data['depot_tools']['repository'],'HEAD'],capture_output=True,timeout=60)
    sha = result.stdout.split()[0]
    if not SHA.fullmatch(sha): raise ValueError('Invalid upstream depot_tools identity')
    data['depot_tools']['revision'] = sha
    (ROOT/'upstream.lock.json').write_text(json.dumps(data,indent=2)+'\n')
    print('Resolved depot_tools pin; commit reviewed lock before publishing a build.')
def verify(src, data):
    actual = run(['git','-C',str(src),'rev-parse','HEAD'],capture_output=True).stdout.strip()
    if actual != data['chromium']['revision']: raise ValueError('Wrong Chromium revision')
    if run(['git','-C',str(src),'status','--porcelain','--untracked-files=no'],capture_output=True).stdout:
        raise ValueError('Tracked Chromium changes present; baseline must be unmodified')
    if (src/'brave').exists(): raise ValueError('Brave directory present in clean baseline')
    version = dict(line.split('=',1) for line in (src/'chrome/VERSION').read_text().splitlines())
    if '.'.join(version[k] for k in ('MAJOR','MINOR','BUILD','PATCH')) != data['chromium']['version']:
        raise ValueError('Version does not match lock')
def setup(path):
    data = lock()
    rev = data['depot_tools']['revision']
    if not rev or not SHA.fullmatch(rev): raise ValueError('Resolve and commit depot_tools lock first')
    preflight(path)
    w = workspace(path)
    depot = w/'depot_tools'
    if not depot.exists(): run(['git','clone',data['depot_tools']['repository'],str(depot)])
    run(['git','-C',str(depot),'fetch','origin',rev])
    run(['git','-C',str(depot),'checkout','--detach',rev])
    env = dict(os.environ, PATH=str(depot)+os.pathsep+os.environ['PATH'],DEPOT_TOOLS_UPDATE='0')
    spec = 'solutions = '+repr([{'name':'src','url':data['chromium']['repository'],'managed':False,'custom_deps':{},'custom_vars':{}}])+"\ntarget_os = ['android']\n"
    cfg = w/'.gclient'
    if cfg.exists() and cfg.read_text()!=spec: raise ValueError('Unexpected gclient configuration')
    cfg.write_text(spec)
    run([str(depot/'gclient'),'sync','--nohooks','--revision','src@'+data['chromium']['revision']],cwd=w,env=env)
    verify(w/'src',data)
    print('Source ready. Install OS dependencies with src/build/install-build-deps.sh, then build.')
def build(path):
    data = lock(); w = Path(path).resolve()
    if not (w/'.raw-sandium-workspace').is_file(): raise ValueError('Not an owned workspace')
    verify(w/'src',data)
    actual = run(['git','-C',str(w/'depot_tools'),'rev-parse','HEAD'],capture_output=True).stdout.strip()
    if actual != data['depot_tools']['revision']: raise ValueError('Wrong depot_tools pin')
    env = dict(os.environ,PATH=str(w/'depot_tools')+os.pathsep+os.environ['PATH'],DEPOT_TOOLS_UPDATE='0')
    run(['gclient','runhooks'],cwd=w,env=env)
    out = w/'src/out/RawSandium'; out.mkdir(parents=True,exist_ok=True)
    args = (ROOT/'ci/args.gn').read_text()
    (out/'args.gn').write_text(args)
    # Remove only our output APK so a failed build cannot publish a stale artifact.
    apk = out/'apks/ChromePublic.apk'
    if apk.exists(): apk.unlink()
    run(['gn','gen','out/RawSandium'],cwd=w/'src',env=env)
    run(['autoninja','-C','out/RawSandium',data['target']],cwd=w/'src',env=env)
    if not apk.is_file() or not apk.stat().st_size: raise ValueError('No new APK')
    dest=ROOT/'artifacts'; dest.mkdir(exist_ok=True)
    shutil.copy2(apk,dest/'RawSandium-baseline-arm64.apk')
    receipt={'upstream':data,'apk_sha256':hashlib.sha256(apk.read_bytes()).hexdigest(),'gn_args_sha256':hashlib.sha256(args.encode()).hexdigest(),'features':[],'device_tested':False,'branding':'Chromium baseline, not yet Sandium'}
    (dest/'build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('command',choices=['preflight','resolve-tools','setup','build']); p.add_argument('--workspace',default=str(ROOT/'work'))
    a=p.parse_args()
    try:
        if a.command=='resolve-tools': resolve_tools()
        elif a.command=='preflight': preflight(a.workspace)
        elif a.command=='setup': setup(a.workspace)
        else: build(a.workspace)
    except (ValueError,AssertionError,subprocess.CalledProcessError,subprocess.TimeoutExpired) as e:
        print('BLOCKED:',e,file=sys.stderr); sys.exit(1)
