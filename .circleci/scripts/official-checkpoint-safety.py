#!/usr/bin/env python3
"""Exceptional official rebuild: reclaim verified transport, reserve archive time."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time


def budget(start, now, stage):
    # 60m job ceiling; 28m reserved for termination, validation, archive,
    # cache upload and safety. First-stage ceiling is 12m until measured.
    if start <= 0 or now < start:
        raise ValueError('invalid job-start clock')
    seconds = min(720 if stage == 1 else 1500, 3600 - (now-start) - 1680)
    if seconds < 60:
        raise ValueError('insufficient whole-job time for safe compile and archive')
    return seconds


def reclaim(root):
    root = root.resolve()
    work = root/'brave-work'
    for rel in ['.sandium/workspace-checkpoint-restored', '.gclient', 'src/out/android_Release_arm64/build.ninja']:
        if not (work/rel).is_file():
            raise ValueError('missing restored workspace proof: '+rel)
    directory=root/'brave-workspace-checkpoint.shards'
    manifest=root/'brave-workspace-checkpoint.manifest.json'
    if directory.is_symlink() or manifest.is_symlink() or not directory.is_dir():
        raise ValueError('only regular parallel-shard transport is supported')
    payload=json.loads(manifest.read_text())
    names=[x['name'] for x in payload['shards']]
    expected=[f'shard-{i:02d}-of-08.tar.zst' for i in range(1,9)]
    if sorted(names)!=expected or {p.name for p in directory.iterdir()} != set(expected):
        raise ValueError('unexpected transport files; refusing cleanup')
    paths=[directory/n for n in expected]
    if any(not stat.S_ISREG(p.lstat().st_mode) for p in paths):
        raise ValueError('nonregular shard; refusing cleanup')
    spec=importlib.util.spec_from_file_location('shards',Path(__file__).with_name('sandium-checkpoint-shards.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.verify(root,zstd_test=False,workers=8)
    # Persist the exact incoming manifest and deleted-file hashes before deletion.
    receipt=work/'.sandium/reclaimed-transport.json'
    receipt.write_text(json.dumps({'manifest':payload,'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'bytes':sum(p.stat().st_size for p in paths)},sort_keys=True)+'\n')
    with receipt.open('rb') as f: os.fsync(f.fileno())
    for p in paths: p.unlink()
    directory.rmdir()
    # Keep tiny incoming manifest for provenance. New archive replaces it only
    # through existing atomic publication; never remove source/output or remote cache.
    free=shutil.disk_usage(root).free
    print('OFFICIAL_TRANSPORT_RECLAIM=PASS free_bytes='+str(free))
    # Empirical 1392 archive exceeded 30GB. Require 50GiB immediately after
    # reclaim; this is a fail-closed headroom floor, not a compression guarantee.
    if free < 50*1024**3:
        raise ValueError('less than 50GiB free after reclaim; refusing official compile')

def space(root):
    root=root.resolve()
    size=int(subprocess.check_output(['du','-sb',str(root/'brave-work')],text=True).split()[0])
    required=max(40*1024**3, (size*65)//100 + 4*1024**3)
    free=shutil.disk_usage(root).free
    print(f'OFFICIAL_ARCHIVE_SPACE source_bytes={size} free_bytes={free} required_bytes={required}')
    if free<required:
        raise ValueError('insufficient archive headroom; no archive will be attempted')

if __name__=='__main__':
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='cmd',required=True)
    b=sub.add_parser('budget');b.add_argument('--stage',type=int,required=True)
    c=sub.add_parser('reclaim');c.add_argument('--root',type=Path,required=True)
    c=sub.add_parser('space');c.add_argument('--root',type=Path,required=True)
    a=parser.parse_args()
    if a.cmd=='budget': print(budget(int(Path('/tmp/sandium-job-start-epoch').read_text()),int(time.time()),a.stage))
    elif a.cmd=='reclaim': reclaim(a.root)
    else: space(a.root)
