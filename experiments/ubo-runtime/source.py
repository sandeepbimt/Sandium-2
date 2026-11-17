#!/usr/bin/env python3
"""Scoped reproducible EXT0 source reset/apply. No network, build or engine cutover."""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).parent
CORE_PIN = '44a84b1f89d9a35287289d6a3d493e362f5a5123'
CHROMIUM_PIN = 'd331de35ca8ab1358c7a17e4bd41627d55eaef51'
RENAMED_SETTINGS = 'android/java/brave-res/drawable/ic_settings.xml'
RENAMED_SETTINGS_SHA = '54ddff249b581c4632e080404d692d754b3041e13c1b616717a9b2a871b7e4a7'
PATCH_SHA = 'aaa98373cb6614700aac99fed04806987028bbeb67b165e73a5e9be4f3bf72b4'

def git(repo, *args, optional=False):
    r = subprocess.run(['git', '-C', str(repo), *args], capture_output=True)
    if r.returncode and not optional:
        raise ValueError(r.stderr.decode())
    return None if r.returncode else r.stdout

def safe(path):
    p = Path(path)
    if p.is_absolute() or '..' in p.parts or not p.parts:
        raise ValueError('Unsafe patch path')
    return path

def target_paths(data):
    return [safe(x.decode()) for x in re.findall(rb'^\+\+\+ b/(.+)$', data, re.M)]

def blob(repo,pin,path):
    return git(repo,'show',pin+':'+path,optional=True)

def patched(data, target, patch):
    if target_paths(patch) != [target]:
        raise ValueError('Unexpected native patch target')
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);p=root/target;p.parent.mkdir(parents=True);p.write_bytes(data)
        for args in (['--check'],[]):
            subprocess.run(['git','apply','--whitespace=nowarn',*args,'-'],cwd=root,input=patch,check=True,capture_output=True)
        return p.read_bytes()

def plan(core,src,enabled):
    for repo,pin in ((core,CORE_PIN),(src,CHROMIUM_PIN)):
        if git(repo,'rev-parse','HEAD').decode().strip()!=pin:
            raise ValueError('Source pin mismatch')
    patch=(ROOT/'brave-android-extensions.patch').read_bytes()
    if hashlib.sha256(patch).hexdigest()!=PATCH_SHA:
        raise ValueError('Patch digest mismatch')
    paths=target_paths(patch)
    if len(paths)!=len(set(paths)):raise ValueError('Duplicate core target')
    original={p:blob(core,CORE_PIN,p) for p in paths}
    # Compute all postimages from exact pinned blobs before any live writes.
    with tempfile.TemporaryDirectory() as td:
        stage=Path(td)
        for name,data in original.items():
            if data is not None:
                p=stage/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
        subprocess.run(['git','apply','--check','-'],cwd=stage,input=patch,check=True,capture_output=True)
        subprocess.run(['git','apply','-'],cwd=stage,input=patch,check=True,capture_output=True)
        candidate={p:(stage/p).read_bytes() for p in paths}
    payload={core/p:(candidate[p] if enabled else original[p]) for p in paths}
    for name in paths:
        if not name.startswith('patches/'):continue
        native_patch=candidate[name]
        targets=target_paths(native_patch)
        if len(targets)!=1:raise ValueError('Expected one native target')
        target=targets[0];raw=blob(src,CHROMIUM_PIN,target)
        if raw is None:raise ValueError('Missing native input')
        use=native_patch if enabled else original[name]
        payload[src/target]=patched(raw,target,use) if use is not None else raw
    # Existing collision on an experiment-added file is not permission to delete it.
    for name,old in original.items():
        p=core/name
        if old is None and p.exists() and p.read_bytes()!=candidate[name]:
            raise ValueError('Unowned new-path collision: '+name)
    retire_renamed_settings(core,enabled,payload)
    for p in payload:
        if p.is_symlink() or any(q.is_symlink() for q in p.parents if q not in (core.parent,src.parent)):
            raise ValueError('Symlink target refused')
    return payload

def retire_renamed_settings(core,enabled,payload):
    # The port renames this resource; retire its exact pinned old name too.
    # Otherwise Android resource inventory rejects the unlisted old drawable.
    old_settings=blob(core,CORE_PIN,RENAMED_SETTINGS)
    if old_settings is None or hashlib.sha256(old_settings).hexdigest()!=RENAMED_SETTINGS_SHA:
        raise ValueError('Unexpected pinned settings drawable')
    old_path=core/RENAMED_SETTINGS
    if old_path.exists() and old_path.read_bytes()!=old_settings:
        raise ValueError('Unowned settings drawable modification')
    payload[old_path]=None if enabled else old_settings

def execute(core,src,enabled):
    payload=plan(core,src,enabled)
    # Deterministic complete preflight; interruption can be recovered by replay.
    for p,data in payload.items():
        if data is None:
            if p.exists():p.unlink()
        else:
            p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    print('EXT0_SOURCE='+('APPLIED' if enabled else 'RESET')+'; runtime remains disabled; Brave blocker retained')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--core',type=Path,required=True)
    parser.add_argument('--src',type=Path,required=True);parser.add_argument('--mode',choices=['on','off'],required=True)
    a=parser.parse_args();execute(a.core.resolve(),a.src.resolve(),a.mode=='on')
