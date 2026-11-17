#!/usr/bin/env python3
"""Validate and deterministically repackage the pinned, complete upstream release.
Offline by default; --fetch explicitly downloads only two locked archives.
No extension execution, installation, runtime enablement, or filter updates.
"""
import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path, PurePosixPath
import stat
import zipfile

HERE = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

ARCHIVE = 'uBlock0_1.76.4.chromium.zip'
SOURCE = 'uBlock-3cca944-source.tar.gz'
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024

def materialize(cache_dir, lock_path=HERE / 'lock.json'):
    """Fetch immutable locked URLs explicitly; never overwrite corrupt cache."""
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    lock = json.loads(Path(lock_path).read_text())
    for filename, urlkey, hashkey in [(ARCHIVE, 'archive_url', 'archive_sha256'),
                                      (SOURCE, 'source_url', 'source_archive_sha256')]:
        target = cache / filename
        if target.is_symlink():
            raise ValueError('symlink cache entry refused')
        if target.exists():
            if target.stat().st_size > MAX_ARCHIVE_BYTES or sha(target.read_bytes()) != lock[hashkey]:
                raise ValueError('existing cache digest mismatch: ' + filename)
            continue
        fd, temporary = tempfile.mkstemp(prefix='.ubo-download-', dir=cache)
        os.close(fd)
        temporary = Path(temporary)
        try:
            subprocess.run(['curl', '--fail', '--silent', '--show-error', '--location',
                            '--proto', '=https', '--proto-redir', '=https',
                            '--connect-timeout', '15', '--max-time', '60',
                            '--max-filesize', str(MAX_ARCHIVE_BYTES),
                            '--output', str(temporary), lock[urlkey]],
                           check=True, timeout=65)
            if temporary.stat().st_size > MAX_ARCHIVE_BYTES or sha(temporary.read_bytes()) != lock[hashkey]:
                raise ValueError('download digest mismatch: ' + filename)
            os.link(temporary, target)  # Atomic create, refuses concurrent overwrite.
        finally:
            temporary.unlink(missing_ok=True)
    return cache

def export_corresponding_source(cache_dir, artifact_dir, integration_details,
                                lock_path=HERE / 'lock.json'):
    """Artifact inputs for distribution; caller must supply exact bridge/patch details."""
    lock = json.loads(Path(lock_path).read_text())
    source = Path(cache_dir) / SOURCE
    if source.is_symlink() or sha(source.read_bytes()) != lock['source_archive_sha256']:
        raise ValueError('source archive digest mismatch')
    details = Path(integration_details)
    if not details.is_file() or not details.read_bytes().strip():
        raise ValueError('exact integration patch details required')
    target = Path(artifact_dir)
    target.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(source, target / SOURCE)
    shutil.copyfile(HERE / 'LICENSE.txt', target / 'LICENSE.txt')
    shutil.copyfile(lock_path, target / 'upstream-lock.json')
    shutil.copyfile(HERE / 'README.md', target / 'README.md')
    shutil.copyfile(details, target / 'sandium-integration-details.txt')

def prepare(source, output, lock_path=HERE / 'lock.json', *, cache_dir=None):
    lock = json.loads(Path(lock_path).read_text())
    if Path(source).is_symlink() or Path(source).stat().st_size > MAX_ARCHIVE_BYTES:
        raise ValueError('invalid input archive')
    data = Path(source).read_bytes()
    if sha(data) != lock['archive_sha256']:
        raise ValueError('upstream archive digest mismatch')
    source_archive = Path(cache_dir if cache_dir is not None else Path(source).parent) / SOURCE
    if sha(source_archive.read_bytes()) != lock['source_archive_sha256']:
        raise ValueError('source archive digest mismatch')
    files = {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = set()
        for entry in archive.infolist():
            name = entry.filename
            if name in names:
                raise ValueError('duplicate archive entry')
            names.add(name)
            if not name.startswith(lock['archive_root']):
                raise ValueError('unexpected archive root')
            relative = name[len(lock['archive_root']):]
            if not relative:
                continue
            path = PurePosixPath(relative)
            if path.is_absolute() or '..' in path.parts or '\\' in relative:
                raise ValueError('unsafe archive path')
            mode = entry.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError('symlink in extension bundle')
            if entry.is_dir():
                continue
            if entry.file_size > 32 * 1024 * 1024:
                raise ValueError('oversized member')
            files[relative] = archive.read(entry)
    if {name: sha(data) for name, data in files.items()} != lock['files']:
        raise ValueError('extension file inventory mismatch')
    manifest = json.loads(files['manifest.json'])
    if manifest['version'] != lock['version'] or manifest['manifest_version'] != 2:
        raise ValueError('wrong release version or manifest type')
    required = {'storage', 'tabs', 'webNavigation', 'webRequest', 'webRequestBlocking', '<all_urls>'}
    if not required.issubset(manifest['permissions']):
        raise ValueError('full runtime permissions missing')
    if not any(x.get('run_at') == 'document_start' and x.get('all_frames') for x in manifest['content_scripts']):
        raise ValueError('document-start all-frame runtime missing')
    for name in ['LICENSE.txt', 'background.html', 'js/start.js', 'js/traffic.js', 'js/static-net-filtering.js', 'js/cosmetic-filtering.js', 'assets/assets.json']:
        if name not in files:
            raise ValueError('full runtime member missing: ' + name)
    output = Path(output)
    if output.exists():
        raise ValueError('output already exists; choose a new artifact path')
    output.parent.mkdir(parents=True, exist_ok=True)
    # ZIP_STORED avoids zlib-version-dependent output. Sorted fixed metadata
    # makes output bytes reproducible and strips no upstream files or licenses.
    with output.open('xb') as stream:
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_STORED) as target:
            for name in sorted(files):
                entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                entry.create_system = 3
                entry.external_attr = (stat.S_IFREG | 0o644) << 16
                target.writestr(entry, files[name])
    return {'version': lock['version'], 'source_commit': lock['source_commit'], 'upstream_sha256': lock['archive_sha256'], 'bundle_sha256': sha(output.read_bytes()), 'file_count': len(files), 'runtime_enabled': False}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache-dir', type=Path, required=True)
    parser.add_argument('--fetch', action='store_true')
    parser.add_argument('--input', type=Path)
    parser.add_argument('--source-artifacts', type=Path)
    parser.add_argument('--integration-details', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if bool(args.source_artifacts) != bool(args.integration_details):
        parser.error('--source-artifacts and --integration-details must be supplied together')
    if args.fetch:
        materialize(args.cache_dir)
    receipt = prepare(args.input or args.cache_dir / ARCHIVE, args.output, cache_dir=args.cache_dir)
    if args.source_artifacts:
        export_corresponding_source(args.cache_dir, args.source_artifacts, args.integration_details)
    print(json.dumps(receipt, sort_keys=True))
