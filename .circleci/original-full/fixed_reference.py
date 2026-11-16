"""Inactive fixed-reference identity/expiry gates. No downloads or publication."""
import base64
import argparse
import os
import time
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess

CACHE='sandium-bridge-base-v1-qPgQ5VYKvKjfebPZMGkn2QqAn0I_pgCmZ64n7Kzs6rg='
BYTES=32775343758
DEADLINE=1795940573  # 2026-11-29T08:22:53Z, conservative capture+14 days
MARGIN=2*86400
CHROMIUM='d331de35ca8ab1358c7a17e4bd41627d55eaef51'
BRAVE='44a84b1f89d9a35287289d6a3d493e362f5a5123'
SCOPE='sandium-exp-single-v1-bridge-backpreview01'
COMPAT='brave-44a84b1-chromium-d331de3-arm64-release-single-v1'

def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
def digest(data):return hashlib.sha256(data).hexdigest()
def envelope(payload):return dict(id=digest(encode(payload)),payload=payload)
def unpack(record):
    p=record['payload']
    if record['id']!=digest(encode(p)):raise ValueError('Reference/receipt digest mismatch')
    return p

def physical_key(logical):
    if not isinstance(logical,str) or not logical:raise ValueError('Missing logical key')
    return 'sandium-bridge-base-v1-'+base64.b64encode(hashlib.sha256(logical.encode()).digest()).decode().replace('/', '_')

def hash_id(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value):raise ValueError('Invalid content identity')
    return value

def bootstrap(receipt,scope,now):
    """Metadata-only read of a trusted accepted receipt; NEVER consume its deltas."""
    p=unpack(receipt)
    if scope!=SCOPE or p['scope']!=SCOPE or p['compatibility']!=COMPAT or p['kind']!='legacy-bridge-v1':
        raise ValueError('Incompatible accepted receipt')
    base=p['plan']['base']
    if physical_key(base['key'])!=CACHE or base['archive_bytes']!=BYTES or base['expires_at']!=DEADLINE:
        raise ValueError('Accepted base differs from approved fixed reference')
    if now>=DEADLINE:raise ValueError('Fixed base expired')
    return envelope(dict(schema=1,scope=SCOPE,status='candidate',cache_key=CACHE,
        logical_cache_key=base['key'],manifest_sha256=hash_id(base['manifest_sha256']),base_id=hash_id(base['id']),
        archive_bytes=BYTES,expires_at=DEADLINE,compatibility=COMPAT,
        chromium_pin=CHROMIUM,brave_pin=BRAVE,bootstrap_receipt=receipt['id']))

def check(record,now,accepted=True):
    p=unpack(record)
    if p['schema']!=1 or p['scope']!=SCOPE or p['compatibility']!=COMPAT or p['chromium_pin']!=CHROMIUM or p['brave_pin']!=BRAVE:
        raise ValueError('Incompatible fixed reference')
    if accepted and p['status']!='verified':raise ValueError('Reference not verified')
    if type(p['expires_at']) is not int or p['expires_at']<=now or p['expires_at']>now+15*86400:
        raise ValueError('Invalid or expired immutable deadline')
    if p['archive_bytes']!=BYTES:raise ValueError('Changed fixed reference size')
    hash_id(p['manifest_sha256']);hash_id(p['base_id'])
    if physical_key(p['logical_cache_key'])!=p['cache_key']:
        raise ValueError('Invalid immutable cache key')
    return p

def verify_archives(record,root,legacy_script,now):
    p=check(record,now,accepted=False);root=Path(root)
    raw=(root/'brave-workspace-checkpoint.manifest.json').read_bytes()
    if digest(raw)!=p['manifest_sha256'] or digest(b'legacy-base-v1\0'+raw)!=p['base_id']:
        raise ValueError('Fixed manifest identity mismatch')
    manifest=json.loads(raw)
    if len(manifest.get('shards',[]))!=8 or sum(x['size_bytes'] for x in manifest['shards'])!=BYTES:
        raise ValueError('Fixed shard size/count mismatch')
    spec=importlib.util.spec_from_file_location('fixed_legacy',legacy_script)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    mod.verify(root,zstd_test=False,workers=8)
    return p

def accept_bootstrap(candidate,root,legacy_script,now):
    p=verify_archives(candidate,root,legacy_script,now)
    if p['status']!='candidate' or p['cache_key']!=CACHE:raise ValueError('Not original bootstrap')
    for path,pin in [(Path(root)/'brave-work/src',CHROMIUM),(Path(root)/'brave-work/src/brave',BRAVE)]:
        actual=subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
        if actual!=pin:raise ValueError('Restored source pin mismatch')
    return envelope(dict(p,status='verified',verified_at=int(now)))

def renewal_candidate(accepted,new_logical_key,now):
    p=check(accepted,now)
    if p['expires_at']-now>MARGIN:raise ValueError('Reference not near expiry')
    new_key=physical_key(new_logical_key)
    if new_key==p['cache_key']:
        raise ValueError('Refresh requires distinct immutable cache key')
    # New transport keys avoid Base64 punctuation whose escaping is not specified
    # by CircleCI docs. The original observed bootstrap key remains unchanged.
    original=new_logical_key
    nonce=0
    while any(ch in base64.b64encode(hashlib.sha256(new_logical_key.encode()).digest()).decode() for ch in '+/'):
        nonce+=1
        new_logical_key=original+':'+str(nonce)
    new_key=physical_key(new_logical_key)
    return envelope(dict(p,status='renewal_candidate',cache_key=new_key,logical_cache_key=new_logical_key,
        expires_at=int(now)+14*86400,renewal_created_at=int(now),previous_reference=accepted['id']))

def accept_renewal(previous,candidate,readback_root,legacy_script,now):
    old=check(previous,now);new=verify_archives(candidate,readback_root,legacy_script,now)
    if new['status']!='renewal_candidate' or new.get('previous_reference')!=previous['id']:
        raise ValueError('Wrong renewal predecessor')
    created=new.get('renewal_created_at')
    if type(created) is not int or created>now or candidate!=renewal_candidate(previous,new['logical_cache_key'],created):
        raise ValueError('Invalid renewal deadline or creation gate')
    if new['cache_key']==old['cache_key']:raise ValueError('Cannot overwrite immutable cache')
    for field in ('base_id','manifest_sha256','archive_bytes','chromium_pin','brave_pin','bootstrap_receipt'):
        if new[field]!=old[field]:raise ValueError('Refresh changed fixed content')
    # Caller must save cache, clear local inputs, restore exact new key, then call.
    # Returned record is data only; caller atomically publishes after native success.
    return envelope(dict(new,status='verified',verified_at=int(now)))

def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.pending');temp.write_bytes(encode(value));os.replace(temp,path)

def read(path):return json.loads(Path(path).read_text())

def actual_pins(root):
    for path,pin in [(Path(root)/'brave-work/src',CHROMIUM),(Path(root)/'brave-work/src/brave',BRAVE)]:
        actual=subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
        if actual!=pin:raise ValueError('Restored source pin mismatch')

def select(root,legacy_receipt,now):
    state=Path(root)/'.fixed-reference';accepted=state/'accepted.json'
    if accepted.exists():
        record=read(accepted);check(record,now)
    else:
        if legacy_receipt is None:raise ValueError('Exact bootstrap receipt path required')
        record=bootstrap(read(legacy_receipt),SCOPE,now)
    atomic_json(state/'selected.json',record)
    (state/'cache.key').write_bytes(record['payload']['logical_cache_key'].encode())
    return record

def postrestore(root,legacy_script,now):
    state=Path(root)/'.fixed-reference';record=read(state/'selected.json')
    p=verify_archives(record,root,legacy_script,now)
    actual_pins(root)
    if p['status']=='candidate':record=envelope(dict(p,status='verified',verified_at=int(now)))
    elif p['status']!='verified':raise ValueError('Unexpected selected status')
    atomic_json(state/'accepted.json',record)
    return record

def clear_readback(root,legacy_script,now):
    root=Path(root);state=root/'.fixed-reference'
    previous=read(state/'accepted.json');candidate=read(state/'renewal.json')
    # Validate predecessor, content and due creation gate BEFORE local disposal.
    accept_renewal(previous,candidate,root,legacy_script,now)
    raw=(root/'brave-workspace-checkpoint.manifest.json').read_bytes()
    manifest=json.loads(raw);directory=root/'brave-workspace-checkpoint.shards'
    paths=[directory/x['name'] for x in manifest['shards']]+[root/'brave-workspace-checkpoint.manifest.json']
    if root.is_symlink() or directory.is_symlink() or len(set(paths))!=9:
        raise ValueError('Unsafe readback cleanup paths')
    for path in paths:
        if path.parent not in (root,directory) or path.is_symlink() or not path.is_file():
            raise ValueError('Unsafe readback cleanup file')
    # Marker is written first as busy so partial cleanup cannot produce acceptance.
    atomic_json(state/'readback.json',dict(candidate=candidate['id'],ready=False))
    for path in paths:path.unlink()
    atomic_json(state/'readback.json',dict(candidate=candidate['id'],ready=True))

def cli():
    parser=argparse.ArgumentParser()
    parser.add_argument('phase',choices=['select','preverify','postrestore','renewal-check','renewal-prepare','renewal-clear','renewal-accept'])
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--legacy-script',type=Path,required=True)
    parser.add_argument('--legacy-receipt',type=Path)
    parser.add_argument('--new-logical-key')
    args=parser.parse_args();root=args.root.resolve();state=root/'.fixed-reference';now=time.time()
    if args.phase=='select':select(root,args.legacy_receipt,now)
    elif args.phase=='preverify':verify_archives(read(state/'selected.json'),root,args.legacy_script,now)
    elif args.phase=='postrestore':postrestore(root,args.legacy_script,now)
    elif args.phase=='renewal-check':
        p=check(read(state/'accepted.json'),now)
        state.mkdir(parents=True,exist_ok=True)
        (state/'renewal-due').write_text('yes' if p['expires_at']-now<=MARGIN else 'no')
    elif args.phase=='renewal-prepare':
        record=renewal_candidate(read(state/'accepted.json'),args.new_logical_key,now)
        atomic_json(state/'renewal.json',record)
        (state/'cache.key').write_bytes(record['payload']['logical_cache_key'].encode())
    elif args.phase=='renewal-clear':clear_readback(root,args.legacy_script,now)
    elif args.phase=='renewal-accept':
        candidate=read(state/'renewal.json');marker=read(state/'readback.json')
        if marker!=dict(candidate=candidate['id'],ready=True):raise ValueError('Missing exact clean readback gate')
        record=accept_renewal(read(state/'accepted.json'),candidate,root,args.legacy_script,now)
        atomic_json(state/'accepted.json',record)
        atomic_json(state/'readback.json',dict(candidate=candidate['id'],ready=False,accepted=True))
    print('FIXED_REFERENCE_PHASE=PASS',args.phase)

if __name__=='__main__':cli()
