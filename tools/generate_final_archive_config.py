#!/usr/bin/env python3
"""Three separately bounded jobs, serialized together; normal Full unchanged."""
import copy,yaml
from generate_full_config import ROOT,generate,run,save,restore,common,gate,layers

def phase(p):return run('Final archive '+p,'python3 -u tools/ci_final_archive.py '+p)
def clock():return run('Start one-off job budget before setup',"mkdir -p .checkpoint-state\npython3 -c 'import json,time;json.dump({\"epoch\":time.time()},open(\".checkpoint-state/job-start.json\",\"w\"))'")
def isolated_restore(steps):
    for step in steps:
        if step=='checkout':yield step;yield clock();continue
        if isinstance(step,dict) and 'restore_cache' in step:
            original=step['restore_cache']['keys'][0]
            if original.startswith('raws-full-delta-v1-'):
                step['restore_cache']['keys'].insert(0,original.replace('raws-full-delta-v1-','raws-final-delta-v1-'))
        yield step

def generate_archive(config=None):
    if config is None:config=generate()
    job=copy.deepcopy(config['jobs']['raws-full-stage-1'])
    steps=job['steps'];cut=next(i for i,s in enumerate(steps) if isinstance(s,dict) and s.get('run',{}).get('name')=='RawS Full completion')
    progress='raws-final-progress-v1-{{ checksum ".checkpoint-state/scope-key" }}-'
    exact='raws-final-completed-v1-<< pipeline.id >>'
    job['steps']=[]
    for step in isolated_restore(steps[:cut]):
        if isinstance(step,dict) and step.get('run',{}).get('name')=='RawS Full prepare':
            job['steps'] += [restore(progress,'Restore isolated one-off progress before normal head fallback'),phase('prepare')]
        else:job['steps'].append(step)
    job['environment'].update(RAWS_FINAL_ARCHIVE='true',RAWS_ALLOW_FRESH_SEED='false')
    delta='raws-final-delta-v1-{{ checksum ".checkpoint-state/outgoing.key" }}'
    job['steps'] += [phase('progress-capture'),save(delta,['.checkpoint-incoming'],'Save isolated one-off increment'),phase('progress-clear'),restore(delta,'Read back exact isolated increment'),phase('progress-publish'),save(progress+'{{ checksum ".raws-final-progress/receipt.json" }}',['.raws-final-progress'],'Publish independent verified continuation'),{'store_artifacts':{'path':'.raws-final-progress','destination':'raws-final-progress-evidence'}},phase('progress-final'),save(exact,['.raws-final-progress'],'Publish same-workflow completed handoff')]
    pack=common(1);pack['environment'].update(RAWS_FINAL_ARCHIVE='true',RAWS_FINAL_PACK_ONLY='true',RAWS_ALLOW_FRESH_SEED='false')
    # No source regeneration, hooks or compilation in the packaging worker.
    startup=gate()[:-1] # omit normal head lookup; only exact same-workflow continuation accepted
    pack['steps']=list(isolated_restore(startup))+[restore(exact,'Restore exact same-workflow completed handoff'),phase('prepare-archive')]+list(isolated_restore(layers('sequential')))
    key='raws-final-base-v1-{{ checksum ".raws-final-archive/base.key" }}'
    final_exact='raws-final-verified-v1-<< pipeline.id >>'
    pack['steps'] += [phase('capture'),save(key,['raw-workspace-checkpoint.manifest.json','raw-workspace-checkpoint.shards'],'Save independent completed full archive'),phase('clear'),restore(key,'Read back exact completed full archive'),phase('verify-publish'),save('raws-final-receipt-v1-{{ checksum ".raws-final-archive/receipt.json" }}',['.raws-final-archive'],'Save independent verified final receipt'),save(final_exact,['.raws-final-archive'],'Publish exact final receipt for fresh-worker probe'),{'store_artifacts':{'path':'.raws-final-archive','destination':'raws-final-archive-evidence'}}]
    probe=common(1);probe['environment'].update(RAWS_FINAL_ARCHIVE='true',RAWS_FINAL_PACK_ONLY='true',RAWS_ALLOW_FRESH_SEED='false')
    probe['steps']=list(isolated_restore(gate()[:-1]))+[restore(final_exact,'Restore exact same-workflow verified final receipt'),phase('prepare-probe'),restore('raws-final-base-v1-{{ checksum ".checkpoint-state/base.key" }}','Restore completed full base only'),run('Verify and extract full base on fresh worker','python3 -u tools/ci_full.py restore-base'),run('Certify full base restore without deltas','python3 -u tools/ci_full.py restore-finish'),run('Probe unchanged target on restored completed workspace','python3 -u tools/ci_restore_probe.py'),{'store_artifacts':{'path':'artifacts','destination':'raws-fresh-restore-probe'}},{'store_artifacts':{'path':'.checkpoint-state','destination':'raws-fresh-restore-evidence'}}]
    group={'jobs':[{'raws-final-compile':{'filters':{'branches':{'only':'raw-sandium/official158'}}}},{'raws-final-pack':{'requires':['raws-final-compile'],'filters':{'branches':{'only':'raw-sandium/official158'}}}},{'raws-final-probe':{'requires':['raws-final-pack'],'filters':{'branches':{'only':'raw-sandium/official158'}}}}]}
    return {'version':2.1,'parameters':{'run_raw_final_archive':{'type':'boolean','default':False}},'jobs':{'raws-final-compile':job,'raws-final-pack':pack,'raws-final-probe':probe},'job-groups':{'raws-final-chain':group},'workflows':{'RawS one-off final archive':{'when':'<< pipeline.parameters.run_raw_final_archive >>','jobs':[{'raws-final-chain':{'serial-group':'<< pipeline.project.slug >>/raws-full'}}]}}}
if __name__=='__main__':(ROOT/'.circleci/final-archive.yml').write_text('# Explicit one-off config, never automatic.\n'+yaml.safe_dump(generate_archive(),sort_keys=False,width=150))
