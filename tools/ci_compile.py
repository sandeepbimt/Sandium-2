#!/usr/bin/env python3
"""Sequential 25-minute compile slices using this workflow's own output only."""
import argparse, hashlib, json, os, shutil, subprocess, tarfile, time
from pathlib import Path
from raw import ROOT, lock, verify
W=ROOT/'work/source'

def file_sha(path):
    with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def fingerprint():
    return hashlib.sha256((ROOT/'upstream.lock.json').read_bytes()+(ROOT/'ci/args.gn').read_bytes()).hexdigest()
def classify(code, apk):
    if code==0 and apk.is_file() and apk.stat().st_size:return 'done'
    if code==124:return 'slice_expired'
    raise ValueError(f'Build failed ({code}); not a resumable slice')
def safe_members(archive):
    members=archive.getmembers()
    for m in members:
        p=Path(m.name)
        if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0]!='RawSandium':raise ValueError('Unsafe output archive path')
        if not (m.isfile() or m.isdir()):raise ValueError('Unexpected output archive member type')
    return members

def main(stage):
    if os.environ.get('CIRCLE_BRANCH')!='raw-sandium/bootstrap' or stage not in (1,2,3):raise ValueError('Wrong build scope')
    ident=fingerprint(); folder=ROOT/f'handoff/stage{stage}';folder.mkdir(parents=True,exist_ok=True)
    artifacts=ROOT/'artifacts';artifacts.mkdir(exist_ok=True)
    state={'stage':stage,'fingerprint':ident,'apk_produced':False}
    try:
        for earlier in range(1,stage):
            old=json.loads((ROOT/f'handoff/stage{earlier}/state.json').read_text())
            if old['fingerprint']!=ident:raise ValueError('Foreign checkpoint identity')
            if old['status'] in ('done','skipped_done'):
                state['status']='skipped_done';return 0
        receipt=json.loads((W/'source-ready.json').read_text())
        expected=hashlib.sha256((ROOT/'upstream.lock.json').read_bytes()).hexdigest()
        if not receipt['ready'] or receipt['lock_sha256']!=expected:raise ValueError('Unverified source handoff')
        data=lock();verify(W/'src',data)
        actual=subprocess.check_output(['git','-C',str(W/'depot_tools'),'rev-parse','HEAD'],text=True).strip()
        if actual!=data['depot_tools']['revision']:raise ValueError('Wrong tool revision')
        if shutil.disk_usage(ROOT).free<20*1024**3:raise ValueError('Need 20 GiB free before compile')
        env=dict(os.environ,PATH=str(W/'depot_tools')+os.pathsep+os.environ['PATH'],DEPOT_TOOLS_UPDATE='0')
        with (artifacts/f'prepare-{stage}.log').open('w') as log:
            subprocess.run(['timeout','--kill-after=30s','15m','sudo','-n',str(W/'src/build/install-build-deps.sh'),'--android','--no-prompt'],check=True,stdout=log,stderr=subprocess.STDOUT,env=env)
            subprocess.run(['timeout','--kill-after=30s','10m','gclient','runhooks'],cwd=W,check=True,stdout=log,stderr=subprocess.STDOUT,env=env)
        out=W/'src/out/RawSandium';out.mkdir(parents=True,exist_ok=True)
        if stage>1:
            prev=ROOT/f'handoff/stage{stage-1}'
            prior=json.loads((prev/'state.json').read_text())
            if prior['status']!='slice_expired':raise ValueError('Previous slice not resumable')
            archive=prev/'output.tar.gz'
            if file_sha(archive)!=prior['archive_sha256']:raise ValueError('Checkpoint checksum mismatch')
            with tarfile.open(archive) as tar:tar.extractall(out.parent,members=safe_members(tar),filter='data')
        (out/'args.gn').write_text((ROOT/'ci/args.gn').read_text())
        subprocess.run(['gn','gen','out/RawSandium'],cwd=W/'src',env=env,check=True,timeout=300)
        apk=out/'apks/ChromePublic.apk'
        if apk.exists():apk.unlink()
        started=float((ROOT/'.raw-job-start').read_text()) if (ROOT/'.raw-job-start').exists() else time.time()
        budget=min(1500,int(3600-(time.time()-started)-900))
        if budget<120:raise ValueError('Insufficient job time for safe compile and checkpoint')
        state['compile_budget_seconds']=budget
        with (artifacts/f'compile-{stage}.log').open('w') as log:
            code=subprocess.run(['timeout','--signal=TERM','--kill-after=30s',str(budget)+'s','autoninja','-C','out/RawSandium','-j','4',data['target']],cwd=W/'src',env=env,stdout=log,stderr=subprocess.STDOUT).returncode
        state['status']=classify(code,apk)
        if state['status']=='done':
            shutil.copy2(apk,artifacts/'RawSandium-baseline-arm64.apk')
            state.update(apk_produced=True,apk_sha256=file_sha(apk),device_tested=False,branding='Chromium baseline')
        else:
            size=sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
            if shutil.disk_usage(ROOT).free<size+5*1024**3:raise ValueError('Insufficient checkpoint space')
            archive=folder/'output.tar.gz'
            with tarfile.open(archive,'w:gz',compresslevel=1) as tar:tar.add(out,arcname='RawSandium')
            state['archive_sha256']=file_sha(archive)
        return 0
    except Exception as e:
        state.update(status='failed',error=str(e));return 1
    finally:
        (folder/'state.json').write_text(json.dumps(state,indent=2)+'\n')
        (artifacts/f'build-state-{stage}.json').write_text(json.dumps(state,indent=2)+'\n')
        print(json.dumps(state,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',type=int,required=True)
    raise SystemExit(main(p.parse_args().stage))
