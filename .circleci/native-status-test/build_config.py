#!/usr/bin/env python3
"""Derive isolated status APK from the already isolated translation build."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2]
BRANCH='experiment/native-status-api15'
spec=importlib.util.spec_from_file_location('translation',ROOT/'.circleci/translation-test/build_config.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)

def derive(normal):
    cfg=base.derive(copy.deepcopy(normal))
    for job in cfg['workflows']['sandium-full-mode']['jobs']:
        job['brave-android-staged-build']['filters']['branches']['only']=BRANCH
    steps=cfg['jobs']['brave-android-staged-build']['steps']
    for step in steps:
        if 'run' in step:
            step['run']['command']=step['run']['command'].replace(base.BRANCH,BRANCH)
        if 'store_artifacts' in step:
            step['store_artifacts']['destination']='sandium-native-status-test-only/brave-apk'
    def add(before,name,command):
        index=next(i for i,s in enumerate(steps) if isinstance(s,dict) and s.get('run',{}).get('name')==before)
        steps.insert(index,{'run':{'name':name,'command':'set -euo pipefail\n'
          +'test "${CIRCLE_BRANCH:-}" = "'+BRANCH+'"\n'+command+'\n'}})
    args=' --src "$CIRCLE_WORKING_DIRECTORY/brave-work/src" --core "$CIRCLE_WORKING_DIRECTORY/brave-work/src/brave"'
    add('Prepare pinned Brave Android source','Reverse isolated native status candidate before normal overlay replay',
        'python3 experiments/native-status/cleanup.py'+args+' --write')
    add('Validate build graph and remote-execution settings','Apply isolated API15 native NTP and Settings status candidate',
        "python3 -m unittest discover -s experiments/native-status -p 'test*.py'\n"
        +'python3 experiments/native-status/prepare.py'+args+' --test-only-enable --test-only-native-screens --write')
    return cfg

if __name__=='__main__':
    cfg=derive(yaml.safe_load((ROOT/'.circleci/original-full/candidate.yml').read_text()))
    raw=yaml.safe_dump(cfg,sort_keys=False,width=1000)
    for rel in ('.circleci/config.yml','.circleci/native-status-test/config.yml'):(ROOT/rel).write_text(raw)
    (ROOT/'.circleci/native-status-test/config.sha256').write_text(hashlib.sha256(raw.encode()).hexdigest()+'\n')
