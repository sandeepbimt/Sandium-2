#!/usr/bin/env python3
"""Bounded fresh Android source sync; publish readiness only after identity validation."""
import hashlib,json,os,shutil,subprocess,time
from pathlib import Path
from raw import ROOT,lock,verify

def main():
    if os.environ.get('CIRCLE_BRANCH')!='raw-sandium/bootstrap':raise ValueError('Wrong branch')
    out=ROOT/'artifacts';out.mkdir(exist_ok=True)
    receipt={'phase':'source-sync','compilation_attempted':False,'apk_produced':False,'legacy_checkpoint_used':False,
             'lock_sha256':hashlib.sha256((ROOT/'upstream.lock.json').read_bytes()).hexdigest()}
    started=time.monotonic()
    try:
        if (ROOT/'work/source/source-ready.json').exists():
            old=json.loads((ROOT/'work/source/source-ready.json').read_text())
            if old.get('lock_sha256')!=receipt['lock_sha256'] or not old.get('ready'):raise ValueError('Cached source identity mismatch')
            verify(ROOT/'work/source/src',lock())
            receipt.update(ready=True,reused_verified_source=True)
            return 0
        with (out/'source-sync.log').open('w') as log:
            p=subprocess.run(['timeout','--signal=TERM','--kill-after=30s','25m','python3','-u',str(ROOT/'tools/raw.py'),'setup','--workspace',str(ROOT/'work/source')],stdout=log,stderr=subprocess.STDOUT)
        receipt['exit_code']=p.returncode
        if p.returncode:raise ValueError('Source sync stopped; see source-sync.log (124 means bounded time limit)')
        verify(ROOT/'work/source/src',lock())
        receipt['ready']=True
        (ROOT/'work/source/source-ready.json').write_text(json.dumps(receipt,indent=2)+'\n')
        return 0
    except Exception as e:
        receipt['ready']=False;receipt['blocker']=str(e);return 1
    finally:
        receipt['elapsed_seconds']=round(time.monotonic()-started)
        receipt['free_disk_bytes']=shutil.disk_usage(ROOT).free
        (out/'source-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps(receipt,indent=2))
if __name__=='__main__':raise SystemExit(main())
