"""Local legacy-base delta bridge experiment. Trusted, quiescent filesystem only.

No remote cache publication, checkpoint authority, secret policy or CI wiring.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile
import time


_progress = {"bytes": 0, "items": 0}
_last_report = 0

def measured(bytes_done=0,items=0):
    global _last_report
    _progress['bytes'] += bytes_done; _progress['items'] += items
    now=time.monotonic()
    if now-_last_report>=30:
        print('BRIDGE_PROGRESS',_progress,flush=True);_last_report=now


def encode(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':')).encode()


def digest(x):
    return hashlib.sha256(x).hexdigest()


def safe(name):
    if not isinstance(name,str) or not name or name == '.' or '\x00' in name or str(PurePosixPath(name)) != name or name.startswith('/') or '..' in PurePosixPath(name).parts:
        raise ValueError('Unsafe path')


def inventory(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Real source directory required')
    result = {}; groups = {}; last = time.monotonic()
    def visit(directory):
        nonlocal last
        for p in sorted(directory.iterdir()):
            name = p.relative_to(root).as_posix(); safe(name)
            st = p.lstat()
            if os.listxattr(p, follow_symlinks=False):
                raise ValueError('Extended attributes unsupported')
            kind = 'directory' if stat.S_ISDIR(st.st_mode) else 'file' if stat.S_ISREG(st.st_mode) else 'symlink' if stat.S_ISLNK(st.st_mode) else None
            if kind is None:
                raise ValueError('Special files unsupported')
            entry = dict(kind=kind, mode=stat.S_IMODE(st.st_mode), mtime=st.st_mtime_ns,
                         ctime=st.st_ctime_ns, dev=st.st_dev, inode=st.st_ino, size=st.st_size, nlink=st.st_nlink)
            if kind == 'symlink': entry['target'] = os.readlink(p)
            result[name] = entry
            measured(items=1)
            if kind == 'file': groups.setdefault((st.st_dev,st.st_ino),[]).append(name)
            if kind == 'directory': visit(p)
            if time.monotonic()-last >= 30:
                print('BRIDGE_INVENTORY',len(result),flush=True);last=time.monotonic()
    visit(root)
    for names in groups.values():
        if result[names[0]]['nlink'] != len(names):
            raise ValueError('External hardlinks are outside checkpoint scope')
        for name in names: result[name]['links'] = sorted(names)
    print('BRIDGE_INVENTORY_COMPLETE',len(result),flush=True)
    return result


def root_metadata(root):
    st = Path(root).stat()
    return dict(mode=stat.S_IMODE(st.st_mode),mtime=st.st_mtime_ns)


def base_id(manifest_bytes):
    # Identity binds the original verified manifest, including shard digests.
    return digest(b'legacy-base-v1\0'+manifest_bytes)


def begin(root, head, job_id):
    """Call only AFTER verified B+D* restore, BEFORE any preparation/build writers."""
    if not job_id: raise ValueError('Same-job identity required')
    st = Path(root).stat()
    return dict(schema=1, head=head, job=job_id, root=[st.st_dev,st.st_ino], entries=inventory(root))


def public(entry):
    return {k: entry[k] for k in ('kind','mode','mtime','target','links') if k in entry}


def capture(root, before, job_id, destination, quiesce):
    """quiesce must fail if writers remain; caller must prevent new writers."""
    root=Path(root);destination=Path(destination)
    st=root.stat()
    if before['job'] != job_id or before['root'] != [st.st_dev,st.st_ino]:
        raise ValueError('Inventory belongs to another job/restored filesystem')
    if destination.exists():raise ValueError('Immutable destination exists')
    quiesce()
    after=inventory(root); root_meta=root_metadata(root); old=before['entries']
    changed={n for n,e in after.items() if old.get(n)!=e}
    # Preserve hardlink topology, even when only one member was noticed initially.
    for n in list(changed):
        changed.update(after[n].get('links',[]))
    entries={n:public(after[n]) for n in sorted(changed)}
    removed=sorted(set(old)-set(after))
    destination.parent.mkdir(parents=True,exist_ok=True)
    needed=sum(after[n]['size'] for n in changed if after[n]['kind']=='file' and after[n]['links'][0]==n)
    required=needed+len(encode(entries))+len(entries)*256+32*1024**2
    free=shutil.disk_usage(destination.parent).free
    print('BRIDGE_CAPTURE_DISK',dict(free=free,required=required),flush=True)
    if free<required:raise ValueError('Insufficient delta archive space')
    fd,tmp=tempfile.mkstemp(prefix='.delta-',dir=destination.parent);os.close(fd)
    hashed=0;count=0
    try:
        with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
            for n,e in entries.items():
                measured(items=1)
                if e['kind']!='file':continue
                leader=e['links'][0]
                if n!=leader:continue
                h=hashlib.sha256();size=0
                # Filename is a digest of path, independent of attacker-controlled path syntax.
                blob='data/'+digest(n.encode())
                with (root/n).open('rb') as f,z.open(blob,'w',force_zip64=True) as out:
                    while chunk:=f.read(1024*1024):
                        out.write(chunk);h.update(chunk);size+=len(chunk);hashed+=len(chunk)
                        measured(bytes_done=len(chunk))
                e.update(blob=blob,sha256=h.hexdigest(),size=size);count+=1;measured(items=1)
            manifest=dict(schema=1,parent=before['head'],entries=entries,deleted=removed,root_metadata=root_meta)
            z.writestr('manifest.json',encode(manifest))
        quiesce()
        if inventory(root)!=after or root_metadata(root)!=root_meta:raise ValueError('Source changed while capturing')
        # Exact archive identity authenticates ordered delta composition.
        h=hashlib.sha256()
        with open(tmp,'rb') as f:
            while chunk:=f.read(1024*1024):h.update(chunk);measured(bytes_done=len(chunk))
        ident=h.hexdigest()
        with open(tmp,'rb') as f:os.fsync(f.fileno())
        os.link(tmp,destination) # no replacement of an existing immutable object
        print('BRIDGE_CAPTURE',dict(changed=len(entries),deleted=len(removed),hashed_bytes=hashed,files=count),flush=True)
        return dict(parent=before['head'],id=ident,hashed_bytes=hashed,changed=len(entries))
    finally:
        os.unlink(tmp)


def _apply(root, archive, expected_id, parent, prior=None):
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
        entries=m['entries'];deleted=m['deleted']
        for name in set(entries)|set(deleted):safe(name)
        # Validate full target topology BEFORE touching disk, never traverse symlink parents.
        if prior is None:
            prior=inventory(root)
        target={n:public(e) for n,e in prior.items() if n not in deleted};target.update(entries)
        expected_members={'manifest.json'}
        for n,e in target.items():
            measured(items=1)
            for p in PurePosixPath(n).parents:
                if str(p)!='.' and target.get(str(p),{}).get('kind')!='directory':raise ValueError('Non-directory parent')
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
                if n not in prior:continue # never traverse an old symlink ancestor for new children
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
            metadata = {n:e for n,e in target.items() if e['kind']=='directory'}
            metadata.update(entries)
            for n,e in sorted(metadata.items(),key=lambda item:len(PurePosixPath(item[0]).parts),reverse=True):
                measured(items=1)
                p=root/n
                if e['kind']!='symlink':os.chmod(p,e['mode'])
                os.utime(p,ns=(e['mtime'],e['mtime']),follow_symlinks=False)
            os.chmod(root,m['root_metadata']['mode'])
            stamp=m['root_metadata']['mtime'];os.utime(root,ns=(stamp,stamp))
        finally:shutil.rmtree(stage)
    return expected_id, target, m['root_metadata']


def apply(root, archive, expected_id, parent):
    """Standalone delta application retains its independent initial inventory."""
    return _apply(root, archive, expected_id, parent)[0]


def apply_chain(root, layers, parent):
    """Restore a verified ordered chain on one disposable, writer-free tree.

    Carry only topology in memory, never inode/ctime capture metadata. Verify the
    actual final filesystem independently before accepting reconstruction. This
    is not a persisted inventory cache and must not be used by capture/begin.
    """
    if len(layers) <= 1:
        for layer in layers:
            if layer['parent'] != parent:
                raise ValueError('Missing/reordered delta')
            parent=apply(root,layer['archive'],layer['id'],parent)
        return parent
    prior=None
    for layer in layers:
        if layer['parent'] != parent:
            raise ValueError('Missing/reordered delta')
        parent,prior,expected_root=_apply(root,layer['archive'],layer['id'],parent,prior)
    # Recheck real topology, unsupported metadata and external hardlinks. No
    # writers may run during restore; publication still requires complete success.
    actual=inventory(root)
    if ({n:public(e) for n,e in actual.items()} !=
            {n:public(e) for n,e in prior.items()} or root_metadata(root)!=expected_root):
        raise ValueError('Restored chain filesystem metadata mismatch')
    print('BRIDGE_CHAIN_INVENTORIES',dict(layers=len(layers),scans=2),flush=True)
    return parent
