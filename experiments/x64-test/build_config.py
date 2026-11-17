#!/usr/bin/env python3
"""Static isolated x64 derivation; original ARM scripts/reference remain read-only."""
import copy,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).resolve().parent/"vendor"))
import yaml
BRANCH='experiment/native-x64-api15'
DEST='.circleci/x64-test'
SOURCES=[
 '.circleci/scripts/prepare-brave-source.sh',
 '.circleci/scripts/verify-clang-diagnostics-gn.sh',
 '.circleci/scripts/verify-brave-remote-smoke.sh',
 '.circleci/scripts/archive-brave-workspace.sh',
 '.circleci/scripts/capture-brave-siso-checkpoint.sh',
 '.circleci/scripts/sandium-checkpoint-shards.py',
 '.circleci/scripts/verify-brave-reference.sh',
 '.circleci/scripts/precheck-graph.py',
 '.circleci/experimental-steps/product-overlay-27-0.sh',
 '.circleci/experimental-steps/product-overlay-30-0.sh',
 '.circleci/experimental-steps/export-apk.sh',
]
PATHS={s:f'{DEST}/{Path(s).name}' for s in SOURCES}

def replace_paths(text):
 for old,new in PATHS.items():text=text.replace(old,new)
 return text

def arch(text):
 return text.replace('android_Release_arm64','android_Release').replace('BraveMonoarm64','BraveMonox64').replace('android-arm64','android-x64').replace('--target_arch=arm64','--target_arch=x64').replace('target_cpu = "arm64"','target_cpu = "x64"')

def scripts(root):
 result={}
 for source,dest in PATHS.items():
  text=(root/source).read_text()
  text=replace_paths(arch(text))
  if source.endswith('prepare-brave-source.sh'):
   # First x64 stage must run native Brave target-aware dependency sync, not
   # mistake the verified ARM bootstrap's preservation marker for x64 state.
   anchor='  SOURCE_REUSE=false\n'
   assert text.count(anchor)==1
   text=text.replace(anchor,anchor+'  rm -f "$ROOT/brave-work/.sandium/workspace-checkpoint-restored"\n')
   anchor='      if [ -s "$GCLIENT_FILE" ] && [ -s "$GCLIENT_ENTRIES" ] && \\\n'
   assert text.count(anchor)==1
   text=text.replace(anchor,'      if false && [ -s "$GCLIENT_FILE" ] && [ -s "$GCLIENT_ENTRIES" ] && \\\n')
  if source.endswith('archive-brave-workspace.sh'):
   anchor='    echo "SANDIUM-FULL-MODE archive: parallel workers=$WORKERS"'
   assert text.count(anchor)==1
   text=text.replace(anchor,'    python3 "$ROOT/experiments/x64-test/reclaim_bootstrap.py" "$ROOT" --archive-space\n'+anchor)
  if source.endswith('precheck-graph.py'):
   # Retain original audited source-policy scripts, route only the output path.
   assert "scripts = root / '.circleci/scripts'" in text
  if source.endswith('sandium-checkpoint-shards.py'):
   # Do not archive the 26GB ARM object tree as if it were x64 reusable state.
   anchor='    for item in children(out):\n        if item == output:\n'
   assert text.count(anchor)==1
   text=text.replace(anchor,'    for item in children(out):\n        if item.name == "android_Release_arm64":\n            continue  # Immutable ARM bootstrap objects are not x64 handoff state.\n        if item == output:\n')
  result[dest]=text
 return result

def walk(steps):
 for step in steps:
  yield step
  if isinstance(step,dict) and 'when' in step:yield from walk(step['when']['steps'])

def choose(original,derived):
 return 'if [ "<< parameters.stage_index >>" = "1" ]; then\n'+original+'\nelse\n'+derived+'\nfi\n'

def derive(normal):
 cfg=copy.deepcopy(normal)
 steps=cfg['jobs']['brave-android-staged-build']['steps']
 # This source config is already isolated with no reference promotion.
 for step in walk(steps):
  if 'save_cache' in step:
   key=step['save_cache']['key']
   if not (key.startswith(('sandium-brave-handoff-v2-','sandium-brave-apk-complete-v2-')) and '{{ .Branch }}' in key and '{{ .Environment.CIRCLE_WORKFLOW_ID }}' in key):
    raise ValueError('Unexpected writable cache in isolated input: '+key)
  if 'run' in step:
   run=step['run'];name=run['name'];old=run['command']
   if name=='Run lightweight Brave continuation self-test':
    # Original source/policy regression tests remain unchanged. Additional x64
    # generated-script integrity and behavior tests run on every job.
    run['command']=old+'\npython3 experiments/x64-test/verify_generated.py\npython3 -m unittest discover -s experiments/x64-test -p "test*.py"\n'
   elif name=='SANDIUM FULL/FAST MODE - Restore checkpoint with up to 8 parallel workers':
    run['command']=choose(old,replace_paths(arch(old)))
   elif name=='Select Sandium build mode and validate reference':
    # The inline original already separates stage1 from handoff; replace only
    # the explicit handoff invocation. Bootstrap still verifies ARM identity.
    anchor='bash "$ROOT/.circleci/scripts/verify-brave-reference.sh" --handoff'
    assert old.count(anchor)==1
    run['command']=old.replace(anchor,'bash "$ROOT/'+PATHS['.circleci/scripts/verify-brave-reference.sh']+'" --handoff')
   elif 'fixed-reference' in name.lower():
    run['command']=old
   elif name=='Diagnose restored Siso checkpoint and compare prior stage':
    run['command']=choose(old,replace_paths(arch(old)))
   else:run['command']=replace_paths(arch(old)).replace('experiment/native-status-api15',BRANCH)
  if 'store_artifacts' in step:step['store_artifacts']['destination']='sandium-native-x64-test-only/brave-apk'
  for action in ('save_cache','restore_cache'):
   if action not in step:continue
   for field in ('key','keys'):
    if field not in step[action]:continue
    value=step[action][field]
    convert=lambda s:(s.replace('sandium-brave-handoff-v2-','sandium-x64-handoff-v1-').replace('sandium-brave-apk-complete-v2-','sandium-x64-apk-complete-v1-') if '{{ .Branch }}' in s else s)
    step[action][field]=[convert(s) for s in value if not s.startswith('sandium-brave-handoff-v1-')] if isinstance(value,list) else convert(value)
 # Remove translation guard: native x64 must retain normal pinned JNI behavior.
 steps[:]=[s for s in steps if (s.get('run',{}) if isinstance(s,dict) else {}).get('name')!='Apply isolated ARM translation JNI compatibility experiment']
 # Existing reference could contain translated guard; reverse only exact known
 # payload via its existing reset before native preparation (added separately).
 for definition in cfg['workflows']['sandium-full-mode']['jobs']:
  definition['brave-android-staged-build']['filters']={'branches':{'only':BRANCH}}
 # Early fail-closed runtime branch protection (before restore or caches).
 steps.insert(1,{'run':{'name':'Verify isolated native x64 branch','command':'set -euo pipefail\ntest "${CIRCLE_BRANCH:-}" = "'+BRANCH+'"\n'}})
 # Graph exists only after immutable ARM bootstrap verification and x64 preparation.
 # Drop disposable local ARM objects/input archives before x64 compile consumes disk.
 # Verify CPU before build and actual ELF ABI before standard APK export.
 i=next(i for i,s in enumerate(steps) if (s.get('run',{}) if isinstance(s,dict) else {}).get('name')=='Validate build graph and remote-execution settings')
 steps.insert(i,{'run':{'name':'Verify native x64 GN graph','command':'python3 experiments/x64-test/verify_generated.py\npython3 -c \'import sys;sys.path.insert(0,"experiments/x64-test");from contract import validate_graph;validate_graph("brave-work/src/out/android_Release")\'\n'}})
 i=next(i for i,s in enumerate(steps) if (s.get('run',{}) if isinstance(s,dict) else {}).get('name')=='Build bounded Brave Android APK slice')
 steps.insert(i,{'run':{'name':'Reclaim isolated local ARM bootstrap copies','command':'python3 experiments/x64-test/reclaim_bootstrap.py "$CIRCLE_WORKING_DIRECTORY"\n'}})
 i+=1
 steps.insert(i,{'run':{'name':'Check native x64 compile disk headroom','command':"python3 -c 'import shutil; free=shutil.disk_usage(\"brave-work\").free; print(\"X64_DISK_FREE_BYTES=\",free); assert free >= 30*1024**3, \"Native x64 compile requires 30GiB free headroom\"'\n"}})
 i=next(i for i,s in enumerate(steps) if (s.get('run',{}) if isinstance(s,dict) else {}).get('name')=='Export APK status and artifacts')
 steps.insert(i,{'run':{'name':'Validate native x64 APK architecture when produced','command':'set -euo pipefail\nAPK=brave-work/src/out/android_Release/apks/BraveMonox64.apk\nif [ -f "$APK" ]; then python3 experiments/x64-test/contract.py brave-work/src/out/android_Release; fi\n'}})
 return cfg

def generate(root=ROOT):
 source=root/'.circleci/native-status-test/config.yml'
 cfg=derive(yaml.safe_load(source.read_text()))
 outputs=scripts(root)
 outputs[DEST+'/config.yml']=yaml.safe_dump(cfg,sort_keys=False,width=120)
 manifest={'inputs':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in SOURCES+['.circleci/native-status-test/config.yml','experiments/x64-test/build_config.py','experiments/x64-test/reclaim_bootstrap.py']+[str(p.relative_to(root)) for p in sorted((root/'experiments/x64-test/vendor').rglob('*')) if p.is_file() and '__pycache__' not in p.parts]},'outputs':{p:hashlib.sha256(t.encode()).hexdigest() for p,t in outputs.items()}}
 for p,text in outputs.items():
  target=root/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text)
 (root/DEST/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
 return outputs
if __name__=='__main__':generate()
