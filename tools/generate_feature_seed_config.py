#!/usr/bin/env python3
"""Held opt-in native UI pipeline: exact baseline seed, fresh proof, five slices.

Does not modify or activate normal Full. Runtime admission/manifest and CircleCI
service validation must be reviewed before this standalone configuration is used.
"""
import copy,json
from pathlib import Path
import yaml
from generate_full_config import ROOT, common, run as _run, restore, save, layers, basepaths
def run(name,command):
    # CircleCI processes template delimiters before handing the command to Bash.
    # Escape only our literal shell heredoc; genuine pipeline expressions remain.
    return _run(name,command.replace("<<'PYCODE'", "\\<<'PYCODE'"))

BRANCH='raw-sandium/native-ui158'
PARAM='run_raw_native_features'
PREPARED='raws-native-inputs-v1-{{ .Environment.CIRCLE_WORKFLOW_ID }}'
VERIFIED='raws-native-inputs-verified-v1-{{ .Environment.CIRCLE_WORKFLOW_ID }}'
COMPLETED='raws-native-completed-v1-{{ .Environment.CIRCLE_WORKFLOW_ID }}'
FINAL='raws-native-final-v1-{{ .Environment.CIRCLE_WORKFLOW_ID }}'
RECOVERY='raws-native-recovery-proof-v1-{{ .Environment.CIRCLE_WORKFLOW_ID }}'
DELTA='raws-final-delta-v1-{{ checksum ".checkpoint-state/outgoing.key" }}'
FULL_BASE='raws-full-base-v1-{{ checksum ".checkpoint-state/base.key" }}'

def phase(p):return run('Native feature '+p,'python3 -u tools/ci_feature_seed.py '+p)
def final(p):return run('Native full archive '+p,'python3 -u tools/ci_final_archive.py '+p)
def full(p):return run('Native checkpoint '+p,'python3 -u tools/ci_full.py '+p)
def clock(seed=False):
    # The seed adoption requires no .checkpoint-state until the old proof moves.
    target='.feature-seed-clock.json' if seed else '.checkpoint-state/job-start.json'
    return run('Start original one-hour job clock',f'''python3 - <<'PYCODE'
import json,os,time
from pathlib import Path
p=Path({target!r})
if p.exists():raise SystemExit('Job clock already exists')
p.parent.mkdir(parents=True,exist_ok=True)
epoch=time.time();p.write_text(json.dumps({{'epoch':epoch}})+'\\n')
with open(os.environ['BASH_ENV'],'a') as f:f.write('export RAWS_FEATURE_JOB_STARTED_EPOCH='+str(epoch)+'\\n')
PYCODE''')

def guard():
    return run('Review explicit native feature scope and tests',f'''test "$CIRCLE_BRANCH" = "{BRANCH}"
python3 - <<'PYCODE'
import sys
sys.path.insert(0,'tools')
from native_features import load_manifest
from ci_compile import fingerprint
from pathlib import Path
if load_manifest()!=('menu','toolbar'):raise SystemExit('Both reviewed UI features must be explicitly enabled')
if Path('ci/cache-identity.txt').read_text().strip()!=fingerprint():raise SystemExit('Recipe identity mismatch')
PYCODE
/usr/bin/python3 -m unittest discover -s tests -v''')

def job(stage=1,seed=False):
    value=common(stage)
    value['environment'].update(RAWS_NATIVE_FEATURE_BUILD='true',RAWS_ALLOW_FRESH_SEED='false')
    if seed:value['environment'].update(RAWS_NATIVE_FEATURE_SEED='true')
    value['steps']=['checkout',clock(seed),run('Verify native tools; install missing capabilities only','bash tools/prepare_native_tools.sh'),guard()]
    return value

def artifact(path,destination):return {'store_artifacts':{'path':path,'destination':destination}}
def progress(n):return 'raws-native-progress-v1-{{ .Environment.CIRCLE_WORKFLOW_ID }}-'+str(n)
def completion(n):return 'raws-native-apk-v1-{{ .Environment.CIRCLE_WORKFLOW_ID }}-'+str(n)

def exact_layers():
    result=copy.deepcopy(layers('sequential'))
    # These increments are written by the final-archive helper, not normal Full.
    for step in result:
        if isinstance(step,dict) and 'restore_cache' in step:
            old=step['restore_cache']['keys'][0]
            if old.startswith('raws-full-delta-v1-'):
                step['restore_cache']['keys']=[old.replace('raws-full-delta-v1-','raws-final-delta-v1-')]
    return result

def generate():
    plan=json.loads((ROOT/'docs/evidence/baseline1396/restore-plan.json').read_text())
    seed=job(seed=True)
    seed['environment']['RAWS_ALLOW_FRESH_SEED']='true'  # New full base only, not a fake fresh marker.
    seed['steps'] += [
        run('Prepare isolated unchanged baseline tools','python3 -u tools/feature_seed_transport.py prepare --repository "$PWD" --session .feature-seed-transport --job-start-epoch "$RAWS_FEATURE_JOB_STARTED_EPOCH"'),
        restore(plan['receipt_cache_key'],'Restore exact frozen #1396 receipt'),
        run('Relocate downloaded receipt outside feature state',"""python3 - <<'PYCODE'
from pathlib import Path
incoming=Path('.feature-seed-incoming');old=Path('.raws-final-archive')
if incoming.exists() or not old.is_dir() or old.is_symlink():raise SystemExit('Unexpected baseline receipt location')
incoming.mkdir();old.rename(incoming/'receipt')
PYCODE"""),
        run('Select exact old receipt in unchanged baseline process','python3 -u tools/feature_seed_transport.py select --session .feature-seed-transport --receipt .feature-seed-incoming/receipt/receipt.json'),
        restore(plan['archive_cache_key'],'Restore exact #1396 full base, no prefix fallback'),
        run('Relocate native cache inputs without copying archive',"""python3 - <<'PYCODE'
from pathlib import Path
for name in ('raw-workspace-checkpoint.manifest.json','raw-workspace-checkpoint.shards'):
    p=Path(name);dest=Path('.feature-seed-incoming')/name
    if p.is_symlink() or not p.exists() or dest.exists():raise SystemExit('Unexpected baseline archive input')
    if p.stat().st_dev!=dest.parent.stat().st_dev:raise SystemExit('Cross-filesystem archive copy forbidden')
    p.rename(dest)
PYCODE"""),
        run('Verify and restore under exact old identity','python3 -u tools/feature_seed_transport.py restore --session .feature-seed-transport --incoming .feature-seed-incoming'),
        run('Adopt only restored workspace and proof','python3 -u tools/feature_seed_transport.py adopt --session .feature-seed-transport --feature-root "$PWD"'),
        phase('transition --baseline-checkout .feature-seed-transport/baseline'),
        phase('capture'),
        save('raws-full-base-v1-{{ checksum ".feature-seed-checkpoint/base.key" }}',basepaths,'Save NEW full feature-input base'),
        phase('clear-readback'),
        restore('raws-full-base-v1-{{ checksum ".feature-seed-checkpoint/base.key" }}','Read back exact new feature-input base'),
        phase('accept-readback'),
        save(PREPARED,['.feature-seed-checkpoint'],'Publish independent prepared receipt, not a normal head'),
        artifact('artifacts','native-seed-evidence'),artifact('.feature-seed-checkpoint','native-seed-checkpoint')]
    validator=job(seed=True)
    validator['steps'] += [restore(PREPARED,'Restore exact same-pipeline prepared receipt'),phase('select-prepared'),
        restore(FULL_BASE,'Restore exact new recipe base'),full('restore-base'),full('restore-finish'),
        phase('verify-prepared'),phase('promote-prepared'),
        save(VERIFIED,['.checkpoint-head'],'Publish fresh-validated new recipe head'),artifact('artifacts','native-input-validation')]
    jobs={'raws-native-seed':seed,'raws-native-validate-inputs':validator}
    for n in range(1,6):
        compile=job(n)
        compile['environment']['RAWS_FINAL_ARCHIVE']='true'
        if n>1:
            # Read newest preceding completion once; later cache restores must not overwrite it.
            compile['steps'][2:2]=[{'restore_cache':{'name':'Restore latest prior verified APK completion','keys':[completion(i) for i in range(n-1,0,-1)]}},run('Skip only a previously archived same-workflow APK','python3 -u tools/ci_completion.py halt-complete')]
        compile['steps'] += [full('gate')]
        compile['steps'] += [restore(VERIFIED,'Restore exact fresh-validated feature head')] if n==1 else [restore(progress(n-1),'Restore exact preceding feature increment')]
        compile['steps'] += [final('prepare')]+exact_layers()+[
            run('Strict source verification','python3 -u tools/ci_source.py'),full('begin'),
            restore('raws-apt-v1-ubuntu2404-{{ checksum "upstream.lock.json" }}-','Restore independent apt download cache'),
            run('Configure apt download cache','bash tools/prepare_apt_cache.sh'),
            run('Compile within remaining one-hour budget, maximum 25 minutes',f'python3 -u tools/ci_compile.py --stage {n}'),
            artifact('artifacts','native-apk-and-build'),final('progress-capture'),
            save(DELTA,['.checkpoint-incoming'],'Save exact feature compilation increment'),final('progress-clear'),
            restore(DELTA,'Read back exact feature compilation increment'),final('progress-publish'),
            save(progress(n),['.raws-final-progress'],'Publish exact archived feature continuation'),
            run('Bind APK completion only after archive readback','python3 -u tools/ci_completion.py completion'),
            save(completion(n),['.raws-completion'],'Publish workflow completion after reusable output is saved'),
            artifact('.raws-final-progress','native-compile-continuation')]
        # A completed slice publishes the immutable handoff; incomplete slices continue.
        compile['steps'] += [run('Require APK before completed handoff; otherwise continue next slice',
            "python3 -u tools/ci_feature_seed.py completed-handoff"),
            save(COMPLETED,['.raws-final-progress'],'Publish completed same-workflow handoff')]
        jobs['raws-native-compile-'+str(n)]=compile
    pack=job()
    pack['environment'].update(RAWS_FINAL_ARCHIVE='true',RAWS_FINAL_PACK_ONLY='true')
    pack['steps'] += [full('gate'),restore(COMPLETED,'Restore completed feature compilation handoff'),final('prepare-archive')]+exact_layers()+[
        final('capture'),save('raws-final-base-v1-{{ checksum ".raws-final-archive/base.key" }}',basepaths,'Save complete APK-producing full archive'),
        final('clear'),restore('raws-final-base-v1-{{ checksum ".raws-final-archive/base.key" }}','Read back exact complete full archive'),final('verify-publish'),
        save(FINAL,['.raws-final-archive'],'Publish exact full archive for fresh probe'),
        save('raws-final-receipt-v1-{{ checksum ".raws-final-archive/receipt.json" }}',['.raws-final-archive'],'Publish immutable full archive receipt'),
        artifact('.raws-final-archive','native-final-archive-evidence')]
    jobs['raws-native-pack']=pack
    probe=job()
    probe['environment'].update(RAWS_FINAL_ARCHIVE='true',RAWS_FINAL_PACK_ONLY='true')
    probe['steps'] += [full('gate'),restore(FINAL,'Restore exact completed full archive receipt'),final('prepare-probe'),
        restore('raws-final-base-v1-{{ checksum ".checkpoint-state/base.key" }}','Restore exact complete full base'),full('restore-base'),full('restore-finish'),
        run('Fresh-worker signed APK and remote-enabled reuse proof','python3 -u tools/ci_restore_probe.py'),
        artifact('artifacts','native-final-fresh-probe'),artifact('.checkpoint-state','native-final-restore-evidence')]
    jobs['raws-native-probe']=probe
    resume=job(seed=True)
    resume['environment'].update(
        RAWS_NATIVE_RESUME_RECEIPT_ID='<< pipeline.parameters.native_resume_receipt_id >>',
        RAWS_NATIVE_RESUME_CACHE_KEY='<< pipeline.parameters.native_resume_cache_key >>')
    resume['steps'] += [run('Validate explicit resume selector before cache access', '''python3 - <<'PYCODE'
import os,re
if not re.fullmatch('[0-9a-f]{64}',os.environ['RAWS_NATIVE_RESUME_RECEIPT_ID']):raise SystemExit('Exact receipt ID required')
if not re.fullmatch('raws-native-progress-v1-[A-Za-z0-9_-]+',os.environ['RAWS_NATIVE_RESUME_CACHE_KEY']):raise SystemExit('Exact native progress cache key required')
PYCODE'''),
        restore('<< pipeline.parameters.native_resume_cache_key >>','Restore explicitly selected prior native progress'),
        phase('select-resume')]+exact_layers()+[phase('verify-resume'),phase('promote-resume'),
        save(VERIFIED,['.checkpoint-head'],'Publish current-pipeline verified resumed head'),
        artifact('artifacts','native-resume-validation')]
    names=list(jobs);chain=[]
    for index,name in enumerate(names):
        item={'filters':{'branches':{'only':BRANCH}}}
        if index:item['requires']=[names[index-1]]
        chain.append({name:item})
    # CircleCI job-group membership is global even for mutually exclusive workflows.
    # Give each group distinct job definitions, not shared member invocations.
    resume_names=['raws-native-validate-resume']
    for original in names:
        if original in ('raws-native-seed','raws-native-validate-inputs'):continue
        unique=original.replace('raws-native-','raws-native-resume-',1)
        jobs[unique]=copy.deepcopy(jobs[original])
        resume_names.append(unique)
    resume_chain=[]
    for index,name in enumerate(resume_names):
        item={'filters':{'branches':{'only':BRANCH}}}
        if index:item['requires']=[resume_names[index-1]]
        resume_chain.append({name:item})
    jobs['raws-native-validate-resume']=resume
    completed_resume=copy.deepcopy(resume)
    completed_resume['environment'].update(RAWS_FINAL_ARCHIVE='true',RAWS_FINAL_PACK_ONLY='true')
    completed_resume['steps']=completed_resume['steps'][:-2]
    # Keep original receipt immutable. This path publishes a separate authorization,
    # never an invented current-workflow compilation receipt or completion marker.
    for step in completed_resume['steps']:
        if isinstance(step,dict) and 'run' in step:
            for old,new in [('select-resume','select-completed-resume'),('verify-resume','verify-completed-resume'),('promote-resume','authorize-completed-resume')]:
                step['run']['command']=step['run']['command'].replace(old,new)
                step['run']['name']=step['run']['name'].replace(old,new)
    for step in completed_resume['steps']:
        if isinstance(step,dict) and 'run' in step:
            for old,new in [('select-completed-resume','select'),('verify-completed-resume','verify'),('authorize-completed-resume','authorize')]:
                if step['run']['command']=='python3 -u tools/ci_feature_seed.py '+old:
                    step['run']['command']='python3 -u tools/completed_feature_resume.py '+new
    completed_resume['steps'] += [save(RECOVERY,['.feature-completed-resume','.raws-final-progress'],'Publish fresh completed-resume authorization with original receipt'),artifact('artifacts','native-completed-resume-validation')]
    jobs['raws-native-validate-completed-resume']=completed_resume
    recovery_pack=copy.deepcopy(pack)
    recovery_pack['environment'].update(RAWS_NATIVE_FEATURE_SEED='true',
        RAWS_NATIVE_RESUME_RECEIPT_ID='<< pipeline.parameters.native_resume_receipt_id >>',
        RAWS_NATIVE_RESUME_CACHE_KEY='<< pipeline.parameters.native_resume_cache_key >>')
    for index,step in enumerate(recovery_pack['steps']):
        if isinstance(step,dict) and 'restore_cache' in step and step['restore_cache']['keys']==[COMPLETED]:
            recovery_pack['steps'][index]=restore(RECOVERY,'Restore exact current-workflow recovery proof and original completed receipt')
        elif isinstance(step,dict) and 'run' in step and step['run']['command']=='python3 -u tools/ci_final_archive.py prepare-archive':
            recovery_pack['steps'][index]=run('Authorize exact completed receipt without rewriting provenance','python3 -u tools/completed_feature_resume.py prepare')
    capture_index=next(i for i,s in enumerate(recovery_pack['steps']) if isinstance(s,dict) and s.get('run',{}).get('command')=='python3 -u tools/ci_final_archive.py capture')
    recovery_pack['steps'].insert(capture_index,run('Reverify actual restored source GN and signed APK before full capture','python3 -u tools/completed_feature_resume.py verify-pack'))
    jobs['raws-native-recovery-pack']=recovery_pack
    recovery_chain=[]
    jobs['raws-native-recovery-probe']=copy.deepcopy(probe)
    recovery_names=['raws-native-validate-completed-resume','raws-native-recovery-pack','raws-native-recovery-probe']
    for index,name in enumerate(recovery_names):
        item={'filters':{'branches':{'only':BRANCH}}}
        if index:item['requires']=[recovery_names[index-1]]
        recovery_chain.append({name:item})
    invalid=common(1)
    invalid['steps']=[run('Reject incomplete explicit resume selection',"echo 'Supply both exact resume receipt ID and exact cache key, or neither.' >&2; exit 1")]
    jobs['raws-native-invalid-resume']=invalid
    id_empty={'equal':['','<< pipeline.parameters.native_resume_receipt_id >>']}
    key_empty={'equal':['','<< pipeline.parameters.native_resume_cache_key >>']}
    enabled='<< pipeline.parameters.'+PARAM+' >>'
    completed='<< pipeline.parameters.native_resume_completed >>'
    fresh_when={'and':[enabled,id_empty,key_empty,{'not':completed}]}
    resume_when={'and':[enabled,{'not':id_empty},{'not':key_empty},{'not':completed}]}
    recovery_when={'and':[enabled,{'not':id_empty},{'not':key_empty},completed]}
    invalid_when={'and':[enabled,{'or':[{'and':[id_empty,{'not':key_empty}]},{'and':[{'not':id_empty},key_empty]},{'and':[completed,{'or':[id_empty,key_empty]}]}]}]}
    return {'version':2.1,'parameters':{PARAM:{'type':'boolean','default':False},
        'native_resume_completed':{'type':'boolean','default':False},
        'native_resume_receipt_id':{'type':'string','default':''},
        'native_resume_cache_key':{'type':'string','default':''}},'jobs':jobs,
        'job-groups':{'raws-native-chain':{'jobs':chain},'raws-native-resume-chain':{'jobs':resume_chain},'raws-native-recovery-chain':{'jobs':recovery_chain}},
        'workflows':{
            'RawS native UI candidate':{'when':fresh_when,'jobs':[{'raws-native-chain':{'serial-group':'<< pipeline.project.slug >>/raws-full'}}]},
            'RawS native UI explicit resume':{'when':resume_when,'jobs':[{'raws-native-resume-chain':{'serial-group':'<< pipeline.project.slug >>/raws-full'}}]},
            'RawS native UI completed archive recovery':{'when':recovery_when,'jobs':[{'raws-native-recovery-chain':{'serial-group':'<< pipeline.project.slug >>/raws-full'}}]},
            'Reject incomplete native resume':{'when':invalid_when,'jobs':[{'raws-native-invalid-resume':{'filters':{'branches':{'only':BRANCH}}}}]}}}

if __name__=='__main__':
    (ROOT/'.circleci/native-features.yml').write_text('# Held standalone configuration; see docs/native-feature-pipeline.md.\n'+yaml.safe_dump(generate(),sort_keys=False,width=150))
