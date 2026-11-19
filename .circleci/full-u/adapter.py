"""Bounded CLI target adapter. Actual target admission remains source-owned."""
import json,os,subprocess,sys
from pathlib import Path
import protocol

def commands(root):
 return {'source-synced':action(root,'verify-source'),'product-preparing':action(root,'verify-source'),
         'build-ready':action(root,'verify-product')}

def action(root,phase):
 return [sys.executable,str(Path(__file__).resolve()),phase,'--root',str(root)]

def runtime(root,install=True):
 root=Path(root);tools=root/'brave-work/.sandium/host-runtime'
 result=json.loads(subprocess.check_output([sys.executable,str(root/'.circleci/upgrades/bootstrap_host.py'),'install' if install else 'verify','--root',str(tools)],text=True))
 os.environ['PATH']=result['path']+os.pathsep+os.environ.get('PATH','')
 os.environ['DEPOT_TOOLS_UPDATE']='0'

def run(root,phase):
 root=Path(root);runtime(root,not phase.startswith('verify-'))
 if phase=='prepare-host':cmd=[sys.executable,str(root/'.circleci/upgrades/host_deps.py'),'prepare','--root',str(root)]
 elif phase=='verify-source':cmd=[sys.executable,str(root/'.circleci/upgrades/source.py'),'verify','--root',str(root/'brave-work')]
 elif phase=='verify-apk':cmd=[sys.executable,str(root/'.circleci/upgrades/apk.py'),'--root',str(root)]
 elif phase=='verify-product':cmd=[sys.executable,str(root/'.circleci/upgrades/product.py'),'verify','--root',str(root)]
 elif phase=='source-acquiring':cmd=[sys.executable,str(root/'.circleci/upgrades/source.py'),'acquire','--root',str(root/'brave-work')]
 elif phase=='product-preparing':
  subprocess.run([sys.executable,str(root/'.circleci/upgrades/host_deps.py'),'prepare','--root',str(root)],check=True)
  cmd=[sys.executable,str(root/'.circleci/upgrades/product.py'),'prepare','--root',str(root)]
 elif phase=='build-ready':
  src=root/'brave-work/src';depot=src/'brave/vendor/depot_tools'
  os.environ['PATH']=str(depot)+os.pathsep+os.environ['PATH'];os.environ['SISO_LIMITS']='local=8,remote=80'
  os.environ['PYTHONPATH']=':'.join(str(x) for x in (src/'brave/script',src/'tools/grit/grit/extern',src/'brave/vendor/requests',src/'build',depot))
  os.chdir(src)
  cmd=[str(depot/'autoninja'),'-strict_remote','-metrics_json','full-u-siso.jsonl','-C',str(src/'out/android_Release_arm64'),'-j80','brave']
 else:raise protocol.ProtocolError('unsupported phase')
 os.execvpe(cmd[0],cmd,os.environ)
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare-host','source-acquiring','product-preparing','build-ready','verify-source','verify-product','verify-apk']);p.add_argument('--root',type=Path,required=True);a=p.parse_args();run(a.root,a.phase)
