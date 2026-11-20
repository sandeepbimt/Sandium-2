#!/usr/bin/env python3
"""Sequential 25-minute compile slices using this workflow's own output only."""
import argparse, hashlib, json, os, re, shutil, subprocess, tarfile, time, zipfile
from pathlib import Path
from raw import ROOT, lock, verify
from ci_official import verify_official
from ci_remote import configure, smoke, remote_command, audit, run_logged, bootstrap_depot, verify_graph_outputs
W=ROOT/'work/source'

def file_sha(path):
    with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def fingerprint():
    files=[ROOT/'upstream.lock.json',ROOT/'ci/args.gn',ROOT/'tools/ci_remote.py',ROOT/'tools/source_compat.py',ROOT/'tools/raw.py',ROOT/'tools/ci_official.py']
    files+=sorted((ROOT/'patches').rglob('*'))+sorted((ROOT/'sandium/features').rglob('*'))
    h=hashlib.sha256()
    for p in files:
        if p.is_file():h.update(str(p.relative_to(ROOT)).encode()+b'\0'+p.read_bytes()+b'\0')
    return h.hexdigest()
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

def host_dependency_command(src):
    # Pinned Chromium Android docs invoke this without deprecated --android.
    # That compatibility flag merely enables i386/multilib, not Android tools.
    return ['timeout','--kill-after=30s','15m',
            str(src/'build/install-build-deps.sh'),'--no-prompt']

def compile_budget(elapsed, fresh_seed):
    # Established Full reserves, capped to the requested 25-minute slice.
    save_reserve=600 if fresh_seed else 300
    return min(1500, int(3300-elapsed-900-save_reserve-60-180))

def restore_only_feature_budget(elapsed):
    # No archive phase: keep the same job clock and APK verification/upload reserve.
    return min(1800, int(3300-elapsed-180))

def restore_only_feature_command(out, metrics, target, budget):
    if not 1 <= budget <= 1800:
        raise ValueError('Restore-only feature slice must fit the 30-minute cap')
    cmd=remote_command(out,metrics,target,min(budget,1500))
    if budget > 1500:
        # Only the outer wall-clock limit changes. Keep the fingerprinted
        # builder, strict-remote mode, and all build/metrics arguments intact.
        prefix=['timeout','--signal=INT','--kill-after=60s','1500s','autoninja','-strict_remote']
        if cmd[:len(prefix)] != prefix:
            raise ValueError('Unexpected strict-remote timeout command prefix')
        cmd[3]=f'{budget}s'
    return cmd

def verify_apk(apk, src, env):
    with zipfile.ZipFile(apk) as z:
        bad=z.testzip()
        if bad:raise ValueError('APK ZIP checksum failed: '+bad)
        names=z.namelist()
        if 'AndroidManifest.xml' not in names:raise ValueError('APK manifest missing')
        abis={n.split('/')[1] for n in names if n.startswith('lib/') and n.endswith('.so')}
        if abis!={'arm64-v8a'}:raise ValueError('Unexpected APK native ABIs: '+repr(sorted(abis)))
    candidates=sorted((src/'third_party/android_sdk/public/build-tools').glob('*/apksigner'))
    if not candidates:raise ValueError('Pinned SDK apksigner unavailable')
    signer=candidates[-1]
    aapt=signer.parent/'aapt2'
    if not aapt.is_file():raise ValueError('Pinned SDK aapt2 unavailable')
    subprocess.run([str(signer),'verify',str(apk)],env=env,check=True,timeout=120,
                   stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    badging=subprocess.check_output([str(aapt),'dump','badging',str(apk)],env=env,text=True,timeout=60)
    match=re.search(r"^package: name='([^']+)'",badging,re.M)
    if not match or match.group(1)!='org.chromium.chrome':
        raise ValueError('Unexpected Chromium baseline APK package')
    return {'apk_verified':True,'apk_sha256':file_sha(apk),'apk_package':match.group(1),
            'apk_abis':sorted(abis),'apk_signature_verified':True,'apk_zip_verified':True}

def main(stage, *, feature=None):
    if os.environ.get('CIRCLE_BRANCH')!='raw-sandium/official158' or stage not in (1,2,3,4,5):raise ValueError('Wrong build scope')
    if feature is not None and (stage != 1 or os.environ.get('RAWS_ALLOW_FRESH_SEED') != 'false'):
        raise ValueError('Feature build requires strict restore-only stage 1')
    source_verifier = verify if feature is None else feature.verify
    ident=fingerprint(); folder=ROOT/f'handoff/stage{stage}';folder.mkdir(parents=True,exist_ok=True)
    artifacts=ROOT/'artifacts';artifacts.mkdir(exist_ok=True)
    state={'stage':stage,'fingerprint':ident,'apk_produced':False}
    if feature is not None:state['feature_recipe_sha256']=feature.identity
    try:
        receipt=json.loads((W/'source-ready.json').read_text())
        expected=hashlib.sha256((ROOT/'upstream.lock.json').read_bytes()).hexdigest()
        if not receipt['ready'] or receipt['lock_sha256']!=expected:raise ValueError('Unverified source handoff')
        data=lock();source_verifier(W/'src',data)
        actual=subprocess.check_output(['git','-C',str(W/'depot_tools'),'rev-parse','HEAD'],text=True).strip()
        if actual!=data['depot_tools']['revision']:raise ValueError('Wrong tool revision')
        if shutil.disk_usage(ROOT).free<20*1024**3:raise ValueError('Need 20 GiB free before compile')
        env=dict(os.environ,PATH=str(W/'depot_tools')+os.pathsep+os.environ['PATH'],DEPOT_TOOLS_UPDATE='0')
        run_logged(host_dependency_command(W/'src'),
                   artifacts/f'prepare-{stage}.log',phase=f'install-dependencies-{stage}',check=True,env=env,stdin=subprocess.DEVNULL)
        run_logged(['timeout','--kill-after=30s','10m','gclient','runhooks'],
                   artifacts/f'prepare-{stage}.log',phase=f'runhooks-{stage}',append=True,cwd=W,check=True,env=env)
        env=bootstrap_depot(W/'depot_tools',data['depot_tools']['revision'],env,artifacts,stage)
        out=W/'src/out/RawSandium';out.mkdir(parents=True,exist_ok=True)
        # Full checkpoint driver restores source and output together before this step.
        # No legacy whole-output tar path may bypass its verified chain.
        state['restored_checkpoint']='managed by RawS Full driver'
        env, state['remote_config'] = configure(W/'src', W/'depot_tools', env)
        (out/'args.gn').write_text((ROOT/'ci/args.gn').read_text())
        run_logged(['timeout','--kill-after=30s','5m',str(W/'depot_tools/gn'),'gen','out/RawSandium','--fail-on-unused-args'],
                   artifacts/f'gn-{stage}.log',phase=f'gn-generation-{stage}',cwd=W/'src',env=env,check=True)
        state['official_build']=verify_official(W/'src',W/'depot_tools',out,env,artifacts,stage)
        state['gn_output_path_gate']=verify_graph_outputs(W/'src',W/'depot_tools',out,env,artifacts,stage)
        if feature is not None:
            from ci_prepare_raws_engine import run_native_gate,verify_apk_graph
            source_verifier(W/'src',data)
            verify_apk_graph(W/'src', W/'depot_tools'/'gn',out,env,
                             artifacts/'raws-engine-apk-graph.txt',require_ui=feature.has_ui)
            state['raws_engine_apk_graph_verified']=True
            if feature.has_ui:state['raws_ui_apk_graph_verified']=True
            epoch=json.loads((ROOT/'.checkpoint-state/job-start.json').read_text())['epoch']
            # Leave time for the Android build, verification and the APK upload.
            native_budget=min(360,int(3300-(time.time()-epoch)-1060))
            state['raws_engine_smoke']=run_native_gate(W/'src',artifacts,env,native_budget)
        apk=out/'apks/ChromePublic.apk'
        if apk.exists():apk.unlink()
        started=json.loads((ROOT/'.checkpoint-state/job-start.json').read_text())['epoch']
        elapsed=time.time()-started
        budget=(restore_only_feature_budget(elapsed) if feature is not None
                else compile_budget(elapsed,(ROOT/'.checkpoint-state/fresh.json').is_file()))
        if budget<120:raise ValueError('Insufficient job time for safe compile and publication')
        state['compile_budget_seconds']=budget
        deadline=time.monotonic()+budget
        if stage==1:
            try:
                state['remote_smoke']=smoke(W/'src',out,env,artifacts,stage,budget)
            except subprocess.CalledProcessError as e:
                if e.returncode!=124:raise
                # Same Full-mode bounded probe policy: a cold prerequisite set
                # can exceed 10m. Real build stays strict remote and is audited.
                state['remote_smoke']={'status':'timeout_warning','verified':False}

        remaining=int(deadline-time.monotonic())
        if remaining<1:
            code=124
        else:
            metrics=f'raws-stage-{stage}-build.jsonl'
            (out/metrics).unlink(missing_ok=True)
            command=remote_command if feature is None else restore_only_feature_command
            code=run_logged(command(out,metrics,data['target'],remaining),
                artifacts/f'compile-{stage}.log',phase=f'compile-{stage}',cwd=W/'src',env=env).returncode
            if code in (0,124):
                # Audit real compilation, not merely configured flags. Time-slice
                # checkpoints may have no finished action; record that explicitly.
                if (out/metrics).is_file() and (out/metrics).stat().st_size:
                    state['remote_audit']=audit(out/metrics)
                    shutil.copy2(out/metrics,artifacts/metrics)
                elif code==0:
                    raise ValueError('Successful build has no remote execution metrics')
                else:
                    state['remote_audit']={'status':'no completed actions before slice expiry'}
        state['status']=classify(code,apk)
        if state['status']=='done':
            if feature is not None:source_verifier(W/'src',data)
            state.update(verify_apk(apk,W/'src',env))
            name='RawSandium-EasyList-arm64.apk' if feature is not None else 'RawSandium-baseline-arm64.apk'
            shutil.copy2(apk,(folder if feature is not None else artifacts)/name)
            state.update(apk_produced=True,apk_sha256=file_sha(apk),device_tested=False,branding='Chromium baseline')
        else:
            state['checkpoint_required']=True
            # The proven Full driver captures the immutable delta and receipt;
            # no whole output archive is generated by this compile adapter.
        return 0
    except Exception as e:
        state.update(status='failed',error=str(e));return 1
    finally:
        for name in ('siso_output', 'siso_failed_commands.sh', 'siso.INFO'):
            diagnostic=W/'src/out/RawSandium'/name
            if diagnostic.is_file():
                shutil.copy2(diagnostic, artifacts/f'stage-{stage}-{name}')
        for metric in (W/'src/out/RawSandium').glob(f'raws-stage-{stage}-*.jsonl'):
            shutil.copy2(metric, artifacts/metric.name)
        (folder/'state.json').write_text(json.dumps(state,indent=2)+'\n')
        (artifacts/f'build-state-{stage}.json').write_text(json.dumps(state,indent=2)+'\n')
        print(json.dumps(state,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',type=int,required=True)
    raise SystemExit(main(p.parse_args().stage))
