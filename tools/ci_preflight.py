#!/usr/bin/env python3
"""Read-only CI feasibility probe. No source checkout, credentials or cache use."""
import json, os, platform, shutil, subprocess, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXPECTED_BRANCH='raw-sandium/bootstrap'
def memory_bytes():
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemTotal:'):return int(line.split()[1])*1024
    return 0
def probe():
    lock=json.loads((ROOT/'upstream.lock.json').read_text())
    disk=shutil.disk_usage(ROOT).free
    memory=memory_bytes()
    checks={'branch':os.environ.get('CIRCLE_BRANCH')==EXPECTED_BRANCH,
            'linux_x64':platform.system()=='Linux' and platform.machine()=='x86_64',
            'disk_100gib':disk>=100*1024**3,'memory_8gb':memory>=7.5*1024**3,
            'git':bool(shutil.which('git')),'python':bool(shutil.which('python3'))}
    endpoints={}
    for name,url in [('chromium_version',lock['chromium']['provenance']),('depot_tools','https://chromium.googlesource.com/chromium/tools/depot_tools.git/info/refs?service=git-upload-pack')]:
        try:
            with urllib.request.urlopen(url,timeout=30) as response:
                body=response.read(4096)
                endpoints[name]={'ok':response.status==200,'status':response.status}
                if name=='chromium_version':
                    values=dict(line.split('=',1) for line in body.decode().splitlines())
                    checks['upstream_version']='.'.join(values[k] for k in ('MAJOR','MINOR','BUILD','PATCH'))==lock['chromium']['version']
        except Exception as e:
            endpoints[name]={'ok':False,'error_type':type(e).__name__}
    checks['upstream_network']=all(x['ok'] for x in endpoints.values())
    result={'schema':1,'checks':checks,'free_disk_bytes':disk,'memory_bytes':memory,'cpu_count':os.cpu_count(),'network':endpoints,'compilation_attempted':False,'apk_produced':False,'checkpoint_used':False,'next_step':'Design separate source/toolchain persistence and bounded compile stages only after reviewing probe.'}
    out=ROOT/'artifacts';out.mkdir(exist_ok=True)
    (out/'ci-preflight.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    return 0 if all(checks.values()) else 1
if __name__=='__main__':raise SystemExit(probe())
