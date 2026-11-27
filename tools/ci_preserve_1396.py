"""Preserve the exact #1396 native CircleCI cache pair; never compile or sign."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import uuid

ROOT = Path.cwd()
ORIGINAL = ROOT / '.raws-final-archive'
RECEIPT = ROOT / '.raws-preserved-1396'
KEY = ROOT / '.preserve-1396-transport.key'
MANIFEST = ROOT / 'raw-workspace-checkpoint.manifest.json'
SHARDS = ROOT / 'raw-workspace-checkpoint.shards'
OLD_RECEIPT = 'd6892b9f3cdfedaedd567b981f7459510877bfc001cd98781b8c9ce1802244e6'
OLD_ID = 'c84a3f88d74b96fc5c8f4b38e3946e85e1a253e1bccc61550f43f59af39c15fe'
BASE_ID = 'd0bf5cf09ce9adf4d176ba8271357f1d22aafa60cc120a54e215d58561b1e631'
MANIFEST_SHA = '38ae30c1610ba11f5d8e23d1d6e6b812678948af628b5a7ed854c10ed928202d'
APK_SHA = '7feb138bacb61dd9f77fca29c579330a2209f1ccd754c5e443962e76a76a977b'
SOURCE = 'e7e782067daef429073e54c2bd8fbb91da7c8439'
OLD_WORKFLOW = 'ceaa5f4e-7a36-4fa1-a5e9-e5633b70bf26'
BRANCH = 'maintenance/raws-1396-preserve'
BYTES = 31_248_194_531
EXPIRY = 1796239322

def need(test, reason):
    if not test:
        raise ValueError(reason)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()

def read_file(path, limit):
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= limit,
         f'Expected regular bounded file: {path.name}')
    return path.read_bytes()

def verify_receipt(folder, now):
    need(folder.is_dir() and not folder.is_symlink(), 'Missing original receipt directory')
    blob = read_file(folder / 'receipt.json', 256 * 1024)
    need(digest(blob) == OLD_RECEIPT, 'Wrong exact receipt bytes')
    receipt = json.loads(blob)
    p = receipt['payload']
    b = p['plan']['base']
    need(receipt['id'] == OLD_ID == digest(encoded(p)), 'Wrong original receipt identity')
    need((p['pipeline'], p['source'], p['workflow']) == (1396, SOURCE, OLD_WORKFLOW),
         'Wrong original producer')
    need(p['apk_verified'] is True and p['apk_sha256'] == APK_SHA, 'Wrong archived APK')
    need(p['plan']['layers'] == [] and p['plan']['head'] == b['id'] == BASE_ID,
         'Wrong base lineage')
    need((b['manifest_sha256'], b['archive_bytes'], b['expires_at']) ==
         (MANIFEST_SHA, BYTES, EXPIRY) and now < EXPIRY, 'Wrong or expired base')
    return blob

def verify_shards():
    blob = read_file(MANIFEST, 1024 * 1024)
    need(digest(blob) == MANIFEST_SHA and digest(b'legacy-base-v1\0'+blob) == BASE_ID,
         'Wrong manifest bytes')
    manifest = json.loads(blob)
    shards = manifest['shards']
    need(SHARDS.is_dir() and not SHARDS.is_symlink(), 'Missing archive shard directory')
    names = [s['name'] for s in shards]
    need(len(names) == len(set(names)) == 8
         and set(names) == {p.name for p in SHARDS.iterdir()}, 'Wrong archive topology')
    need(sum(s['size_bytes'] for s in shards) == BYTES, 'Wrong archive size')
    def verify(shard):
        name = shard['name']
        need(re.fullmatch(r'[\w.-]+', name) and name not in ('.', '..'), 'Unsafe shard name')
        path = SHARDS / name
        need(path.is_file() and not path.is_symlink(), 'Wrong shard file type')
        need(path.stat().st_size == shard['size_bytes'], 'Shard length mismatch')
        with path.open('rb') as f:
            need(hashlib.file_digest(f, 'sha256').hexdigest() == shard['sha256'],
                 'Shard hash mismatch')
        print('PRESERVE_1396_SHARD_VERIFIED', name, shard['size_bytes'], flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(verify, shards))
    return manifest

def identity():
    workflow = str(uuid.UUID(os.environ['CIRCLE_WORKFLOW_ID']))
    return {'workflow': workflow, 'checkout': os.environ['CIRCLE_SHA1'],
            'original_receipt_sha256': OLD_RECEIPT, 'base_id': BASE_ID}

def gate():
    need(os.environ.get('CIRCLE_PROJECT_REPONAME') == 'Sandium-2'
         and os.environ.get('CIRCLE_PROJECT_ID') == 'fd422453-4cc0-4090-a024-b5c53476982f'
         and os.environ.get('CIRCLE_BRANCH') == BRANCH
         and os.environ.get('CIRCLE_JOB') in ('preserve-1396-copy', 'preserve-1396-readback'),
         'Wrong CircleCI project, branch, or job')
    need(subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
         == os.environ['CIRCLE_SHA1'], 'Wrong checkout')
    need(int(time.time()) < EXPIRY, 'Original receipt has expired')

def setup():
    for path in (ORIGINAL, RECEIPT, KEY, MANIFEST, SHARDS, ROOT/'work'):
        need(not path.exists() and not path.is_symlink(), 'Expected clean worker')
    need(shutil.disk_usage(ROOT).free > BYTES + 8*1024**3, 'Insufficient disk for compressed archive')
    KEY.write_bytes(encoded(identity()))

def copy():
    old = verify_receipt(ORIGINAL, int(time.time()))
    verify_shards()
    RECEIPT.mkdir()
    (RECEIPT/'receipt.json').write_bytes(old)
    (RECEIPT/'copy-provenance.json').write_bytes(encoded(dict(identity(),
        copy_job=os.environ['CIRCLE_BUILD_NUM'], logical_expiry=EXPIRY)))
    print('PRESERVE_1396_ORIGINAL_VERIFIED', flush=True)

def readback():
    verify_receipt(RECEIPT, int(time.time()))
    proof = json.loads(read_file(RECEIPT/'copy-provenance.json', 8192))
    need(proof == dict(identity(), copy_job=proof['copy_job'], logical_expiry=EXPIRY)
         and proof['copy_job'] != os.environ['CIRCLE_BUILD_NUM'], 'Not a distinct fresh worker')
    need(not ORIGINAL.exists() and not (ROOT/'work').exists(), 'Readback input was not isolated')
    manifest = verify_shards()
    from final_archive_proof import verify_archived_apk
    apk = verify_archived_apk(manifest, SHARDS, APK_SHA, timeout=300)
    output = ROOT/'preservation-proof.json'
    output.write_bytes(encoded(dict(proof, readback_job=os.environ['CIRCLE_BUILD_NUM'],
        transport_key_sha256=digest(read_file(KEY, 8192)), archive_bytes=BYTES,
        manifest_sha256=MANIFEST_SHA, shard_count=8, archived_apk=apk)))
    print('PRESERVE_1396_FRESH_READBACK_VERIFIED', flush=True)

if __name__ == '__main__':
    gate()
    {'setup': setup, 'original-receipt': lambda: verify_receipt(ORIGINAL, int(time.time())),
     'copy': copy, 'readback': readback}[sys.argv[1]]()
