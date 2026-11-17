#!/usr/bin/env python3
"""Stage typed diagnostic transport/producers/UI as one validated source transaction."""
from pathlib import Path
import argparse,importlib.util,tempfile,os,re,json
ROOT=Path(__file__).resolve().parents[2]
def load(relative):
 path=ROOT/relative;spec=importlib.util.spec_from_file_location(path.stem.replace('-','_')+str(hash(relative)),path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
BASE='experiments/navigation-diagnostics/'
bridge=load(BASE+'native-bridge/apply.py')
ui=load('.circleci/features/navigation-diagnostics/ui/apply-ui.py')
producers=[load(BASE+'apply-'+name+'.py') for name in ('lifecycle','capture','menu','redirect','dark-policy','popup','document-paint','typography-policy')]
transition=load('experiments/native-transition-diagnostics/apply.py')
metrics=load(BASE+'apply-renderer-metrics.py')
ad=load(BASE+'ad/apply.py')
ad_load=load(BASE+'ad/load_snapshot.py')
ad_domain=load(BASE+'ad/domain.py')
ad_baseline=load(BASE+'ad/baseline.py')
AD_TRANSFORMS={ad.PATH:ad.transform,ad_load.HEADER:ad_load.header,ad_load.SOURCE:ad_load.source,ad_domain.HEADER:ad_domain.header,ad_domain.SOURCE:ad_domain.source,ad_baseline.JAVA:ad_baseline.java,ad_baseline.CPP:ad_baseline.cpp}
RECORDER=ROOT/BASE/'java'/bridge.RECORDER
INPUTS=set(bridge.TRANSFORMS)|{p.PATH for p in producers}|{transition.BLUR,transition.BACK}|{'brave/'+ui.MAIN,'brave/android/brave_java_sources.gni'}
INPUTS.update('brave/'+p for p in AD_TRANSFORMS)
INPUTS.update((metrics.OBSERVER,metrics.TRACKER))
def compose(src):
 if json.loads((ROOT/'experiments/native-navigation/profile.json').read_text()).get('enabled'):
  raise ValueError('Diagnostic producers target Sandium navigation, not alternate native experiment')
 with tempfile.TemporaryDirectory() as d:
  stage=Path(d)
  for rel in INPUTS:
   p=stage/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text((src/rel).read_text())
  def write(outputs):
   for p,t in outputs.items():p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t)
  bridge_outputs=bridge.plan(stage,RECORDER)
  revision=os.environ.get('CIRCLE_SHA1','unavailable')
  if revision!='unavailable' and not re.fullmatch('[0-9a-fA-F]{40}',revision):raise ValueError('Invalid diagnostic build revision')
  for p,t in list(bridge_outputs.items()):
   bridge_outputs[p]=t.replace('__SANDIUM_DIAGNOSTIC_BUILD_REVISION__',revision)
  write(bridge_outputs)
  for m in producers:
   p=stage/m.PATH;p.write_text(m.transform(p.read_text()))
  write(transition.plan(stage))
  for rel,transform in ((metrics.OBSERVER,metrics.observer),(metrics.TRACKER,metrics.tracker)):
   p=stage/rel;p.write_text(transform(p.read_text()))
  for rel,transform in AD_TRANSFORMS.items():
   p=stage/'brave'/rel;p.write_text(transform(p.read_text()))
  write(ui.outputs(stage,ROOT/'.circleci/features/navigation-diagnostics/ui'))
  return {src/p.relative_to(stage):p.read_text() for p in stage.rglob('*') if p.is_file()}
def reset_native_probes(src):
 outputs={}
 for rel in (transition.BLUR,transition.BACK):
  p=src/rel
  if not p.exists():continue
  text=p.read_text()
  for name,old,new in reversed(transition.CHANGES):
   if name==rel and new in text:
    if text.count(new)!=1:raise ValueError('Duplicate native diagnostic block')
    text=text.replace(new,old,1)
  if 'SANDIUM_TRANSITION_RING_V1' in text:raise ValueError('Unrecognized native diagnostic block')
  outputs[p]=text
 return outputs
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--verify-only',action='store_true');p.add_argument('--reset-native-probes',action='store_true');a=p.parse_args()
 out=reset_native_probes(a.source) if a.reset_native_probes else compose(a.source)
 if a.verify_only:
  for path,text in out.items():
   if not path.exists() or path.read_text()!=text:raise ValueError('Diagnostic consumer drift: '+str(path))
 else:
  for path,text in out.items():path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
 print('SANDIUM_NAVIGATION_DIAGNOSTICS_SOURCE=PASS (not runtime completeness proof)')
