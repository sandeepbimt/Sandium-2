#!/usr/bin/env python3
"""RawS-only sharded source checkpoints and verified cross-run output reuse."""
import argparse,concurrent.futures,json,shutil,subprocess,tarfile,time
from pathlib import Path
from raw import ROOT
from ci_compile import file_sha,fingerprint

def partition(items,count=5):
    groups=[[] for _ in range(count)];sizes=[0]*count
    for path,size in sorted(items,key=lambda x:x[1],reverse=True):
        i=min(range(count),key=lambda n:sizes[n]);groups[i].append(path);sizes[i]+=size
    return groups

def pack():
    state=json.loads((ROOT/'handoff/stage1/state.json').read_text())
    if state['status']!='slice_expired':return
    hand=ROOT/'handoff/source';hand.mkdir(parents=True,exist_ok=True)
    candidates=[]
    for p in (ROOT/'work/source').iterdir():
        if p.name=='src':
            for q in p.iterdir():
                if q.name=='out':continue
                if q.name=='third_party' and q.is_dir():candidates.extend(q.iterdir())
                else:candidates.append(q)
        else:candidates.append(p)
    items=[(str(p.relative_to(ROOT/'work')),int(subprocess.check_output(['du','-sb',str(p)],text=True).split()[0])) for p in candidates]
    groups=partition(items);started=time.monotonic()
    def shard(entry):
        i,paths=entry;name=f'source-{i}.tar.zst';target=hand/name
        listing=hand/f'paths-{i}.txt';listing.write_text('\n'.join(paths)+'\n')
        subprocess.run(['tar','--use-compress-program=zstd -T1 -1','-cf',str(target),'-C',str(ROOT/'work'),'-T',str(listing)],check=True,timeout=600)
        return {'name':name,'sha256':file_sha(target),'bytes':target.stat().st_size,'paths':len(paths)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:shards=list(pool.map(shard,enumerate(groups)))
    receipt={'schema':2,'fingerprint':fingerprint(),'shards':shards,'archive_workers':5,'restore_workers':8,'uncompressed_disk_bytes':sum(n for _,n in items),'elapsed_seconds':round(time.monotonic()-started)}
    (hand/'receipt.json').write_text(json.dumps(receipt,indent=2));print('SOURCE_CHECKPOINT',json.dumps(receipt),flush=True)

def restore():
    hand=ROOT/'handoff/source';receipt=json.loads((hand/'receipt.json').read_text())
    if receipt.get('schema')!=2 or receipt['fingerprint']!=fingerprint():raise ValueError('Foreign source handoff')
    shards=receipt['shards']
    if len(shards)!=5:raise ValueError('Expected five independent shards')
    for s in shards:
        if Path(s['name']).name!=s['name'] or file_sha(hand/s['name'])!=s['sha256']:raise ValueError('Corrupt source shard')
    dest=ROOT/'work';dest.mkdir(exist_ok=True)
    if (dest/'source').exists():raise ValueError('Refusing existing source restore')
    started=time.monotonic()
    def extract(s):
        with subprocess.Popen(['zstd','-dc',str(hand/s['name'])],stdout=subprocess.PIPE) as proc:
            with tarfile.open(fileobj=proc.stdout,mode='r|') as tar:tar.extractall(dest,filter='data')
            if proc.wait():raise ValueError('Source decompression failed')
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(extract,shards))
    print('RESTORED_SOURCE',json.dumps({'receipt':receipt,'elapsed_seconds':round(time.monotonic()-started)}),flush=True)

def cache_output():
    pairs=[(p,json.loads(p.read_text())) for p in (ROOT/'handoff').glob('stage*/state.json')]
    valid=[(p,v) for p,v in pairs if v['status']=='slice_expired']
    if not valid:return
    p,state=max(valid,key=lambda x:x[1]['stage']);dest=ROOT/'resume';dest.mkdir(exist_ok=True)
    shutil.copy2(p,dest/'state.json');target=dest/'output.tar.gz'
    if target.exists():target.unlink()
    target.hardlink_to(p.parent/'output.tar.gz')
    print('CACHE_OUTPUT',state['archive_sha256'],target.stat().st_size,flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['pack','restore','cache-output']);a=p.parse_args().action
    {'pack':pack,'restore':restore,'cache-output':cache_output}[a]()
