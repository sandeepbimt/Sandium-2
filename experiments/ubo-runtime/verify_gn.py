#!/usr/bin/env python3
"""Check effective GN argument, not merely the requested CLI switch."""
import argparse
import os
from pathlib import Path
import re
import subprocess

def require_enabled(output):
 if not re.fullmatch(r'\s*enable_extensions_core\s*=\s*true\s*', output):
  raise ValueError('EXT0 effective enable_extensions_core is not true: '+output)

def verify(src):
 gn=src/'buildtools/linux64/gn'
 env=os.environ.copy()
 env['PYTHONPATH']=os.pathsep.join(str(src/p) for p in ('brave/script','tools/grit/grit/extern','brave/vendor/requests','build','brave/vendor/depot_tools'))+os.pathsep+env.get('PYTHONPATH','')
 result=subprocess.run([str(gn),'args',str(src/'out/android_Release_arm64'),'--list=enable_extensions_core','--short'],cwd=src,env=env,text=True,capture_output=True)
 if result.returncode:raise ValueError(result.stdout+result.stderr)
 require_enabled(result.stdout)
 print('EXT0_EFFECTIVE_GN_GATE=PASS enable_extensions_core=true; runtime remains disabled')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--src',required=True,type=Path);a=p.parse_args();verify(a.src.resolve())
