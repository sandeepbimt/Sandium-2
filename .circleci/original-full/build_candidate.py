import yaml,copy,json,pathlib
root=pathlib.Path(__file__).resolve().parents[2]
a=yaml.safe_load((root/'.circleci/original-full/fc220e7f.config.yml').read_text());product=json.loads((root/'.circleci/original-full/product-steps.json').read_text())
j=copy.deepcopy(a['jobs']['brave-android-staged-build']); old=j['steps'];out=[];mapping=[]
for i,step in enumerate(old):
 if i==8:
  step=copy.deepcopy(step);step['when']['steps']=[
   {'restore_cache':{'name':'Read accepted fixed-reference metadata only','keys':['fixed-sandium-reference-v1-backpreview01-']}},
   {'restore_cache':{'name':'Read legacy accepted receipt only for initial fixed-base metadata bootstrap','keys':['sandium-experimental-head-v1-fSJgSbKhoW8y5Z2yXRIK+o_g6oruZ_+JUYmKGb3vgt4=-']}},
   {'run':{'name':'Select exact fixed base without consuming legacy increments','command':'python3 .circleci/original-full/fixed_reference.py select --root "$CIRCLE_WORKING_DIRECTORY" --legacy-script .circleci/scripts/sandium-checkpoint-shards.py --legacy-receipt "$CIRCLE_WORKING_DIRECTORY/.checkpoint-head/receipt.json"'}},
   {'restore_cache':{'name':'Restore only exact selected fixed complete reference','keys':['sandium-bridge-base-v1-{{ checksum ".fixed-reference/cache.key" }}']}},
   {'run':{'name':'Verify fixed reference manifest identity and all eight shard hashes','command':'python3 .circleci/original-full/fixed_reference.py preverify --root "$CIRCLE_WORKING_DIRECTORY" --legacy-script .circleci/scripts/sandium-checkpoint-shards.py'}}]
  kind='approved fixed-reference metadata and exact cache selection'
 elif i==21:
  step=copy.deepcopy(step)
  cmd=step['run']['command']
  needle='  bash "$ROOT/.circleci/scripts/verify-brave-reference.sh"'
  # FAST branch stays untouched; only FULL verification chooses explicit handoff.
  pos=cmd.index('elif [ "$MODE" = "full" ]; then')
  before,after=cmd[:pos],cmd[pos:]
  assert after.count(needle)==1
  after=after.replace(needle,'''  if [ "<< parameters.stage_index >>" -eq 1 ]; then
    bash "$ROOT/.circleci/scripts/verify-brave-reference.sh"
  else
    bash "$ROOT/.circleci/scripts/verify-brave-reference.sh" --handoff "<< parameters.stage_index >>" "$CIRCLE_WORKFLOW_ID" "$CIRCLE_SHA1"
  fi''')
  step['run']['command']=before+after;kind='approved incomplete handoff validation'
 elif i==39:
  step=copy.deepcopy(step);run=step['when']['steps'][0]['run'];needle='  echo "STAGE=<< parameters.stage_index >>"'
  assert run['command'].count(needle)==1
  run['command']=run['command'].replace(needle,needle+'\n  echo "WORKFLOW_ID=$CIRCLE_WORKFLOW_ID"')
  assert run['command'].count('echo "REFERENCE_SOURCE_REVISION={{ .Revision }}"')==1
  run['command']=run['command'].replace('echo "REFERENCE_SOURCE_REVISION={{ .Revision }}"','echo "REFERENCE_SOURCE_REVISION=$CIRCLE_SHA1"')
  kind='approved hashed handoff workflow binding'
 elif i in [23,24,25,26,27]:
  if i==23:
   for st in product['overlays']:out.append(copy.deepcopy(st));mapping.append({'baseline_index':None,'exception':'current Sandium product overlays','name':st['run']['name']})
  continue
 elif i==34:
  step=copy.deepcopy(step)
  from failfast import transform
  step['run']['command']=transform(step['run']['command'])
  kind='user-approved fail-fast genuine build failures; attested budget handoff only'
 elif i==35:
  step=copy.deepcopy(product['export']);step['run']['when']='on_success';kind='current APK validation; user-approved on-success only'
 elif isinstance(step,dict) and ('run' in step or 'save_cache' in step) and next(iter(step.values())).get('when')=='always':
  step=copy.deepcopy(step);next(iter(step.values()))['when']='on_success'
  kind='user-approved no marker save after failed build'

 else:kind='byte-identical task object'
 mapping.append({'baseline_index':i,'candidate_index':len(out),'status':kind});out.append(step)
 if i==20:
  out.append({'when':{'condition':{'equal':[1,'<< parameters.stage_index >>']},'steps':[
   {'run':{'name':'Verify restored fixed-reference source pins and accept bootstrap metadata','command':'python3 .circleci/original-full/fixed_reference.py postrestore --root "$CIRCLE_WORKING_DIRECTORY" --legacy-script .circleci/scripts/sandium-checkpoint-shards.py'}},
   {'save_cache':{'name':'Save small fixed-reference identity only; identical metadata is immutable','key':'fixed-sandium-reference-v1-backpreview01-{{ checksum ".fixed-reference/accepted.json" }}','paths':['.fixed-reference/accepted.json']}}]}})
  mapping.append({'baseline_index':None,'exception':'fixed-reference postrestore source identity and metadata only'})
# Existing overlay scripts require same stage environment, not altered commands.
j['environment']={'SANDIUM_STAGE':'<< parameters.stage_index >>','SISO_LIMITS':'local=8,remote=80'}
j['steps']=out
j['retention']={'caches':'15d'}
w=copy.deepcopy(a['workflows']['sandium-full-mode']);w['when']='<< pipeline.parameters.run_build >>';w['jobs']=w['jobs'][:5]
for job in w['jobs']:next(iter(job.values()))['filters']={'branches':{'only':'experiment/sandium-back-transition'}}
result={'version':2.1,'parameters':{'run_build':{'type':'boolean','default':False},'sandium_build_mode':{'type':'enum','enum':['full'],'default':'full'},'run_maintenance':{'type':'boolean','default':False}},'jobs':{'brave-android-staged-build':j},'workflows':{'sandium-full-mode':w}}
def run(name,phase,extra=''):
 return {'run':{'name':name,'command':'python3 .circleci/original-full/fixed_reference.py '+phase+' --root "$CIRCLE_WORKING_DIRECTORY" --legacy-script .circleci/scripts/sandium-checkpoint-shards.py'+extra}}
maintenance={'machine':{'image':'ubuntu-2404:current'},'resource_class':'large','retention':{'caches':'15d'},'steps':[
 'checkout',
 {'restore_cache':{'name':'Read accepted fixed-reference metadata','keys':['fixed-sandium-reference-v1-backpreview01-']}},
 run('Select accepted fixed reference; no legacy fallback in maintenance','select'),
 {'run':{'name':'Stop before large download unless saved reference is within expiry margin','command':'set -euo pipefail\npython3 .circleci/original-full/fixed_reference.py renewal-check --root "$CIRCLE_WORKING_DIRECTORY" --legacy-script .circleci/scripts/sandium-checkpoint-shards.py\nif [ "$(cat .fixed-reference/renewal-due)" = no ]; then circleci-agent step halt; fi'}},
 {'restore_cache':{'name':'Restore exact unchanged fixed reference for expiry-only renewal','keys':['sandium-bridge-base-v1-{{ checksum ".fixed-reference/cache.key" }}']}},
 run('Verify all fixed-reference archive identities before copying','preverify'),
 run('Prepare new immutable key for identical reference bytes','renewal-prepare',' --new-logical-key "fixed-reference-backpreview01-${CIRCLE_WORKFLOW_ID}-${CIRCLE_BUILD_NUM}"'),
 {'save_cache':{'name':'Copy identical compressed reference only when expiry is near','key':'sandium-bridge-base-v1-{{ checksum ".fixed-reference/cache.key" }}','paths':['brave-workspace-checkpoint.shards','brave-workspace-checkpoint.manifest.json']}},
 run('Clear only verified local transport files before remote readback','renewal-clear'),
 {'restore_cache':{'name':'Read back exact newly saved immutable reference','keys':['sandium-bridge-base-v1-{{ checksum ".fixed-reference/cache.key" }}']}},
 run('Verify remote readback before accepting renewed reference metadata','renewal-accept'),
 {'save_cache':{'name':'Publish renewed fixed identity only after readback','key':'fixed-sandium-reference-v1-backpreview01-{{ checksum ".fixed-reference/accepted.json" }}','paths':['.fixed-reference/accepted.json']}}
]}
result['jobs']['renew-fixed-reference']=maintenance
result['workflows']['sandium-full-mode']['when']={'and':['<< pipeline.parameters.run_build >>',{'not':'<< pipeline.parameters.run_maintenance >>'}]}
result['workflows']['fixed-reference-maintenance']={'when':{'and':['<< pipeline.parameters.run_maintenance >>',{'not':'<< pipeline.parameters.run_build >>'}]},'jobs':[{'renew-fixed-reference':{'filters':{'branches':{'only':'experiment/sandium-back-transition'}}}}]}
(root/'.circleci/original-full/candidate.yml').write_text(yaml.safe_dump(result,sort_keys=False,width=120))
(root/'.circleci/original-full/step-provenance.json').write_text(json.dumps(mapping,indent=2)+'\n')

import hashlib
(root/'.circleci/original-full/config.sha256').write_text(hashlib.sha256((root/'.circleci/original-full/candidate.yml').read_bytes()).hexdigest()+'\n')
