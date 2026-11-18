#!/usr/bin/env python3
"""Product adapter for the vendored, proven Full checkpoint engine.

CircleCI performs native immutable save/restore. This adapter cannot assert a
remote save occurred: clear-readback + readback must succeed before publication.
"""
import argparse, hashlib, json, os, shutil, sys, time, zipfile
from pathlib import Path
from ci_compile import fingerprint
from raw import ROOT,require_build_scope
os.environ['RAWS_CHECKPOINT_SCOPE']='raws-full-v1-'+fingerprint()
sys.path.insert(0,str(ROOT/'.circleci/bridge'))
import full_driver as f
import bridge
from rollup import archive_hash,validate_manifest
D=f.d

def fresh():
    return (D.STATE/'fresh.json').exists()

def gate():
    D.gate()
    require_build_scope()
    for name in ['base.key','outgoing.key']+[f'slot-{i}.key' for i in range(16)]:
        p=D.STATE/name
        if not p.exists():p.write_text('unused-'+D.c.scope()+'-'+name)

def prepare():
    gate()
    if D.HEAD.exists():
        D.select()
        f.summary(D.c.read(D.STATE/'selected.json')['payload']['plan'],D.c.read(D.STATE/'selected.json')['id'])
    else:
        if os.environ.get('RAWS_STAGE')!='1' or os.environ.get('RAWS_ALLOW_FRESH_SEED')!='true':
            raise ValueError('Missing accepted head; only explicitly enabled stage1 may bootstrap')
        D.c.save(D.STATE/'fresh.json',{'scope':D.c.scope(),'workflow':os.environ['CIRCLE_WORKFLOW_ID']})

def begin():
    if not fresh():D.begin()

def capture():
    gate()
    state=D.c.read(ROOT/f"handoff/stage{os.environ['RAWS_STAGE']}/state.json")
    if state.get('status')!='slice_expired' or state.get('fingerprint')!=fingerprint():
        raise ValueError('Only verified timeslice exhaustion is resumable')
    if fresh():
        meta=ROOT/'work/source/.sandium';meta.mkdir(exist_ok=True)
        (meta/'checkpoint-manifest.txt').write_text('PRODUCT=RawS\nCOMPATIBILITY='+D.c.COMPAT+'\n')
        f.cli.run_bounded([sys.executable,'-u',str(D.LEGACY),'archive','--root',str(ROOT),'--workers','8'],D.operation_budget-10)
        D.seed_capture()
        # Missing delta is an explicit unused key, never a Brave/default fallback.
        D.INCOMING.mkdir(exist_ok=True)
    else:f.capture()

def clear_readback():
    candidate=D.c.read(D.STATE/'candidate.json');p=D.valid(candidate)
    D.c.save(D.STATE/'readback-required.json',{'candidate':candidate['id'],'fresh':fresh()})
    (D.STATE/'readback-proof.json').unlink(missing_ok=True)
    (D.STATE/'readback-base.key').write_text((D.STATE/'base.key').read_text() if fresh() else 'unused-'+D.c.scope()+'-base-readback')
    (D.STATE/'readback-delta.key').write_text('unused-'+D.c.scope()+'-delta-readback' if fresh() else (D.STATE/'outgoing.key').read_text())
    paths=[ROOT/D.MANIFEST,ROOT/D.SHARDS] if fresh() else [D.INCOMING]
    for path in paths:
        if path.is_symlink() or path.is_file():path.unlink()
        elif path.is_dir():shutil.rmtree(path)

def readback():
    candidate=D.c.read(D.STATE/'candidate.json');p=D.valid(candidate)
    required=D.c.read(D.STATE/'readback-required.json')
    if required!={'candidate':candidate['id'],'fresh':fresh()}:raise ValueError('Wrong readback candidate')
    if fresh():
        raw=(ROOT/D.MANIFEST).read_bytes();base=p['plan']['base']
        if bridge.base_id(raw)!=base['id'] or bridge.digest(raw)!=base['manifest_sha256']:raise ValueError('Base readback mismatch')
        f.cli.run_bounded([sys.executable,'-u',str(D.LEGACY),'verify','--root',str(ROOT)],D.operation_budget-10)
    else:
        record=p['plan']['layers'][-1];archive=D.INCOMING/'payload.zip'
        if D.c.read(D.INCOMING/'envelope.json')!=record or archive_hash(archive)!=record['id']:raise ValueError('Delta readback mismatch')
        with zipfile.ZipFile(archive) as z:
            manifest=validate_manifest(z,record['parent'])
            for name,e in manifest['entries'].items():
                if e['kind']!='file' or name!=e['links'][0]:continue
                h=hashlib.sha256();n=0
                with z.open(e['blob']) as src:
                    while block:=src.read(1024*1024):n+=len(block);h.update(block)
                if n!=e['size'] or h.hexdigest()!=e['sha256']:raise ValueError('Delta blob readback mismatch')
    D.c.save(D.STATE/'readback-proof.json',{'candidate':candidate['id']})

def publish():
    candidate=D.c.read(D.STATE/'candidate.json')
    if D.c.read(D.STATE/'readback-proof.json')!={'candidate':candidate['id']}:raise ValueError('Missing exact remote readback proof')
    if D.HEAD.exists():D.c.save(D.HEAD.parent/'previous-receipt.json',D.c.read(D.HEAD))
    f.publish()

def run(phase,slot=None):
    gate()
    started=D.c.read(D.STATE/'job-start.json')['epoch']
    remaining=3300-(time.time()-started)
    reserve=300 if phase in ('capture','readback') else 60
    D.operation_budget=min(1200,remaining-reserve)
    if D.operation_budget<30:raise ValueError('No safe checkpoint budget remains')
    actions={'gate':gate,'prepare':prepare,'begin':begin,'capture':capture,'clear-readback':clear_readback,'readback':readback,'publish':publish,'final':D.c.final_gate,
      'restore-base':lambda:None if fresh() else f.restore_base(),
      'restore-layer':lambda:None if fresh() else f.restore_layer(slot),
      'restore-finish':lambda:None if fresh() else f.restore_finish(),
      'maintenance-check':f.maintenance_check,'maintenance-capture':f.maintenance_capture,
      'maintenance-clear-saved-local':f.maintenance_clear_saved_local,'maintenance-readback':f.maintenance_readback,'maintenance-publish':f.publish,
      'ingest':lambda:D.ingest(slot)}
    with D.Watchdog(D.operation_budget,stall_seconds=D.operation_budget):actions[phase]()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase');p.add_argument('--slot',type=int);a=p.parse_args();run(a.phase,a.slot)
