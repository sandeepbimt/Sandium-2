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
def add_restore_only(result):
 # The existing Full workflow and stage 1 job own this policy. Normal Full
 # and the separate maintenance/final archive templates are left intact.
 from ci_restore_only import BASE_CACHE, RECEIPT_CACHE
 key='raw_full_restore_only'
 condition='<< pipeline.parameters.'+key+' >>'
 result['parameters'][key]={'type':'boolean','default':False}
 j=result['jobs']['raws-full-stage-1']
 original=j['steps']
 startup=gate()
 def policy_phase(name):
  return run('RawS Full restore-only '+name,
             'RAWS_DISTINCT_TEST_IDENTITY=true RAWS_ALLOW_FRESH_SEED=false '
             'python3 -u tools/ci_restore_only.py '+name)
 source_steps=[
  restore(RECEIPT_CACHE,'Restore exact verified RawS #1396 receipt'),
  policy_phase('select'),
  restore(BASE_CACHE,'Restore exact verified RawS #1396 final archive'),
  phase('restore-base'),phase('restore-finish')]
 # No source bootstrap, capture inventory, checkpoint/completion save, or
 # fallback cache. A matching completed archive is input, never output proof.
 artifact_steps=[step for step in original if isinstance(step,dict)
                 and 'store_artifacts' in step and step['store_artifacts']['destination']=='raws-arm64']
 j['steps']=startup[:-1]+[
  {'unless':{'condition':condition,'steps':original[len(startup)-1:]}},
  {'when':{'condition':condition,'steps':source_steps+[policy_phase('compile'),policy_phase('completed')]+artifact_steps}}]
 for item in result['job-groups']['raws-full-chain']['jobs'][1:]:
  invocation=next(iter(item.values()))
  invocation['filters']='pipeline.git.branch == "raw-sandium/official158" and not pipeline.parameters.'+key

def add_regular_raws(result):
 # One regular, restore-only RawS Full route. Keep the existing restricted
 # signer name and context; compile never gets signing material. The codec
 # choice changes build settings, not the workflow or access policy.
 from ci_restore_only import BASE_CACHE, RECEIPT_CACHE
 key='run_raw_full'
 probe_key='run_raw_signing_probe'
 codec_key='raws_h264_aac'
 selector='<< pipeline.parameters.'+key+' >>'
 probe_selector='<< pipeline.parameters.'+probe_key+' >>'
 codec_selector='<< pipeline.parameters.'+codec_key+' >>'
 result['parameters'][probe_key]={'type':'boolean','default':False}
 result['parameters'][codec_key]={'type':'boolean','default':False}
 branch='raw-sandium/official158'
 branch_filter={'branches':{'only':branch}}
 guard='set -euo pipefail\ntest "$CIRCLE_BRANCH" = "'+branch+'"\ntest "$(git rev-parse HEAD)" = "$CIRCLE_SHA1"'
 # Check route requests before tools, receipt lookup, or archive restore.
 # Unknown old CircleCI parameters are not declared, so the API rejects them.
 other_routes=[other for other in result['parameters'] if other not in (key, codec_key)]
 guards=[
  f'test "{selector}" = true || {{ echo "Request run_raw_full=true for a RawS build"; exit 2; }}',
  *[f'test "<< pipeline.parameters.{other} >>" = false || '
    f'{{ echo "RawS full cannot combine with {other}"; exit 2; }}' for other in other_routes],
 ]
 no_key=r"""set +x
test -z "${RAWS_TEST_KEYSTORE_B64+x}"
test -z "${RAWS_KEYSTORE_PASSWORD+x}"
test -z "${RAWS_KEY_PASSWORD+x}"
"""
 def policy_phase(name):
  return run('RawS restore-only '+name,
             'RAWS_CODEC_TRIAL='+codec_selector+' RAWS_UNSIGNED_TEST_APK=true '
             'RAWS_DISTINCT_TEST_IDENTITY=true RAWS_ALLOW_FRESH_SEED=false '
             'python3 -u tools/ci_restore_only.py '+name)
 compile_job=common(1)
 compile_job['environment'].update(RAWS_ALLOW_FRESH_SEED='false')
 compile_job['steps']=['checkout',
  run('Verify exact checkout, request, and no signing material',guard+'\n'+'\n'.join(guards)+'\n'+no_key),
  # zstd was installed by this same gate; do not run the legacy fallback again.
  *gate()[1:-2],
  restore(RECEIPT_CACHE,'Restore exact verified RawS #1396 receipt'),
  policy_phase('select'),
  restore(BASE_CACHE,'Restore exact verified RawS #1396 final archive'),
  phase('restore-base'),phase('restore-finish'),
  policy_phase('compile'),policy_phase('completed'),
  {'persist_to_workspace':{'root':'.raws-signing-input','paths':['candidate.apk','receipt.json']}},
 ]
 install_sdk=r"""set +x
set -euo pipefail
umask 077
expected=5d9ac77fb6ff43d9da518a337b4fcf8f9097113df531d99ccefe80ef7ce8250b
sdk=/tmp/raws-signer-sdk
mkdir -m 700 "$sdk"
archive=$(mktemp /tmp/raws-build-tools.XXXXXX)
trap 'rm -f "$archive"' EXIT
curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' \
  --tlsv1.2 --retry 2 --connect-timeout 15 --max-time 180 \
  --output "$archive" https://dl.google.com/android/repository/build-tools_r36_linux.zip
test "$(wc -c < "$archive")" -eq 63737259
printf '%s  %s\n' "$expected" "$archive" | sha256sum --check --status
unzip -q "$archive" -d "$sdk"
test -x "$sdk/android-16/apksigner"
test -x "$sdk/android-16/zipalign"
test -x "$sdk/android-16/aapt2"
grep -Eq '^[[:space:]]*Pkg.Revision[[:space:]]*=[[:space:]]*36\.0\.0[[:space:]]*$' "$sdk/android-16/source.properties"
printf 'RAWS_SIGNING_SDK_VERIFIED sha256=%s prefix=android-16 revision=36.0.0\n' "$expected"
"""
 sign_job={'machine':{'image':'ubuntu-2404:current'},'resource_class':'medium','steps':[
  'checkout',run('Verify exact signer source commit',guard),
  run('Install hash-pinned official Android Build Tools 36.0.0',install_sdk),
  {'attach_workspace':{'at':'.raws-signing-input'}},
  run('Verify inputs, sign, and admit the final directory atomically',r"""set +x
set -euo pipefail
umask 077
test ! -e .raws-signing-verified
test ! -L .raws-signing-verified
test ! -e artifacts/raws-signed
test ! -L artifacts/raws-signed
test ! -L artifacts
RAWS_CODEC_TRIAL=CODEC_SELECTOR RAWS_UNSIGNED_TEST_APK=true python3 -u tools/ci_sign_raws_test.py --input .raws-signing-input \
  --sdk /tmp/raws-signer-sdk/android-16 --output-dir .raws-signing-verified
mkdir -p artifacts
mv -T .raws-signing-verified artifacts/raws-signed
""".replace('CODEC_SELECTOR',codec_selector)),
  {'store_artifacts':{'path':'artifacts/raws-signed','destination':'raws-signed'}},
 ]}
 probe_job={'machine':{'image':'ubuntu-2404:current'},'resource_class':'medium','steps':[
  run('Verify only restricted nonsecret signing canary',
      'set +x\nset -euo pipefail\ntest "$CIRCLE_BRANCH" = "'+branch+'"\n'+no_key+
      'test "${RAWS_SIGNING_CONTEXT_CANARY:-}" = "raws-test-signing-probe-v1"'),
  run('Verify the official signer tools with no credentials present',install_sdk),
 ]}
 result['jobs'].update({'raws-test-identity-compile':compile_job,'raws-test-identity-sign':sign_job,
                        'raws-test-signing-context-probe':probe_job})
 result['job-groups']['raws-signed-test-chain']={'jobs':[
  {'raws-test-identity-compile':{'filters':branch_filter}},
  {'raws-test-identity-sign':{'requires':['raws-test-identity-compile'],
                            'filters':{'branches':{'only':branch}},'context':'RawS-Test-Signing'}},
 ]}
 # The normal build selector and probe are exclusive, and turning on the
 # codec setting alone authorizes no route. Do not fall back to an archive or
 # preflight if someone combines the regular route with other trigger flags.
 for name, workflow in result['workflows'].items():
  if name != 'RawS full':
   workflow['when']={'and':[workflow['when'],{'not':selector},
                           {'not':probe_selector},{'not':codec_selector}]}
 def exclusive(selected):
  return {'and':['<< pipeline.parameters.'+selected+' >>',
                 {'equal':[branch,'<< pipeline.git.branch >>']},
                 *({'not':'<< pipeline.parameters.'+other+' >>'}
                   for other in result['parameters'] if other!=selected)]}
 result['workflows']['RawS full']={
  # Route ambiguous requests through the same early refusing compile guard;
  # never silently run an alternate archive/preflight or a second codec workflow.
  'when':{'and':[{'or':[selector,codec_selector]},
                 {'equal':[branch,'<< pipeline.git.branch >>']}]},
  'jobs':[{'raws-signed-test-chain':{'serial-group':'<< pipeline.project.slug >>/raws-full'}}],
 }
 result['workflows']['RawS signing context probe']={
  'when':exclusive(probe_key),
  'jobs':[{'raws-test-signing-context-probe':{'filters':branch_filter,'context':'RawS-Test-Signing'}}],
 }

def generate(*, restore_only=True, signed_test=True):
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
 workflows['raw-sandium-feasibility']['when']='<< pipeline.parameters.run_raw_preflight >>'
 workflows['raw-sandium-bootstrap']['when']='<< pipeline.parameters.run_raw_bootstrap >>'
 workflows['RawS full']={'when':'<< pipeline.parameters.run_raw_full >>','jobs':[{'raws-full-chain':{'serial-group':'<< pipeline.project.slug >>/raws-full'}}]}
 workflows['RawS checkpoint maintenance']={'when':'<< pipeline.parameters.run_raw_maintenance >>','jobs':[{'raws-maintenance':{'serial-group':'<< pipeline.project.slug >>/raws-full','filters':{'branches':{'only':'raw-sandium/official158'}}}}]}
 result={'version':2.1,'parameters':params,'jobs':jobs,'job-groups':{'raws-full-chain':{'jobs':group}},'workflows':workflows}
 # Separate opt-in workflow only; normal Full remains fast-exit.
 from generate_final_archive_config import generate_archive
 final=generate_archive(result)
 for section in ('parameters','jobs','workflows','job-groups'):result.setdefault(section,{}).update(final.get(section,{}))
 if restore_only:
  if signed_test:
   add_regular_raws(result)
  else:
   # Historical template for protocol regression checks only; the checked-in
   # config always uses the regular fail-fast signed route above.
   add_restore_only(result)
 return result
if __name__=='__main__':(ROOT/'.circleci/config.yml').write_text('# Generated by tools/generate_full_config.py; no Brave cache imports.\n'+yaml.safe_dump(generate(),sort_keys=False,width=150))
