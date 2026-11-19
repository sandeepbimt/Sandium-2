#!/usr/bin/env python3
"""Reversible native navigation comparison, applied AFTER frozen product overlays."""
import argparse,hashlib,importlib.util,json,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
PIN='d331de35ca8ab1358c7a17e4bd41627d55eaef51'
BRAVE='44a84b1f89d9a35287289d6a3d493e362f5a5123'
STATE='.sandium-native-navigation-state.json'
CHANGES=json.loads((HERE/'patches.json').read_text())
def module(name):
 spec=importlib.util.spec_from_file_location('native_'+name,HERE/(name+'.py'))
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
diag=module('diagnostics')
settings=module('settings')
def source_identity(root):
 path=HERE.parents[1]/'.circleci/scripts/sandium-source-identity.py'
 spec=importlib.util.spec_from_file_location('native_source_identity',path)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 return module.verify(root)
def recipe_hash():
 root=HERE.parents[1]
 paths=[HERE/'patches.json',HERE/'geometry.py',HERE/'settings.py',HERE/'settings-reversal.json',HERE/'diagnostics.py',
        root/'experiments/native-transition-diagnostics/apply.py',
        root/'.circleci/scripts/native-status-geometry.py',
        root/'.circleci/scripts/trace-sandium-back-geometry.py',
        root/'.circleci/features/native-status-geometry/reversal.json',
        root/'.circleci/features/native-status-geometry/paint.json',
        HERE/'apply.py',root/'.circleci/scripts/sandium-source-identity.py',root/'.circleci/scripts/apply-sandium-page-transition-full.py',
        root/'.circleci/scripts/sandium-native-blur-source.py',
        root/'experiments/single-handoff/native_blur.py',
        *sorted((root/'experiments/single-handoff/fixtures/native-blur-158').glob('*'))]
 return hashlib.sha256(b''.join(p.read_bytes() for p in paths if p.exists())).hexdigest()

def sha(s):return hashlib.sha256(s.encode()).hexdigest()
def native158_blur(root, staged):
 # Authenticate the full reviewed158 intermediate; never apply156 lifecycle
 # reversal text to a new native manager. The outer owner adds dim separately.
 repository=HERE.parents[1]
 def load(path):
  spec=importlib.util.spec_from_file_location('native158_'+path.stem,path)
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
 native=load(repository/'experiments/single-handoff/native_blur.py')
 full=load(repository/'.circleci/scripts/apply-sandium-page-transition-full.py')
 capture=load(repository/'.circleci/scripts/sandium-native-blur-source.py')
 originals={native.CC:native.fixture(native.CC),native.H:native.fixture(native.H)}
 expected={native.CC:capture.implementation(full.transform_transition_cc(originals[native.CC])),
           native.H:capture.header(full.transform_transition_h(originals[native.H]))}
 current={p:staged.get(root/p,(root/p).read_text()) for p in originals}
 if not any(current[p]==expected[p] for p in originals):return {}
 if current!=expected:raise RuntimeError('Mixed or modified158 native blur overlay')
 return {root/p:text for p,text in originals.items()}

def transform(root):
 result={}
 probed=set()
 for path in diag.PATHS:
  p=root/path;text=p.read_text()
  if "SANDIUM_TRANSITION_RING_V1" in text:
   result[p]=diag.strip(path,text);probed.add(path)
 target_blur=native158_blur(root,result)
 result.update(target_blur)
 for c in CHANGES:
  if root/c['path'] in target_blur:continue
  p=root/c['path'];s=result.get(p,p.read_text());old,new=c['old'],c['new']
  # Input must be the frozen overlay, not arbitrary already-edited native text.
  if s.count(old)!=1:raise RuntimeError('Native experiment anchor mismatch: '+c['path']+' '+old[:70])
  result[p]=s.replace(old,new,1)
 for path in probed:
  p=root/path;result[p]=diag.apply(path,result[p])
 return result

def geometry_changes(root):
 geometry=HERE/'geometry.py'
 if not geometry.exists():return {}
 spec=importlib.util.spec_from_file_location('native_geometry',geometry)
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 return m.plan(root)

def plan(root,enabled,identity=None):
 state_path=root/STATE
 if state_path.exists():
  state=json.loads(state_path.read_text())
  if identity is not None and (state.get('chromium_pin'),state.get('brave_pin'))!=tuple(identity):raise RuntimeError('Native journal source identity mismatch')
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
 settings_changes=settings.plan(root)
 if set(settings_changes)&set(result):raise RuntimeError("Settings overlap requires composition")
 result.update(settings_changes)
 state={'schema':1,'recipe_sha256':recipe_hash(),'baseline_commit':'a6863ec','chromium_pin':identity[0] if identity else PIN,'brave_pin':identity[1] if identity else BRAVE,'files':{}}
 for p,after in result.items():
  before=p.read_text();state['files'][str(p.relative_to(root))]={'before':before,'after':after,'before_sha256':sha(before),'after_sha256':sha(after)}
 return result,state

def execute(root,enabled,verify_only=False,identity=None):
 changes,state=plan(root,enabled,identity)
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
 identity=source_identity(r)
 if a.mode=='on' and not (HERE/'geometry.py').exists():raise RuntimeError('Native geometry profile missing; refusing partial production experiment')
 execute(r,a.mode=='on',a.verify_only,identity)
 print('SANDIUM_NATIVE_NAVIGATION='+a.mode.upper()+'; runtime comparison required')
if __name__=='__main__':main()
