#!/usr/bin/env python3
"""Fresh-worker unchanged-target probe, never a cache promotion or offline claim."""
import json,os,shutil,subprocess,time
from pathlib import Path
import ci_full as c
from ci_compile import file_sha,host_dependency_command,verify_apk
from ci_remote import bootstrap_depot,configure,remote_command,run_logged
from raw import lock,verify
ROOT=c.ROOT

def validate_restore(selected,proof):
    p=c.D.valid(selected)
    if proof!={'receipt':selected['id'],'head':p['plan']['head']}:
        raise ValueError('Exact completed archive restore proof required')
    if p.get('apk_verified') is not True or not p.get('apk_sha256'):
        raise ValueError('Verified APK receipt required')
    return p

def metrics_summary(path):
    if not path.is_file() or not path.stat().st_size:
        return {'metrics_present':False,'classification':'inconclusive: no action metrics'}
    rows=[json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    actions=[x for x in rows if isinstance(x,dict) and x.get('step_id')]
    if not actions:return {'metrics_present':True,'classification':'inconclusive: no action records'}
    # Retain the strict remote gate, but account separately for pinned Siso's
    # observed `cache` metric (the shared historical auditor reads `cached`).
    for x in actions:
        if any(x.get(k) is True for k in ('err','scandeps_err','deps_log_err')):
            raise ValueError('Siso reports failed action')
        if x.get('action') in ('cc','cxx','link','solink') and not (x.get('is_remote') is True or x.get('cache') is True or x.get('cached') is True):
            raise ValueError('Compile/link action executed without remote execution')
    result={'actions':len(actions),'local':sum(x.get('is_local') is True for x in actions)}
    result['raw_cache_true']=sum(x.get('cache') is True for x in actions)
    result['raw_cached_true']=sum(x.get('cached') is True for x in actions)
    result['remote_cache_hits']=sum(x.get('is_remote') is True and (x.get('cache') is True or x.get('cached') is True) for x in actions)
    result['fresh_remote']=sum(x.get('is_remote') is True and x.get('cache') is not True and x.get('cached') is not True and x.get('no_exec') is not True for x in actions)
    result.update(metrics_present=True,no_exec=sum(x.get('no_exec') is True for x in actions))
    result['classification']=('remote/local work observed' if result['fresh_remote'] or result['local'] else
                              'remote cache hits observed' if result['remote_cache_hits'] else
                              'no execution reported in action metrics')
    return result

def main():
    artifacts=ROOT/'artifacts';artifacts.mkdir(exist_ok=True)
    result={'offline_complete':False,'normal_head_modified':False,'target_unchanged':True,'status':'failed'}
    try:
        if os.environ.get('RAWS_FINAL_ARCHIVE')!='true':raise ValueError('Explicit one-off probe required')
        c.gate()
        p=validate_restore(c.D.c.read(c.D.STATE/'selected.json'),c.D.c.read(c.D.STATE/'restored-proof.json'))
        w=ROOT/'work/source';src=w/'src';out=src/'out/RawSandium';apk=out/'apks/ChromePublic.apk';data=lock()
        verify(src,data)
        if subprocess.check_output(['git','-C',str(w/'depot_tools'),'rev-parse','HEAD'],text=True).strip()!=data['depot_tools']['revision']:
            raise ValueError('Wrong pinned depot tools')
        before=file_sha(apk)
        if before!=p['apk_sha256']:raise ValueError('Restored APK hash mismatch')
        siso=src/'third_party/siso/cipd/siso'
        result['siso_binary']={'exists':siso.is_file(),'sha256':file_sha(siso) if siso.is_file() else None}
        if siso.is_file():
            version=subprocess.run([str(siso),'version'],capture_output=True,text=True,timeout=30)
            result['siso_binary'].update(version_exit=version.returncode,version_output=version.stdout.strip()[:1000])
        args_before=(out/'args.gn').read_bytes()
        if args_before!=(ROOT/'ci/args.gn').read_bytes():raise ValueError('Restored GN args differ')
        result.update(apk_sha256_before=before,siso_state_before={n:{'exists':(out/n).is_file(),'bytes':(out/n).stat().st_size if (out/n).is_file() else 0,'sha256':file_sha(out/n) if (out/n).is_file() else None} for n in ('.siso_fs_state','.siso_deps')})
        env=dict(os.environ,PATH=str(w/'depot_tools')+os.pathsep+os.environ['PATH'],DEPOT_TOOLS_UPDATE='0')
        run_logged(host_dependency_command(src),artifacts/'restore-probe-setup.log',phase='probe-host-dependencies',check=True,env=env,stdin=subprocess.DEVNULL)
        env=bootstrap_depot(w/'depot_tools',data['depot_tools']['revision'],env,artifacts,'restore-probe')
        env,result['remote_config']=configure(src,w/'depot_tools',env)
        if (out/'args.gn').read_bytes()!=args_before:raise ValueError('Probe changed GN args')
        elapsed=time.time()-c.D.c.read(c.D.STATE/'job-start.json')['epoch']
        budget=min(900,int(3300-elapsed-240))
        if budget<60:raise ValueError('Insufficient probe budget')
        metrics=out/'raws-restore-probe.jsonl';metrics.unlink(missing_ok=True)
        result['probe_budget_seconds']=budget
        code=run_logged(remote_command(out,metrics.name,data['target'],budget),artifacts/'restore-probe-build.log',phase='unchanged-target-restore-probe',cwd=src,env=env).returncode
        result['exit_code']=code
        result['metrics']=metrics_summary(metrics)
        if metrics.exists():shutil.copy2(metrics,artifacts/metrics.name)
        if code!=0:raise ValueError('Unchanged target probe did not finish; inspect logs for rebuild/CAS/timeout evidence')
        result.update(verify_apk(apk,src,env));result['apk_sha256_after']=file_sha(apk)
        result['siso_state_after']={n:{'exists':(out/n).is_file(),'sha256':file_sha(out/n) if (out/n).is_file() else None} for n in ('.siso_fs_state','.siso_deps')}
        result['apk_identical']=result['apk_sha256_after']==before
        if not result['apk_identical']:raise ValueError('Unchanged-target probe changed APK digest; exact reuse not validated')
        result['incremental_state_proof']=all(x['exists'] for x in result['siso_state_before'].values())
        result['status']='completed' if result['incremental_state_proof'] else 'inconclusive_missing_incremental_state'
        result['reusable_label']='not promoted: remote-enabled probe, not offline materialization proof'
        return 0
    except Exception as e:
        result['error']=str(e);return 1
    finally:
        (artifacts/'restore-probe.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':raise SystemExit(main())
