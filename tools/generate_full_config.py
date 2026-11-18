#!/usr/bin/env python3
"""Render RawS adapter around proven Full phase/cache/serialization protocol."""
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
def run(name,command):return {'run':{'name':name,'command':command,'no_output_timeout':'55m'}}
def phase(p):return run('RawS Full '+p,'python3 -u tools/'+('ci_completion.py' if p in ('completion','halt-complete') else 'ci_full.py')+' '+p)
def cache(prefix,selector):return prefix+'{{ checksum "'+selector+'" }}'
HEAD=cache('raws-full-head-v1-','.checkpoint-state/scope-key')+'-'
BASE=cache('raws-full-base-v1-','.checkpoint-state/base.key')
DELTA=cache('raws-full-delta-v1-','.checkpoint-state/outgoing.key')
def restore(key,name):return {'restore_cache':{'name':name,'keys':[key]}}
def save(key,paths,name):return {'save_cache':{'name':name,'key':key,'paths':paths}}
def common(stage):
 return {'machine':{'image':'ubuntu-2404:current'},'resource_class':'large','retention':{'caches':'15d'},'environment':{'RAWS_STAGE':str(stage),'RAWS_PIPELINE_NUMBER':'<< pipeline.number >>','RAWS_CHECKPOINT_REVIEWED':'true','RAWS_ALLOW_FRESH_SEED':'true','SISO_LIMITS':'local=8,remote=80'}}
def gate():return ['checkout',run('Install CI validation and checkpoint tools','sudo apt-get update -qq && sudo apt-get install -y zstd python3-yaml'),run('Guard isolated RawS checkout','test "$CIRCLE_BRANCH" = "raw-sandium/official158"\n/usr/bin/python3 -m unittest discover -s tests -v'),phase('gate'),run('Ensure verified shard tools','command -v zstd >/dev/null || (sudo apt-get update -qq && sudo apt-get install -y zstd)'),restore(HEAD,'Restore latest accepted RawS receipt only')]
def layers(mode):
 steps=[restore(BASE,'Restore exact RawS base')]
 if mode=='sequential':steps += [phase('restore-base')]
 for i in range(16):
  steps += [run('Clear disposable incoming delta','rm -rf .checkpoint-incoming'),restore(cache('raws-full-delta-v1-',f'.checkpoint-state/slot-{i}.key'),f'Restore exact delta {i}'),phase(('restore-layer' if mode=='sequential' else 'ingest')+f' --slot {i}')]
 if mode=='sequential':steps += [phase('restore-finish')]
 return steps
basepaths=['raw-workspace-checkpoint.manifest.json','raw-workspace-checkpoint.shards']
def publish():return [phase('publish'),save(HEAD+'{{ checksum ".checkpoint-head/receipt.json" }}',['.checkpoint-head'],'Publish receipt only after verified native cache readback')]
def checkpoint():
 return [phase('capture'),save(BASE,basepaths,'Save independent immutable base if new'),save(DELTA,['.checkpoint-incoming'],'Save new immutable delta'),phase('clear-readback'),restore(cache('raws-full-base-v1-','.checkpoint-state/readback-base.key'),'Read back new base only for fresh seed'),restore(cache('raws-full-delta-v1-','.checkpoint-state/readback-delta.key'),'Read back new delta only'),phase('readback')]+publish()
def generate():
 old=yaml.safe_load((ROOT/'.circleci/config.yml').read_text())
 jobs={k:v for k,v in old['jobs'].items() if k in ('raw-preflight','raw-bootstrap')}
 params={k:v for k,v in old['parameters'].items() if k in ('run_raw_preflight','run_raw_bootstrap')}
 params.update(run_raw_full={'type':'boolean','default':False},run_raw_maintenance={'type':'boolean','default':False})
 for n in range(1,6):
  j=common(n);j['steps']=gate()+[phase('prepare')]+layers('sequential')+[
   run('Ensure pinned fresh source or verify restored source','python3 -u tools/ci_source.py'),phase('begin'),
   restore('raws-apt-v1-ubuntu2404-{{ checksum "upstream.lock.json" }}-', 'Restore independent RawS apt downloads'),
   run('Configure independent RawS apt cache','bash tools/prepare_apt_cache.sh'),
   run('Strict remote BuildBuddy ARM64 compile, maximum 25 minutes',f'python3 -u tools/ci_compile.py --stage {n}'),
   save('raws-apt-v1-ubuntu2404-{{ checksum "upstream.lock.json" }}-<< pipeline.id >>-'+str(n),['.raws-apt-cache/archives'],'Save RawS apt downloads'),
   {'store_artifacts':{'path':'artifacts','destination':'raws-arm64'}},
   phase('completion'),save('raws-full-apk-v1-<< pipeline.id >>-'+str(n),['.raws-completion'],'Save verified workflow APK completion'),phase('halt-complete')]+checkpoint()+[phase('final'),{'store_artifacts':{'path':'.checkpoint-state','destination':'raws-checkpoint-evidence'}}]
  # Read small completion markers before downloading any large checkpoint.
  # One restore selects the newest available receipt. Multiple restore steps
  # overwrite the newer completed marker with older incomplete markers.
  keys=['raws-full-apk-v1-<< pipeline.id >>-'+str(earlier) for earlier in range(n-1,0,-1)]
  if keys:j['steps'][1:1]=[{'restore_cache':{'name':'Restore newest prior APK completion','keys':keys}},phase('halt-complete')]
  jobs[f'raws-full-stage-{n}']=j
 m=common(6);m['steps']=gate()+[phase('maintenance-check')]+layers('ingest')+[phase('maintenance-capture'),save(BASE,basepaths,'Save refreshed base under new immutable key'),save(DELTA,['.checkpoint-incoming'],'Save refreshed overlay under new immutable key'),phase('maintenance-clear-saved-local'),restore(BASE,'Read back refreshed base'),restore(DELTA,'Read back refreshed overlay'),phase('maintenance-readback'),phase('maintenance-publish'),save(HEAD+'{{ checksum ".checkpoint-head/receipt.json" }}',['.checkpoint-head'],'Publish refreshed receipt after readback')]+[{'store_artifacts':{'path':'.checkpoint-state/maintenance-report.json','destination':'raws-maintenance'}}]
 jobs['raws-maintenance']=m
 group=[]
 for n in range(1,6):
  item={'filters':{'branches':{'only':'raw-sandium/official158'}}}
  if n>1:item['requires']=[f'raws-full-stage-{n-1}']
  group.append({f'raws-full-stage-{n}':item})
 workflows={k:v for k,v in old['workflows'].items() if k in ('raw-sandium-feasibility','raw-sandium-bootstrap')}
 workflows['RawS full']={'when':'<< pipeline.parameters.run_raw_full >>','jobs':[{'raws-full-chain':{'serial-group':'<< pipeline.project.slug >>/raws-full'}}]}
 workflows['RawS checkpoint maintenance']={'when':'<< pipeline.parameters.run_raw_maintenance >>','jobs':[{'raws-maintenance':{'serial-group':'<< pipeline.project.slug >>/raws-full','filters':{'branches':{'only':'raw-sandium/official158'}}}}]}
 result={'version':2.1,'parameters':params,'jobs':jobs,'job-groups':{'raws-full-chain':{'jobs':group}},'workflows':workflows}
 # Separate opt-in workflow only; normal Full remains fast-exit.
 from generate_final_archive_config import generate_archive
 final=generate_archive(result)
 for section in ('parameters','jobs','workflows','job-groups'):result.setdefault(section,{}).update(final.get(section,{}))
 return result
if __name__=='__main__':(ROOT/'.circleci/config.yml').write_text('# Generated by tools/generate_full_config.py; no Brave cache imports.\n'+yaml.safe_dump(generate(),sort_keys=False,width=150))
