"""Sparse schema-1 delta replay for the proven Full checkpoint restore.

Untouched paths come from the verified base and exact ordered ancestors. Only
changed paths and ancestors are examined; no complete-tree reconstruction.
Requires disposable, trusted, writer-free job filesystem, as capture does.
"""
from bridge import safe, digest, measured
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile
from functools import lru_cache

def apply(root, archive, expected_id, parent):
    """Apply only to a disposable restored job tree; failure invalidates whole tree."""
    root=Path(root)
    h=hashlib.sha256()
    with open(archive,'rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk);measured(bytes_done=len(chunk))
    if h.hexdigest()!=expected_id:raise ValueError('Corrupt delta archive')
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        if len(set(names))!=len(names):raise ValueError('Duplicate archive members')
        m=json.loads(z.read('manifest.json'))
        if m['schema']!=1 or m['parent']!=parent:raise ValueError('Wrong ordered parent')
        entries=m['entries'];deleted=set(m['deleted'])
        for name in set(entries)|set(deleted):safe(name)
        # Validate only touched topology; an already verified base/ordered parent
        # is authoritative for untouched paths. Never walk through symlinks.
        directory_metadata = {}
        @lru_cache(maxsize=None)
        def existing(name):
            parts = PurePosixPath(name).parts
            p = root
            for part in parts[:-1]:
                p = p / part
                if p.is_symlink() or not p.is_dir():
                    return False
            return (root/name).exists() or (root/name).is_symlink()
        for name in set(entries) | deleted:
            ancestor = PurePosixPath(name).parent
            while str(ancestor) != '.':
                n = str(ancestor)
                if n not in directory_metadata and existing(n):
                    p = root/n
                    st = p.lstat()
                    if stat.S_ISDIR(st.st_mode):
                        directory_metadata[n] = dict(kind='directory',mode=stat.S_IMODE(st.st_mode),mtime=st.st_mtime_ns)
                ancestor = ancestor.parent
        for name in entries:
            ancestor = PurePosixPath(name).parent
            while str(ancestor) != '.':
                n = str(ancestor)
                if n in entries:
                    if entries[n]['kind'] != 'directory':
                        raise ValueError('Non-directory target parent')
                elif n in deleted or not existing(n) or (root/n).is_symlink() or not (root/n).is_dir():
                    raise ValueError('Missing/unsafe target parent')
                ancestor = ancestor.parent
        present = {n for n in set(entries) | deleted if existing(n)}
        if not m.get('tombstones_idempotent',False) and not deleted <= present:
            raise ValueError('Tombstone missing from ordered parent')
        expected_members={'manifest.json'}
        for n,e in entries.items():
            measured(items=1)
            if e['kind'] not in ('file','directory','symlink'):raise ValueError('Bad kind')
            if e['kind']=='file':
                links=e['links']
                if not links or n not in links or sorted(set(links))!=links:raise ValueError('Bad link group')
                for member in links:
                    if entries.get(member,{}).get('links')!=links or entries[member].get('kind')!='file':raise ValueError('Incomplete link group')
                    if (entries[member]['mode'],entries[member]['mtime'])!=(e['mode'],e['mtime']):raise ValueError('Inconsistent hardlink metadata')
                if n==links[0]:
                    if e['blob']!='data/'+digest(n.encode()):raise ValueError('Bad blob path')
                    expected_members.add(e['blob'])
        if set(names)!=expected_members:raise ValueError('Unexpected/missing archive members')
        needed=sum(e['size'] for n,e in entries.items() if e['kind']=='file' and n==e['links'][0])
        free=shutil.disk_usage(root.parent).free
        print('BRIDGE_APPLY_DISK',dict(free=free,required=needed+32*1024**2),flush=True)
        if free<needed+32*1024**2:raise ValueError('Insufficient delta staging space')
        # Stage and verify all changed content before modifying the restored tree.
        stage=Path(tempfile.mkdtemp(prefix='.bridge-payload-',dir=root.parent))
        try:
            for n,e in entries.items():
                measured(items=1)
                if e['kind']!='file' or n!=e['links'][0]:continue
                dest=stage/digest(n.encode());hh=hashlib.sha256();size=0
                with z.open(e['blob']) as f,dest.open('xb') as out:
                    while chunk:=f.read(1024*1024):
                        size+=len(chunk)
                        if size>e['size']:raise ValueError('Oversized blob')
                        hh.update(chunk);out.write(chunk);measured(bytes_done=len(chunk))
                if size!=e['size'] or hh.hexdigest()!=e['sha256']:raise ValueError('Bad blob')
            for n in sorted(set(deleted)|set(entries),key=lambda s:len(PurePosixPath(s).parts),reverse=True):
                if n not in present:continue # never traverse an old symlink ancestor for new children
                p=root/n
                if not p.exists() and not p.is_symlink():continue
                # Same-kind dirs retain unchanged descendants. Type changes may not.
                if p.is_dir() and not p.is_symlink():
                    if entries.get(n,{}).get('kind')=='directory':continue
                    p.rmdir() # refuses silently dropping undeclared descendants
                else:p.unlink()
            for n,e in sorted(entries.items(),key=lambda item:(len(PurePosixPath(item[0]).parts),item[0])):
                measured(items=1)
                p=root/n
                if e['kind']=='directory':p.mkdir(exist_ok=True)
                elif e['kind']=='symlink':os.symlink(e['target'],p)
                else:os.link(stage/digest(e['links'][0].encode()),p)
            metadata = {n:e for n,e in directory_metadata.items() if n not in deleted and entries.get(n,e)['kind']=='directory'}
            metadata.update(entries)
            for n,e in sorted(metadata.items(),key=lambda item:len(PurePosixPath(item[0]).parts),reverse=True):
                measured(items=1)
                p=root/n
                if e['kind']!='symlink':os.chmod(p,e['mode'])
                os.utime(p,ns=(e['mtime'],e['mtime']),follow_symlinks=False)
            os.chmod(root,m['root_metadata']['mode'])
            stamp=m['root_metadata']['mtime'];os.utime(root,ns=(stamp,stamp))
        finally:shutil.rmtree(stage)
    return expected_id



def apply_chain(root, layers, parent):
    root=Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Real root directory required')
    for layer in layers:
        if layer['parent'] != parent:
            raise ValueError('Missing/reordered delta')
        parent=apply(root,layer['archive'],layer['id'],parent)
    print('FULL_INCREMENTAL_RESTORE',dict(layers=len(layers),whole_tree_scans=0),flush=True)
    return parent
