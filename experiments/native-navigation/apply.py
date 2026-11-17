#!/usr/bin/env python3
"""Reversible native navigation comparison, applied AFTER frozen product overlays."""
import argparse,hashlib,importlib.util,json,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
PIN='d331de35ca8ab1358c7a17e4bd41627d55eaef51'
BRAVE='44a84b1f89d9a35287289d6a3d493e362f5a5123'
STATE='.sandium-native-navigation-state.json'
CHANGES=json.loads((HERE/'patches.json').read_text())
def recipe_hash():
 root=HERE.parents[1]
 paths=[HERE/'patches.json',HERE/'geometry.py',
        root/'.circleci/scripts/native-status-geometry.py',
        root/'.circleci/scripts/trace-sandium-back-geometry.py',
        root/'.circleci/features/native-status-geometry/reversal.json',
        root/'.circleci/features/native-status-geometry/paint.json']
 return hashlib.sha256(b''.join(p.read_bytes() for p in paths if p.exists())).hexdigest()

def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def transform(root):
 result={}
 for c in CHANGES:
  p=root/c['path'];s=result.get(p,p.read_text());old,new=c['old'],c['new']
  # Input must be the frozen overlay, not arbitrary already-edited native text.
  if s.count(old)!=1:raise RuntimeError('Native experiment anchor mismatch: '+c['path']+' '+old[:70])
  result[p]=s.replace(old,new,1)
 return result

def geometry_changes(root):
 geometry=HERE/'geometry.py'
 if not geometry.exists():return {}
 spec=importlib.util.spec_from_file_location('native_geometry',geometry)
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 return m.plan(root)

def plan(root,enabled):
 state_path=root/STATE
 if state_path.exists():
  state=json.loads(state_path.read_text())
  if state['schema']!=1:raise RuntimeError('Unknown native experiment snapshot')
  if enabled and state.get('recipe_sha256')!=recipe_hash():raise RuntimeError('Native experiment recipe changed; restore off before replay')
  result={}
  for relative,entry in state['files'].items():
   p=root/relative;current=p.read_text()
   if sha(entry['before'])!=entry['before_sha256'] or sha(entry['after'])!=entry['after_sha256']:raise RuntimeError('Corrupt native experiment snapshot: '+relative)
   if sha(current) not in (entry['before_sha256'],entry['after_sha256']):
    raise RuntimeError('Source changed after native experiment; refusing destructive restore: '+relative)
   result[p]=entry['after'] if enabled else entry['before']
  return result,state
 if not enabled:return {},None
 result=transform(root)
 extra=geometry_changes(root)
 if set(extra)&set(result):raise RuntimeError('Native geometry/transition overlap requires staged composition')
 result.update(extra)
 state={'schema':1,'recipe_sha256':recipe_hash(),'baseline_commit':'a6863ec','chromium_pin':PIN,'brave_pin':BRAVE,'files':{}}
 for p,after in result.items():
  before=p.read_text();state['files'][str(p.relative_to(root))]={'before':before,'after':after,'before_sha256':sha(before),'after_sha256':sha(after)}
 return result,state

def execute(root,enabled,verify_only=False):
 changes,state=plan(root,enabled)
 if verify_only:
  for p,s in changes.items():
   if p.read_text()!=s:raise RuntimeError('Native experiment verification differs: '+str(p))
  return
 # Save journal before writing so interrupted changes can safely resume/restore.
 if state is not None:
  temp=root/(STATE+'.tmp');temp.write_text(json.dumps(state));temp.replace(root/STATE)
 for p,s in changes.items():p.write_text(s)
 for p,s in changes.items():
  if p.read_text()!=s:raise RuntimeError('Native experiment write verification failed')
 if not enabled and state is not None:
  # Retire the restored journal before ordinary overlays replay. The next on
  # captures their latest frozen output, not stale previous-build preimages.
  (root/STATE).replace(root/(STATE+'.restored'))

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--mode',choices=['on','off','configured'],default='configured');p.add_argument('--verify-only',action='store_true');a=p.parse_args();r=a.source.resolve()
 if a.mode=='configured':a.mode='on' if json.loads((HERE/'profile.json').read_text())['enabled'] else 'off'
 for directory,pin in [(r,PIN),(r/'brave',BRAVE)]:
  if subprocess.check_output(['git','-C',str(directory),'rev-parse','HEAD'],text=True).strip()!=pin:raise RuntimeError('Pin mismatch')
 if a.mode=='on' and not (HERE/'geometry.py').exists():raise RuntimeError('Native geometry profile missing; refusing partial production experiment')
 execute(r,a.mode=='on',a.verify_only)
 print('SANDIUM_NATIVE_NAVIGATION='+a.mode.upper()+'; runtime comparison required')
if __name__=='__main__':main()
