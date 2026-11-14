#!/usr/bin/env python3
"""Full-mode checkpoint transport. Refresh/compaction is maintenance-only."""
import argparse
import copy
import datetime
import json
import os
from pathlib import Path
import shutil
import time
import zipfile
import bridge
import cli
import sparse_restore
import driver as d
bridge.apply_chain = sparse_restore.apply_chain
cli.apply_chain = sparse_restore.apply_chain
d.MAX_LAYERS=16;d.SLOT_COUNT=16;cli.MAX_LAYERS=16


def summary(plan, receipt_id):
    expiry=min(x['expires_at'] for x in [plan['base']]+plan['layers'])
    utc=lambda t:datetime.datetime.fromtimestamp(t,datetime.timezone.utc).isoformat()
    return dict(receipt_id=receipt_id,layers=len(plan['layers']),capacity=16,
                capacity_due=len(plan['layers'])>=11,earliest_dependency_expires_at=utc(expiry),
                due_at=utc(expiry-2*86400),base_expiry=utc(plan['base']['expires_at']),
                refresh_due=expiry<=time.time()+2*86400,
                last_verified_refresh=plan.get('last_verified_refresh'))


def maintenance_check():
    d.select(precheck=True)
    selected=d.c.read(d.STATE/'selected.json')
    report=summary(selected['payload']['plan'],selected['id'])
    d.c.save(d.STATE/'maintenance-summary.json',report)
    d.c.save(d.STATE/'maintenance-report.json',report)
    print('FULL_MAINTENANCE',json.dumps(report),flush=True)
    if not (report['capacity_due'] or report['refresh_due']):d.c.halt()


def capture():
    d.gate();selected=d.c.read(d.STATE/'selected.json');p=d.valid(selected);plan=p['plan']
    if len(plan['layers'])>=16:raise ValueError('Maintenance required: incremental slots exhausted')
    temporary=d.ROOT/'.bridge-new.zip'
    result=bridge.capture(d.ROOT/'brave-work',d.c.read(d.STATE/'inventory.json'),
        os.environ['CIRCLE_WORKFLOW_ID']+':'+os.environ['CIRCLE_BUILD_NUM'],temporary,
        lambda:cli.quiesce(d.LEGACY,d.ROOT/'brave-work'))
    d.INCOMING.mkdir(exist_ok=True);shutil.move(temporary,d.INCOMING/'payload.zip')
    record=dict(id=result['id'],parent=result['parent'],key=d.new_key('delta',result['id']),
                expires_at=int(time.time())+14*86400,content_bytes=(d.INCOMING/'payload.zip').stat().st_size)
    d.c.save(d.INCOMING/'envelope.json',record);(d.STATE/'outgoing.key').write_text(record['key'])
    # The original base key remains unchanged. Ordinary jobs never refresh or roll up.
    (d.STATE/'base.key').write_text(plan['base']['key'])
    new=copy.deepcopy(plan);new.update(head=record['id'],layers=plan['layers']+[record])
    d.make_candidate(new,selected['id'])


def post_publish_eligibility():
    d.gate()
    receipt=d.c.read(d.HEAD);p=d.valid(receipt)
    remaining=3300-(time.time()-d.c.read(d.STATE/'job-start.json')['epoch'])
    exact=(p['source']==os.environ['CIRCLE_SHA1'] and p['workflow']==os.environ['CIRCLE_WORKFLOW_ID']
           and p['pipeline']==int(os.environ['SANDIUM_PIPELINE_NUMBER']) and p['stage']==int(os.environ['SANDIUM_STAGE']))
    request=dict(head=receipt['id'],source=p['source'],workflow=p['workflow'],pipeline=p['pipeline'],stage=p['stage'],
                 remaining_seconds=remaining,eligible=bool(exact and p['apk_verified'] and remaining>1200))
    d.c.save(d.STATE/'optional-refresh-request.json',request)
    print('FULL_POST_PUBLISH_REFRESH_ELIGIBILITY',json.dumps(request),flush=True)


def optional_check():
    d.gate()
    receipt=d.c.read(d.HEAD);p=d.valid(receipt)
    request_path=d.STATE/'optional-refresh-request.json'
    request=d.c.read(request_path) if request_path.exists() else {}
    bound=dict(head=receipt['id'],source=p['source'],workflow=p['workflow'],pipeline=p['pipeline'],stage=p['stage'])
    if not (request.get('eligible') is True and request.get('remaining_seconds',0)>1200
            and all(request.get(k)==v for k,v in bound.items()) and p['apk_verified']
            and p['source']==os.environ['CIRCLE_SHA1']
            and p['workflow']==os.environ['CIRCLE_WORKFLOW_ID']
            and p['pipeline']==int(os.environ['SANDIUM_PIPELINE_NUMBER'])
            and 1<=p['stage']<=5):
        print('FULL_OPTIONAL_REFRESH_SKIPPED',flush=True);d.c.halt();return
    # Stage six is a separately serialized, fresh maintenance job. Select the
    # exact current head without a stage-five prerequisite (APK can finish early).
    d.c.save(d.STATE/'selected.json',receipt)
    plan=p['plan'];(d.STATE/'base.key').write_text(plan['base']['key'])
    d.c.disk_guard('before-optional-maintenance-restore',plan['base']['archive_bytes']+sum(x['content_bytes'] for x in plan['layers'])+32*1024**2)
    for i in range(d.SLOT_COUNT):
        (d.STATE/f'slot-{i}.key').write_text(plan['layers'][i]['key'] if i<len(plan['layers']) else f'unused-{d.c.scope()}-{i}')
    report=summary(plan,receipt['id']);report['reason']='verified_apk_and_more_than_20_minutes_remained_after_durable_increment_publication'
    d.c.save(d.STATE/'maintenance-report.json',report)
    print('FULL_OPTIONAL_REFRESH_SELECTED',json.dumps(report),flush=True)


def maintenance_capture():
    d.gate();selected=d.c.read(d.STATE/'selected.json');p=d.valid(selected);plan=p['plan']
    raw=(d.ROOT/d.MANIFEST).read_bytes()
    if bridge.base_id(raw)!=plan['base']['id'] or bridge.digest(raw)!=plan['base']['manifest_sha256']:
        raise ValueError('Wrong maintenance base')
    if (d.ROOT/'brave-work').exists():raise ValueError('Maintenance requires fresh disposable workspace')
    rolled=d.ROOT/'.full-maintenance.zip'
    if plan['layers']:
        from rollup import rollup
        result=rollup(plan['base']['id'],[dict(path=d.LAYERS/f'{i}.zip',id=x['id']) for i,x in enumerate(plan['layers'])],rolled)
        # Rollup verifies every input, copies/checks all surviving blobs, fsyncs
        # the merged archive and returns its digest. Keep that verified overlay,
        # not both it and every downloaded input while extracting the full base.
        # These are disposable local copies, never accepted remote caches/head.
        released=0
        for i in range(len(plan['layers'])):
            path=d.LAYERS/f'{i}.zip'
            released+=path.stat().st_size
            path.unlink()
        print('FULL_MAINTENANCE_LOCAL_INPUTS_RELEASED',dict(layers=len(plan['layers']),bytes=released),flush=True)
    else:
        result=None
    # Verify/extract original compressed shards, then prove the new overlay can
    # actually restore. This expensive refresh is NEVER part of ordinary capture.
    cli.run_bounded([os.sys.executable,'-u',str(d.LEGACY),'restore','--root',str(d.ROOT)],d.operation_budget-10)
    if result is None:
        with zipfile.ZipFile(rolled,'w') as z:
            z.writestr('manifest.json',bridge.encode(dict(schema=1,parent=plan['base']['id'],entries={},deleted=[],root_metadata=bridge.root_metadata(d.ROOT/'brave-work'))))
        import hashlib
        result=dict(id=hashlib.sha256(rolled.read_bytes()).hexdigest(),parent=plan['base']['id'])
    sparse_restore.apply_chain(d.ROOT/'brave-work',[dict(archive=rolled,id=result['id'],parent=plan['base']['id'])],plan['base']['id'])
    expires=int(time.time())+14*86400
    base=dict(plan['base'],key=d.new_key('base-refresh',plan['base']['id']),expires_at=expires)
    d.INCOMING.mkdir(exist_ok=True);shutil.move(rolled,d.INCOMING/'payload.zip')
    record=dict(id=result['id'],parent=plan['base']['id'],key=d.new_key('delta-refresh',result['id']),expires_at=expires,content_bytes=(d.INCOMING/'payload.zip').stat().st_size)
    d.c.save(d.INCOMING/'envelope.json',record)
    (d.STATE/'outgoing.key').write_text(record['key']);(d.STATE/'base.key').write_text(base['key'])
    # Source/APK evidence is inherited unchanged, not relabelled as this checkout.
    payload=copy.deepcopy(p)
    payload.update(pipeline=int(os.environ['SANDIUM_PIPELINE_NUMBER']),workflow=os.environ['CIRCLE_WORKFLOW_ID'],stage=int(os.environ['SANDIUM_STAGE']),previous_receipt=selected['id'])
    payload['plan']=dict(base=base,head=record['id'],layers=[record],last_verified_refresh=datetime.datetime.now(datetime.timezone.utc).isoformat())
    d.c.save(d.STATE/'candidate.json',dict(id=bridge.digest(bridge.encode(payload)),payload=payload))
    report=dict(status='candidate_locally_verified_awaiting_cache_saves',before=summary(plan,selected['id']),candidate=summary(payload['plan'],bridge.digest(bridge.encode(payload))))
    d.c.save(d.STATE/'maintenance-report.json',report)
    print('FULL_MAINTENANCE_VERIFIED',json.dumps(report),flush=True)


def maintenance_clear_saved_local():
    candidate=d.c.read(d.STATE/'candidate.json');d.valid(candidate)
    report=d.c.read(d.STATE/'maintenance-report.json')
    if report.get('status')!='candidate_locally_verified_awaiting_cache_saves':
        raise ValueError('No maintenance candidate awaiting readback')
    d.c.save(d.STATE/'maintenance-readback-required.json',dict(candidate=candidate['id']))
    (d.STATE/'maintenance-readback-proof.json').unlink(missing_ok=True)
    # Only disposable downloaded cache objects. Never delete accepted remote
    # caches, source workspace, candidate receipt, or selector key files.
    for path in (d.ROOT/d.SHARDS,d.ROOT/d.MANIFEST,d.INCOMING):
        if path.is_symlink() or path.is_file():path.unlink()
        elif path.is_dir():shutil.rmtree(path)
    report['status']='local_cache_objects_cleared_for_exact_remote_readback'
    d.c.save(d.STATE/'maintenance-report.json',report)


def maintenance_readback():
    import hashlib
    from rollup import archive_hash,validate_manifest
    (d.STATE/'maintenance-readback-proof.json').unlink(missing_ok=True)
    candidate=d.c.read(d.STATE/'candidate.json');p=d.valid(candidate);plan=p['plan']
    required=d.c.read(d.STATE/'maintenance-readback-required.json')
    if required!=dict(candidate=candidate['id']):raise ValueError('Wrong readback candidate')
    if len(plan['layers'])!=1:raise ValueError('Expected one maintained overlay')
    raw=(d.ROOT/d.MANIFEST).read_bytes()
    if bridge.base_id(raw)!=plan['base']['id'] or bridge.digest(raw)!=plan['base']['manifest_sha256']:
        raise ValueError('Readback base identity mismatch')
    cli.run_bounded([os.sys.executable,'-u',str(d.LEGACY),'verify','--root',str(d.ROOT)],d.operation_budget-10)
    record=plan['layers'][0]
    if d.c.read(d.INCOMING/'envelope.json')!=record:raise ValueError('Readback delta envelope mismatch')
    archive=d.INCOMING/'payload.zip'
    if archive_hash(archive)!=record['id']:raise ValueError('Readback delta digest mismatch')
    with zipfile.ZipFile(archive) as z:
        m=validate_manifest(z,plan['base']['id'])
        for name,e in m['entries'].items():
            if e['kind']!='file' or name!=e['links'][0]:continue
            h=hashlib.sha256();size=0
            with z.open(e['blob']) as src:
                while chunk:=src.read(1024*1024):
                    size+=len(chunk);h.update(chunk);bridge.measured(bytes_done=len(chunk))
                    if size>e['size']:raise ValueError('Readback blob exceeds size')
            if size!=e['size'] or h.hexdigest()!=e['sha256']:raise ValueError('Readback blob mismatch')
    d.c.save(d.STATE/'maintenance-readback-proof.json',dict(candidate=candidate['id'],base=plan['base']['id'],delta=record['id']))
    report=d.c.read(d.STATE/'maintenance-report.json')
    report.update(status='remote_readback_verified_awaiting_publication',remote_readback_verified=True)
    d.c.save(d.STATE/'maintenance-report.json',report)


def publish():
    # Maintenance must restore and verify BOTH newly saved immutable objects.
    report=d.STATE/'maintenance-report.json'
    if report.exists():
        candidate=d.c.read(d.STATE/'candidate.json');plan=candidate['payload']['plan']
        proof=d.c.read(d.STATE/'maintenance-readback-proof.json')
        expected=dict(candidate=candidate['id'],base=plan['base']['id'],delta=plan['layers'][0]['id'])
        if proof!=expected:raise ValueError('Missing exact maintenance remote readback proof')
        previous=d.c.read(d.STATE/'selected.json')
        if candidate['payload']['previous_receipt']!=previous['id']:raise ValueError('Wrong previous maintenance head')
        d.c.save(d.HEAD.parent/'previous-receipt.json',previous)
    d.c.publish()
    if report.exists():
        data=d.c.read(report)
        data['status']='published_after_native_cache_saves'
        data['remote_readback_verified']=True
        data['published_receipt']=d.c.read(d.HEAD)['id']
        d.c.save(report,data)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase');parser.add_argument('--slot',type=int);a=parser.parse_args()
    started=d.c.read(d.STATE/'job-start.json')['epoch'] if (d.STATE/'job-start.json').exists() else time.time()
    remaining=3300-(time.time()-started)-(300 if a.phase=='capture' else 600 if a.phase in ('restore','maintenance-capture') else 0)
    d.operation_budget=min(900 if a.phase=='capture' else 2700,remaining)
    if d.operation_budget<=0:raise ValueError('Insufficient job time for checkpoint operation')
    phases={'gate':d.gate,'seed-select':lambda:d.select(True),'select':d.select,'precheck-select':lambda:d.select(precheck=True),
            'seed-capture':d.seed_capture,'ingest':lambda:d.ingest(a.slot),'restore':d.restore,'verify-restored':d.verify_restored,
            'begin':d.begin,'capture':capture,'publish':publish,'final':d.c.final_gate,
            'post-publish-eligibility':post_publish_eligibility,'optional-check':optional_check,'maintenance-check':maintenance_check,'maintenance-capture':maintenance_capture,
            'maintenance-clear-saved-local':maintenance_clear_saved_local,'maintenance-readback':maintenance_readback}
    with d.Watchdog(d.operation_budget,stall_seconds=d.operation_budget if a.phase in ('restore','maintenance-capture','maintenance-readback','seed-capture') else 300):
        phases[a.phase]()
