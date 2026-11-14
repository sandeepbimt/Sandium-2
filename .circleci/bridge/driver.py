#!/usr/bin/env python3
"""Experimental native-cache orchestration for verified legacy B + ordered deltas."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'checkpoint'))
from progress import advance,Watchdog
from job_budget import save_policy
spec=importlib.util.spec_from_file_location('flow_common',HERE.parent/'checkpoint/driver.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
import bridge
from cli import restore_chain,quiesce,run_bounded
bridge.measured=lambda bytes_done=0,items=0:advance(bytes_done=bytes_done,items=items)
ROOT=c.ROOT;STATE=c.STATE;HEAD=c.HEAD
LEGACY=HERE.parent/'scripts/sandium-checkpoint-shards.py'
INCOMING=ROOT/'.checkpoint-incoming';LAYERS=ROOT/'.bridge-layers'
MANIFEST='brave-workspace-checkpoint.manifest.json'
SHARDS='brave-workspace-checkpoint.shards'
KIND='legacy-bridge-v1'


def valid(receipt):
    p=receipt['payload']
    if receipt['id']!=bridge.digest(bridge.encode(p)) or p['scope']!=c.scope() or p['compatibility']!=c.COMPAT or p.get('kind')!=KIND:
        raise ValueError('Invalid or incompatible bridge receipt')
    plan=p['plan'];base=plan['base']
    if len(plan['layers'])>7:raise ValueError('Unbounded delta chain')
    if min(x['expires_at'] for x in [base]+plan['layers'])<=time.time():raise ValueError('Expired dependency; no base-only fallback')
    if p['pipeline']>int(os.environ['SANDIUM_PIPELINE_NUMBER']):raise ValueError('Old rerun refused')
    expected=base['id']
    for layer in plan['layers']:
        if layer['parent']!=expected:raise ValueError('Missing/reordered layer')
        expected=layer['id']
    if plan['head']!=expected:raise ValueError('Incorrect final head')
    return p

c.valid=valid


def gate():
    c.gate()
    if not c.scope().startswith('sandium-exp-single-v1-bridge-'):
        raise ValueError('Dedicated bridge namespace required')


def select(seed=False, precheck=False):
    gate()
    if not HEAD.exists():
        if not seed or os.environ.get('SANDIUM_ALLOW_SEED_IMPORT')!='true':raise ValueError('No accepted bridge head')
        return
    receipt=c.read(HEAD);p=valid(receipt)
    if seed:c.halt();return
    stage=int(os.environ['SANDIUM_STAGE'])
    if not precheck and p['apk_verified'] and p['source']==os.environ['CIRCLE_SHA1']:c.halt();return
    if stage>1 and (p['workflow'],p['stage'],p['source'])!=(os.environ['CIRCLE_WORKFLOW_ID'],stage-1,os.environ['CIRCLE_SHA1']):
        raise ValueError('Exact prior stage receipt required')
    c.save(STATE/'selected.json',receipt)
    plan=p['plan'];(STATE/'base.key').write_text(plan['base']['key'])
    c.disk_guard('before-bridge-cache-restore',plan['base']['archive_bytes']+sum(x['content_bytes'] for x in plan['layers'])+32*1024**2)
    for i in range(8):(STATE/f'slot-{i}.key').write_text(plan['layers'][i]['key'] if i<len(plan['layers']) else f'unused-{c.scope()}-{i}')


def new_key(kind,ident):
    return '-'.join((c.scope(),kind,os.environ['CIRCLE_WORKFLOW_ID'],os.environ['CIRCLE_BUILD_NUM'],ident))


def make_candidate(plan,previous=None):
    status=ROOT/'brave-apk/status.txt'
    apk=status.exists() and all(x in status.read_text().splitlines() for x in ('BUILD_FINISHED=true','APK_ARCHIVE_VALID=true','APK_SIGNATURE_VALID=true','APK_PACKAGE_ID_VALID=true','APK_BRANDING_VALID=true','APK_REMOVALS_VALID=true'))
    p=dict(kind=KIND,scope=c.scope(),compatibility=c.COMPAT,source=os.environ['CIRCLE_SHA1'],pipeline=int(os.environ['SANDIUM_PIPELINE_NUMBER']),
        workflow=os.environ['CIRCLE_WORKFLOW_ID'],stage=int(os.environ['SANDIUM_STAGE']),plan=plan,apk_verified=apk and previous is not None,previous_receipt=previous)
    c.save(STATE/'candidate.json',dict(id=bridge.digest(bridge.encode(p)),payload=p))


def seed_capture():
    gate()
    if HEAD.exists():raise ValueError('Seed cannot replace accepted head')
    if os.environ.get('SANDIUM_ALLOW_SEED_IMPORT')!='true':raise ValueError('Seed not enabled')
    # No extraction or 68 GiB conversion: verify and retain original compressed shards.
    run_bounded([sys.executable,'-u',str(LEGACY),'verify','--root',str(ROOT)],min(1500,operation_budget-10))
    raw=(ROOT/MANIFEST).read_bytes();m=json.loads(raw)
    if len(m['shards'])!=8:raise ValueError('Expected eight canonical shards')
    ident=bridge.base_id(raw)
    base=dict(id=ident,manifest_sha256=bridge.digest(raw),key=new_key('base',ident),expires_at=int(time.time())+14*86400,
              archive_bytes=sum(x['size_bytes'] for x in m['shards']))
    (STATE/'base.key').write_text(base['key'])
    make_candidate(dict(base=base,head=ident,layers=[]))


def ingest(index):
    layers=c.read(STATE/'selected.json')['payload']['plan']['layers']
    if index>=len(layers):return
    record=layers[index]
    if c.read(INCOMING/'envelope.json')!=record:raise ValueError('Missing/prefix-collided delta cache')
    LAYERS.mkdir(exist_ok=True)
    shutil.move(INCOMING/'payload.zip',LAYERS/f'{index}.zip')


def restore():
    selected=c.read(STATE/'selected.json');p=valid(selected);plan=p['plan']
    raw=(ROOT/MANIFEST).read_bytes()
    if bridge.base_id(raw)!=plan['base']['id']:raise ValueError('Wrong/prefix-collided base')
    concrete=dict(base_manifest_sha256=plan['base']['manifest_sha256'],head=plan['head'],layers=[dict(x,archive=str(LAYERS/f'{i}.zip')) for i,x in enumerate(plan['layers'])])
    restore_chain(ROOT,concrete,LEGACY,timeout=operation_budget-10)
    c.save(STATE/'restored-proof.json',dict(receipt=selected['id'],head=plan['head']))


def verify_restored():
    selected=c.read(STATE/'selected.json');valid(selected)
    if c.read(STATE/'restored-proof.json')!=dict(receipt=selected['id'],head=selected['payload']['plan']['head']):raise ValueError('Missing exact restored proof')


def begin():
    verify_restored();quiesce(LEGACY,ROOT/'brave-work')
    head=c.read(STATE/'selected.json')['payload']['plan']['head']
    c.save(STATE/'inventory.json',bridge.begin(ROOT/'brave-work',head,os.environ['CIRCLE_WORKFLOW_ID']+':'+os.environ['CIRCLE_BUILD_NUM']))


def capture():
    gate();selected=c.read(STATE/'selected.json');p=valid(selected);plan=p['plan'];base=dict(plan['base']);layers=plan['layers']
    temporary=ROOT/'.bridge-new.zip'
    result=bridge.capture(ROOT/'brave-work',c.read(STATE/'inventory.json'),os.environ['CIRCLE_WORKFLOW_ID']+':'+os.environ['CIRCLE_BUILD_NUM'],temporary,lambda:quiesce(LEGACY,ROOT/'brave-work'))
    compact=len(layers)>=7 or any(x['expires_at']<time.time()+2*86400 for x in layers)
    if compact:
        from rollup import rollup
        rolled=ROOT/'.bridge-rollup.zip'
        result=rollup(base['id'],[dict(path=LAYERS/f'{i}.zip',id=x['id']) for i,x in enumerate(layers)]+[dict(path=temporary,id=result['id'])],rolled)
        temporary.unlink();temporary=rolled;layers=[]
    INCOMING.mkdir(exist_ok=True)
    shutil.move(temporary,INCOMING/'payload.zip')
    record=dict(id=result['id'],parent=result['parent'],key=new_key('delta',result['id']),expires_at=int(time.time())+14*86400,content_bytes=(INCOMING/'payload.zip').stat().st_size)
    c.save(INCOMING/'envelope.json',record);(STATE/'outgoing.key').write_text(record['key'])
    if base['expires_at']<time.time()+2*86400:
        # Refresh the identical already verified compressed B. No conversion/rehash of decompressed tree.
        base.update(key=new_key('base-refresh',base['id']),expires_at=int(time.time())+14*86400)
    (STATE/'base.key').write_text(base['key'])
    make_candidate(dict(base=base,head=record['id'],layers=layers+[record]),selected['id'])


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase');parser.add_argument('--slot',type=int);args=parser.parse_args()
    started=c.read(STATE/'job-start.json')['epoch'] if (STATE/'job-start.json').exists() else time.time()
    reserve=600 if args.phase in ('capture','seed-capture','restore') else 0
    if args.phase == 'capture':
        # Same horizon-based classification used before compilation. Missing or
        # malformed plans cannot buy extra time; capture itself still validates.
        try:
            plan=c.read(STATE/'selected.json')['payload']['plan']
        except (OSError, KeyError, TypeError, ValueError):
            plan=None
        policy=save_policy(plan,started)
        reserve=policy['seconds']
        print('FLOW_CAPTURE_SAVE_POLICY',json.dumps(policy),flush=True)
    remaining=3300-(time.time()-started)-reserve
    budget=min(900 if args.phase=='capture' else 1800,remaining)
    if budget<=0:raise ValueError('No remaining job budget')
    operation_budget=budget
    advance(phase='bridge-'+args.phase)
    # Legacy subprocess validates/extracts independent shards; only total timeout here,
    # since per-file parent-side progress cannot observe its internal tar reads.
    stall=budget if args.phase in ('seed-capture','restore') else 300
    with Watchdog(budget,stall_seconds=stall):
        {'gate':gate,'seed-select':lambda:select(True),'select':select,'precheck-select':lambda:select(precheck=True),'seed-capture':seed_capture,'ingest':lambda:ingest(args.slot),
         'restore':restore,'verify-restored':verify_restored,'begin':begin,'capture':capture,'publish':c.publish,'final':c.final_gate}[args.phase]()
