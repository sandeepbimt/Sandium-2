"""Default-off namespaced Full Mode-U; preserves ordinary Full semantics."""
from pathlib import Path
import yaml,copy,hashlib
ROOT=Path(__file__).resolve().parents[2]
def run(name,command):return {'run':{'name':name,'command':'set -euo pipefail\n'+command,'no_output_timeout':'45m'}}
def restore(keys):return {'restore_cache':{'keys':keys}}
def save(key,paths):return {'save_cache':{'key':key,'paths':paths}}
S='{{ checksum ".full-u/scope" }}';WF='{{ .Environment.CIRCLE_WORKFLOW_ID }}';ST='<< parameters.stage >>'
A='full-u-archive-v1-'+S+'-{{ checksum ".full-u/archive-key" }}'
P='full-u-pending-v1-'+S+'-'+WF+'-stage-'+ST
R='full-u-accepted-v1-'+S
W='python3 .circleci/full-u/worker.py ';ARGS=' --root "$CIRCLE_WORKING_DIRECTORY" --stage '+ST

def generate(base):
 credential=next(x for x in base['jobs']['brave-android-staged-build']['steps'] if isinstance(x,dict) and isinstance(x.get('run'),dict) and x['run'].get('name')=='Configure Siso BuildBuddy API-key credential helper')
 common=[run('Record job start','date +%s > /tmp/full-u-job-start'),'checkout',run('Admit exact target and scope',W+'init'+ARGS),run('Install archive tools','if ! command -v zstd >/dev/null; then sudo timeout --signal=TERM --kill-after=30s 180s bash -c \'apt-get update -qq && apt-get install -y zstd\'; fi\nzstd --version'),credential]
 # Previous validator completion is authoritative only after full archive readback.
 early=common[:3]
 early.append({'when':{'condition':{'equal':[1,ST]},'steps':[restore([R+'-{{ checksum ".full-u/expected" }}']),run('Stop explicit completed resume','if '+W+'completed'+ARGS+'; then circleci-agent step halt; fi')]}})
 for n in range(2,6):early.append({'when':{'condition':{'equal':[n,ST]},'steps':[restore([R+'-'+WF+'-stage-'+str(k)+'-' for k in range(n-1,0,-1)]),run('Stop after verified APK plus full archive','if '+W+'completed'+ARGS+'; then circleci-agent step halt; fi')]}})
 common=early+common[3:]
 writer=list(common)
 for n in range(2,6):writer += [{'when':{'condition':{'equal':[n,ST]},'steps':[restore([R+'-'+WF+'-stage-'+str(n-1)+'-'])]}}]
 writer += [run('Validate predecessor receipt',W+'predecessor'+ARGS),restore([A]),run('Execute bounded source or product phase',W+'write'+ARGS),{'store_artifacts':{'path':'.full-u'}},{'store_artifacts':{'path':'brave-apk'}},run('Capture full quiescent workspace',W+'capture'+ARGS),
 run('Start native archive save clock',W+'upload_start'+ARGS),save(A,['full-u-workspace.shards','full-u-workspace.manifest.json']),run('Record actual archive save elapsed',W+'upload_end'+ARGS),
 save('full-u-pending-digest-v1-'+S+'-{{ checksum ".full-u/candidate-id" }}',['.full-u/candidate.json','.full-u/archive-key']),
 save(P+'-{{ checksum ".full-u/candidate-id" }}',['.full-u/candidate.json','.full-u/archive-key']),
 run('Clear local pending reference','rm .full-u/candidate.json'),restore([P+'-{{ checksum ".full-u/candidate-id" }}']),run('Verify pending reference readback',W+'check-pending'+ARGS),{'store_artifacts':{'path':'.full-u'}}]
 validator=list(common)+[{'when':{'condition':{'equal':['none','<< pipeline.parameters.full_u_recover >>']},'steps':[restore([P+'-'])]}},
 {'unless':{'condition':{'equal':['none','<< pipeline.parameters.full_u_recover >>']},'steps':[restore(['full-u-pending-digest-v1-'+S+'-{{ checksum ".full-u/recover" }}'])]}},restore([A]),run('Fresh restore validates source and output',W+'accept'+ARGS),
 save(R+'-{{ checksum ".full-u/accepted-id" }}',['.full-u/receipt.json','.full-u/archive-key']),run('Clear local receipt','rm .full-u/receipt.json'),restore([R+'-{{ checksum ".full-u/accepted-id" }}']),run('Verify accepted reference readback',W+'check-published'+ARGS),
 save(R+'-'+WF+'-stage-'+ST+'-{{ checksum ".full-u/accepted-id" }}',['.full-u/receipt.json','.full-u/archive-key']),{'store_artifacts':{'path':'.full-u'}},run('Report verified completion or preserved hold',W+'finish'+ARGS)]
 def job(steps):return {'parameters':{'stage':{'type':'integer'}},'machine':{'image':'ubuntu-2404:current'},'resource_class':'large','environment':{'FULL_U_RESUME':'<< pipeline.parameters.full_u_resume >>','FULL_U_RECOVER':'<< pipeline.parameters.full_u_recover >>','CIRCLE_PIPELINE_NUMBER':'<< pipeline.number >>'},'steps':steps}
 jobs=[]
 for n in range(1,6):
  for key,suffix in [('full-u-writer',''),('full-u-validator','-verify')]:
   opt={'name':f'Full Mode-U-{n}{suffix}','stage':n,'serial-group':'<< pipeline.project.slug >>/full-u','filters':{'branches':{'only':['work/full-u-1100']}}}
   if suffix:opt['requires']=[f'Full Mode-U-{n}']
   elif n>1:opt['requires']=[f'Full Mode-U-{n-1}-verify']
   jobs.append({key:opt})
 return {'version':2.1,'parameters':{'run_full_u':{'type':'boolean','default':False},'full_u_resume':{'type':'string','default':'none'},'full_u_recover':{'type':'string','default':'none'}},'jobs':{'full-u-writer':job(writer),'full-u-validator':job(validator)},'workflows':{'Full-Mode-U':{'when':{'and':['<< pipeline.parameters.run_full_u >>',{'equal':['none','<< pipeline.parameters.full_u_recover >>']}]},'jobs':jobs},'Full-Mode-U-Recovery':{'when':{'and':['<< pipeline.parameters.run_full_u >>',{'not':{'equal':['none','<< pipeline.parameters.full_u_recover >>']}}]},'jobs':[{'full-u-validator':{'stage':1,'name':'Full Mode-U recovery','serial-group':'<< pipeline.project.slug >>/full-u','filters':{'branches':{'only':['work/full-u-1100']}}}}]}}}
def merge(base):
 addition=generate(base);result=copy.deepcopy(base)
 for section in ('parameters','jobs','workflows'):
  for key,value in addition[section].items():
   if key in result[section] and not (key.startswith('full-u') or key.startswith('full_u') or key.startswith('Full-Mode-U') or key=='run_full_u'):
    raise ValueError('refusing ordinary config collision '+key)
   result[section][key]=value
 # A malformed explicit request must not start both Full and Full-U.
 for name in addition['workflows']:
  conditions=result['workflows'][name]['when']['and']
  conditions.extend([{'not':'<< pipeline.parameters.run_build >>'},{'not':'<< pipeline.parameters.run_maintenance >>'}])
 return result

if __name__=='__main__':
 base=yaml.safe_load((ROOT/'.circleci/config.yml').read_text())
 (ROOT/'.circleci/full-u.yml').write_text(yaml.safe_dump(generate(base),sort_keys=False,width=1000))
 result=yaml.safe_dump(merge(base),sort_keys=False,width=1000)
 (ROOT/'.circleci/config.yml').write_text(result)
 (ROOT/'.circleci/original-full/candidate.yml').write_text(result)
 (ROOT/'.circleci/original-full/config.sha256').write_text(hashlib.sha256(result.encode()).hexdigest()+'\n')
