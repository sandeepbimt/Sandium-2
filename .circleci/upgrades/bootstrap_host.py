#!/usr/bin/env python3
"""Owned local Node/pnpm toolchain, no global package manager configuration.

Caller owns overall deadline/process cleanup. Downloads are independently pinned;
existing installs are integrity-checked before capability/version reuse.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request

NODE_VERSION = 'v24.16.0'
PNPM_VERSION = '11.11.0'
SOURCES = {
    'node': {
        'url': 'https://nodejs.org/dist/v24.16.0/node-v24.16.0-linux-x64.tar.xz',
        'sha256': 'd804845d34eddc21dc1092b519d643ef40b1f58ec5dec5c22b1f4bd8fabde6c9',
        'max_bytes': 100 * 1024**2,
    },
    'pnpm': {
        'url': 'https://github.com/pnpm/pnpm/releases/download/v11.11.0/pnpm-linux-x64.tar.gz',
        'sha256': 'df4699e897012ab14df2cc6eaa942910e830eb7fcaa420a2a1421a9461fd9108',
        'max_bytes': 200 * 1024**2,
    },
}
IDENTITY = {'schema': 2, 'node': NODE_VERSION, 'pnpm': PNPM_VERSION,
            'archives': {key: item['sha256'] for key, item in SOURCES.items()}}


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def download(name, destination):
    item = SOURCES[name]
    request = urllib.request.Request(item['url'], headers={'User-Agent': 'Sandium-pinned-host-bootstrap'})
    total = 0
    with urllib.request.urlopen(request, timeout=30) as response, Path(destination).open('xb') as f:
        while block := response.read(1024 * 1024):
            total += len(block)
            if total > item['max_bytes']:
                raise ValueError('Oversized pinned host archive: ' + name)
            f.write(block)
    if digest(destination) != item['sha256']:
        raise ValueError('Pinned host archive checksum mismatch: ' + name)


def extract(path, destination):
    # Python's data filter rejects traversal, device entries and escaping links.
    # Bound inflated size as well as transport bytes before any extraction.
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        if sum(member.size for member in members) > 1024**3:
            raise ValueError('Oversized extracted host archive')
        archive.extractall(destination, members=members, filter='data')


def inventory(root):
    entries = {}
    for path in sorted(Path(root).rglob('*')):
        name = path.relative_to(root).as_posix()
        if name == 'installed.json':
            continue
        if path.is_symlink():
            if not path.resolve().is_relative_to(root):
                raise ValueError('Escaping host tool link')
            entries[name] = {'link': os.readlink(path)}
        elif path.is_file():
            entries[name] = {'sha256': digest(path), 'executable': bool(path.stat().st_mode & 0o111)}
        elif not path.is_dir():
            raise ValueError('Special host tool entry')
    return entries


def capabilities(root):
    for relative, expected in (('node/bin/node', NODE_VERSION), ('bin/pnpm', PNPM_VERSION)):
        path = root / relative
        if not path.is_file() or path.is_symlink() or not os.access(path, os.X_OK):
            raise ValueError('Missing host executable: ' + relative)
        result = subprocess.check_output([str(path), '--version'], text=True, timeout=15).strip()
        if result != expected:
            raise ValueError('Wrong host capability: ' + relative)


def verify(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Host install must be a real owned directory')
    marker = root / 'installed.json'
    if marker.is_symlink() or not marker.is_file():
        raise ValueError('Host install lacks completed ownership record')
    receipt = json.loads(marker.read_text())
    if receipt.get('identity') != IDENTITY or receipt.get('files') != inventory(root):
        raise ValueError('Host install integrity mismatch')
    capabilities(root)
    return {'node': NODE_VERSION, 'pnpm': PNPM_VERSION,
            'path': str(root/'bin') + os.pathsep + str(root/'node/bin'), 'reused': True}


def install(root):
    root = Path(root).absolute()
    if root.exists() or root.is_symlink():
        return verify(root)  # Never repair/delete an unknown existing runtime.
    if not root.parent.is_dir():
        raise ValueError('Host install parent must already exist')
    if shutil.disk_usage(root.parent).free < 2 * 1024**3:
        raise ValueError('Insufficient host bootstrap disk reserve')
    with tempfile.TemporaryDirectory(prefix='.full-u-host-', dir=root.parent) as temporary:
        temporary = Path(temporary)
        stage = temporary/'runtime';stage.mkdir()
        for name in SOURCES:
            download(name, temporary/(name+'.archive'))
            extract(temporary/(name+'.archive'), temporary/name)
        node_parent = temporary/'node'
        expected = node_parent/('node-'+NODE_VERSION+'-linux-x64')
        if sorted(x.name for x in node_parent.iterdir()) != [expected.name] or not expected.is_dir() or expected.is_symlink():
            raise ValueError('Unexpected Node archive layout')
        expected.rename(stage/'node')
        # Official standalone tar may include a containing directory, but it
        # must provide exactly one regular named pnpm binary; never npm install.
        binaries = [p for p in (temporary/'pnpm').rglob('*') if p.name in ('pnpm', 'pnpm-linux-x64') and p.is_file()]
        if len(binaries) != 1 or binaries[0].is_symlink() or not os.access(binaries[0], os.X_OK):
            raise ValueError('Unexpected standalone pnpm archive layout')
        relative = binaries[0].relative_to(temporary/'pnpm').as_posix()
        if not re.fullmatch(r'[A-Za-z0-9_./-]+', relative):
            raise ValueError('Unexpected pnpm executable path')
        # Official pnpm11 executable loads adjacent dist/pnpm.mjs. Preserve
        # the entire hash-authenticated payload, not just its launcher.
        (temporary/'pnpm').rename(stage/'pnpm')
        (stage/'bin').mkdir()
        launcher = stage/'bin/pnpm'
        launcher.write_text('#!/bin/sh\nexec "$(dirname "$0")/../pnpm/' + relative + '" "$@"\n')
        launcher.chmod(0o755)
        capabilities(stage)
        (stage/'installed.json').write_text(json.dumps({'identity': IDENTITY, 'files': inventory(stage)}, sort_keys=True)+'\n')
        if root.exists() or root.is_symlink():
            raise ValueError('Host install destination collision')
        stage.rename(root)
    result = verify(root);result['reused'] = False
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('install', 'verify'))
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps((install if args.action == 'install' else verify)(args.root), sort_keys=True))
