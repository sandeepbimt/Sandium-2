#!/usr/bin/env python3
"""Real source-owner compile probe for an already generated pinned CI tree.

Planning/readiness is NOT compilation. A completed probe is NOT a full link,
packaging, APK audit or runtime result. This never writes a completion receipt.
"""
import argparse
import json
import math
import os
from pathlib import Path, PurePosixPath
import signal
import re
import subprocess
import time

SOURCE_SUFFIXES={'.c','.cc','.cpp','.cxx','.h','.hpp','.java','.kt','.aidl','.mojom','.proto','.rs'}
EXCLUDED_TYPES='group,executable,shared_library,loadable_module,create_bundle,bundle_data'


def safe_relative(value):
    p=PurePosixPath(value)
    if not value or p.is_absolute() or '..' in p.parts or str(p)!=value or any(c in value for c in '\r\n\0'):
        raise ValueError('Unsafe source/output path: '+repr(value))
    return value


def source_inputs(manifest, src):
    """Declared edited inputs only; generated/new sources are a stated coverage gap."""
    files=[];missing=[]
    for key,prefix in (('core_restore','brave/'),('chromium_restore','')):
        if not isinstance(manifest.get(key),list):raise ValueError('Missing reset source manifest')
        for name in manifest[key]:
            rel=safe_relative(prefix+safe_relative(name))
            if Path(rel).suffix not in SOURCE_SUFFIXES:continue
            if (src/rel).is_file():files.append('//'+rel)
            else:missing.append(rel)
    if missing:raise ValueError('Declared source inputs absent: '+json.dumps(missing))
    if not files:raise ValueError('No declared compilable source inputs')
    return sorted(set(files))


def target_outputs(text):
    values=[]
    for value in text.splitlines():
        value=value.strip()
        if not value:continue
        safe_relative(value)
        if not re.fullmatch(r'[A-Za-z0-9_./+@-]+',value) or value.startswith('-') or ':' in value or value.endswith(('.apk','.aab','.so')):
            raise ValueError('Unexpected compile probe output: '+value)
        values.append(value)
    if not values:raise ValueError('GN resolved no direct non-link source-owner outputs')
    if len(values)>2000 or sum(len(v)+1 for v in values)>100000:raise ValueError('Source-owner plan is too broad; split and review it before compilation')
    return sorted(set(values))


def package_readiness(src):
    tools=src/'third_party/android_sdk/public/build-tools/37.0.0'
    result={name:os.access(tools/name,os.X_OK) for name in ('aapt','apksigner','zipalign')}
    if not all(result.values()):raise ValueError('Pinned packaging tools unavailable: '+json.dumps(result))
    # Running a version command catches missing interpreter/JVM/shared-library
    # problems, without claiming that signing or packaging has succeeded.
    for name,args in [('aapt',['version']),('apksigner',['version'])]:
        subprocess.run([str(tools/name),*args],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
    return {'tool_executables_present':result,'aapt_apksigner_launch':True,
            'apk_packaged':False,'signature_verified':False,'manifest_verified':False}


def bounded_run(command,cwd,env,seconds,log):
    started=time.monotonic()
    with log.open('w') as stream:
        p=subprocess.Popen(command,cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        try:rc=p.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGINT)
            try:p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid,signal.SIGKILL);p.wait()
            return {'status':'INCOMPLETE_TIMEOUT','exit_code':124,'elapsed_seconds':round(time.monotonic()-started,2)}
    return {'status':'PASS_SELECTED_TARGETS' if rc==0 else 'FAILED','exit_code':rc,
            'elapsed_seconds':round(time.monotonic()-started,2)}


def compile_budget(requested, start, now):
    if isinstance(start,bool) or not isinstance(start,(int,float)) or not math.isfinite(start) or start<=0 or start>now:
        raise ValueError('Invalid or future job start timestamp')
    if not isinstance(requested,int) or not 0<=requested<=2400:
        raise ValueError('Invalid requested compile time')
    remaining=math.floor(3300-(now-start)-180-30)
    return max(0,min(requested,remaining))


def parse_args(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--src',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--report-dir',type=Path,required=True)
    p.add_argument('--compile-seconds',type=int,default=0,help='0 plans only; >0 performs bounded real compilation, never final link')
    p.add_argument('--job-start',type=Path,required=True,help='Same-job epoch receipt used to cap actual compilation')
    return p.parse_args(argv)


def main(argv=None):
    a=parse_args(argv);src=a.src.resolve();out=a.out.resolve();report=a.report_dir.resolve()
    if not 0<=a.compile_seconds<=2400:raise ValueError('compile-seconds must be between0 and2400')
    if src not in out.parents:raise ValueError('Build output must be inside pinned source tree')
    gn=src/'buildtools/linux64/gn'
    if not os.access(gn,os.X_OK) or not (out/'build.ninja').is_file():raise ValueError('Generated pinned GN graph required')
    report.mkdir(parents=True,exist_ok=True)
    result={'schema':1,'full_build_verified':False,'link_verified':False,'apk_verified':False,
            'coverage':'Direct non-link GN owners of declared edited source inputs; excludes final link, APK, runtime and undeclared generated files',
            'status':'STARTED'}
    report_file=report/'build-precheck.json'
    try:
        result['packaging_readiness']=package_readiness(src)
        inputs=source_inputs(json.loads(a.manifest.read_text()),src)
        response=report/'source-inputs.rsp';response.write_text('\n'.join(inputs)+'\n')
        result['declared_source_count']=len(inputs)
        # GNU output is generated from actual pinned graph; never guess target names.
        proc=subprocess.run([str(gn),'refs',str(out),'@'+str(response),'--testonly=false',
                             '--exclude-type='+EXCLUDED_TYPES,'--as=output','-q'],cwd=src,
                            text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=180)
        outputs=target_outputs(proc.stdout)
        (report/'compile-targets.txt').write_text('\n'.join(outputs)+'\n')
        result['target_count']=len(outputs)
        result['status']='PLAN_ONLY_NOT_COMPILED'
        if a.compile_seconds:
            start=json.loads(a.job_start.read_text())['epoch']
            budget=compile_budget(a.compile_seconds,start,time.time())
            result['compile_budget_seconds']=budget
            result['requested_compile_seconds']=a.compile_seconds
            if budget<60:
                result['status']='INCOMPLETE_NO_TIME'
                result['compilation']={'status':'INCOMPLETE_NO_TIME','exit_code':124,'elapsed_seconds':0}
                report_file.write_text(json.dumps(result,indent=2)+'\n')
                print('SANDIUM_BUILD_PRECHECK=INCOMPLETE_NO_TIME')
                return 124
            depot=src/'brave/vendor/depot_tools';autoninja=depot/'autoninja'
            if not os.access(autoninja,os.X_OK):raise ValueError('Pinned Brave autoninja required')
            if not os.environ.get('BUILDBUDDY_API_KEY'):raise ValueError('BuildBuddy credentials required for strict remote probe')
            env=dict(os.environ);env['PATH']=str(depot)+':'+env.get('PATH','');env['DEPOT_TOOLS_UPDATE']='0';env['SISO_LIMITS']='local=8,remote=80'
            env['PYTHONPATH']=':'.join(str(x) for x in [src/'brave/script',src/'tools/grit/grit/extern',src/'brave/vendor/requests',src/'build',depot])+(':'+env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
            command=[str(autoninja),'-strict_remote','-metrics_json','sandium-targeted-precheck.jsonl','-C',str(out),'-j80',*outputs]
            result['compilation']=bounded_run(command,src,env,budget,report/'compile.log')
            result['status']=result['compilation']['status']
        report_file.write_text(json.dumps(result,indent=2)+'\n')
        print('SANDIUM_BUILD_PRECHECK='+result['status'])
        return result.get('compilation',{}).get('exit_code',0)
    except Exception as exc:
        result['status']='FAILED';result['error']=str(exc);report_file.write_text(json.dumps(result,indent=2)+'\n');raise

if __name__=='__main__':raise SystemExit(main())
