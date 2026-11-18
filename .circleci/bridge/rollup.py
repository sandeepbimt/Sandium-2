"""Consolidate verified delta archives without reading the legacy base.

Inputs are immutable ordered archives whose expected IDs come from the accepted
checkpoint descriptor. Hashes prove integrity, not publisher authorization.
"""
import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import zipfile

from bridge import digest, encode, measured, safe


def path_check(name):
    if not isinstance(name, str) or name == '.' or '\x00' in name:
        raise ValueError('Unsafe path')
    safe(name)


def fingerprint(path):
    st = Path(path).lstat()
    if not stat.S_ISREG(st.st_mode): raise ValueError('Regular immutable archive required')
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def archive_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk); measured(bytes_done=len(chunk))
    return h.hexdigest()


def validate_manifest(z, parent):
    names = z.namelist()
    if len(names) != len(set(names)):
        raise ValueError('Duplicate archive members')
    m = json.loads(z.read('manifest.json'))
    if m.get('schema') != 1 or m.get('parent') != parent:
        raise ValueError('Wrong ordered parent')
    entries, deleted = m['entries'], m['deleted']
    if not isinstance(entries, dict) or not isinstance(deleted, list) or len(deleted) != len(set(deleted)):
        raise ValueError('Invalid delta paths')
    if set(entries) & set(deleted):
        raise ValueError('Entry also deleted')
    for n in set(entries) | set(deleted): path_check(n)
    rm = m['root_metadata']
    if not isinstance(rm.get('mode'), int) or not 0 <= rm['mode'] <= 0o7777 or not isinstance(rm.get('mtime'), int):
        raise ValueError('Invalid root metadata')
    expected = {'manifest.json'}
    for n, e in entries.items():
        measured(items=1)
        if e.get('kind') not in ('file', 'directory', 'symlink'):
            raise ValueError('Bad kind')
        if not isinstance(e.get('mode'), int) or not 0 <= e['mode'] <= 0o7777 or not isinstance(e.get('mtime'), int):
            raise ValueError('Invalid metadata')
        if e['kind'] == 'symlink' and (not isinstance(e.get('target'), str) or '\x00' in e['target']):
            raise ValueError('Invalid symlink')
        if e['kind'] != 'file': continue
        links = e['links']
        if not isinstance(links, list) or not links or n not in links or links != sorted(set(links)):
            raise ValueError('Bad link group')
        for member in links:
            path_check(member)
            other = entries.get(member, {})
            if other.get('kind') != 'file' or other.get('links') != links or (other.get('mode'), other.get('mtime')) != (e['mode'], e['mtime']):
                raise ValueError('Incomplete/inconsistent link group')
        if n == links[0]:
            if e.get('blob') != 'data/' + digest(n.encode()) or not re.fullmatch('[0-9a-f]{64}', e.get('sha256', '')) or not isinstance(e.get('size'), int) or e['size'] < 0:
                raise ValueError('Invalid payload declaration')
            expected.add(e['blob'])
    if set(names) != expected:
        raise ValueError('Unexpected/missing archive members')
    return m


def rollup(base_head, layers, destination):
    """layers: ordered {path (or archive), id} records. Never reads base content."""
    if not isinstance(base_head, str) or not base_head or not layers:
        raise ValueError('Base identity and nonempty chain required')
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise ValueError('Immutable destination exists')
    destination.parent.mkdir(parents=True, exist_ok=True)
    entries, deleted, sources = {}, set(), {}
    previous = base_head
    inputs = []
    tmp = None
    with contextlib.ExitStack() as stack:
        for spec in layers:
            archive = Path(spec.get('path', spec.get('archive', '')))
            expected = spec['id']
            initial = fingerprint(archive)
            if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected) or archive_hash(archive) != expected:
                raise ValueError('Corrupt delta archive')
            if fingerprint(archive) != initial: raise ValueError('Archive changed during verification')
            inputs.append((archive, initial))
            z = stack.enter_context(zipfile.ZipFile(archive))
            m = validate_manifest(z, previous)
            for n in m['deleted']:
                entries.pop(n, None); sources.pop(n, None); deleted.add(n)
            for n, e in m['entries'].items():
                entries[n] = dict(e); sources[n] = z; deleted.discard(n)
            root_meta = dict(m['root_metadata'])
            previous = expected
        # Validate all known topology. Unknown parents may legitimately be in B.
        for n, e in entries.items():
            for p in PurePosixPath(n).parents:
                p = str(p)
                if p == '.': continue
                if p in deleted or (p in entries and entries[p]['kind'] != 'directory'):
                    raise ValueError('Non-directory final parent')
            if e['kind'] == 'file':
                for member in e['links']:
                    other = entries.get(member, {})
                    if other.get('kind') != 'file' or other.get('links') != e['links'] or (other.get('mode'), other.get('mtime')) != (e['mode'], e['mtime']):
                        raise ValueError('Incomplete final hardlink group')
        needed = sum(e['size'] for n, e in entries.items() if e['kind'] == 'file' and n == e['links'][0])
        required = needed + len(encode(entries)) + len(entries) * 256 + 32 * 1024**2
        if shutil.disk_usage(destination.parent).free < required:
            raise ValueError('Insufficient rollup archive space')
        fd, tmp = tempfile.mkstemp(prefix='.rollup-', dir=destination.parent); os.close(fd)
        copied = 0
        try:
            with zipfile.ZipFile(tmp, 'w', compression=zipfile.ZIP_STORED, allowZip64=True) as out:
                for n, e in sorted(entries.items()):
                    measured(items=1)
                    if e['kind'] != 'file' or n != e['links'][0]: continue
                    h = hashlib.sha256(); size = 0
                    with sources[n].open(e['blob']) as src, out.open(e['blob'], 'w', force_zip64=True) as dst:
                        while chunk := src.read(1024 * 1024):
                            size += len(chunk)
                            if size > e['size']: raise ValueError('Oversized blob')
                            dst.write(chunk); h.update(chunk); measured(bytes_done=len(chunk))
                    if size != e['size'] or h.hexdigest() != e['sha256']:
                        raise ValueError('Bad surviving blob')
                    copied += size
                manifest = dict(schema=1, tombstones_idempotent=True, parent=base_head, entries=entries, deleted=sorted(deleted), root_metadata=root_meta)
                out.writestr('manifest.json', encode(manifest))
            for source, initial in inputs:
                if fingerprint(source) != initial: raise ValueError('Input changed during rollup')
            ident = archive_hash(tmp)
            with open(tmp, 'rb') as f: os.fsync(f.fileno())
            os.link(tmp, destination)  # fail, never overwrite concurrent publication
            print('BRIDGE_ROLLUP', dict(layers=len(layers), changed=len(entries), deleted=len(deleted), content_bytes=copied), flush=True)
            return dict(parent=base_head, id=ident, changed=len(entries), deleted=len(deleted), hashed_bytes=copied, layers=len(layers))
        finally:
            if tmp is not None: os.unlink(tmp)
