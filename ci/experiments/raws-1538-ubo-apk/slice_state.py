"""Workflow-private transfer of the experiment's Siso output only."""
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

def digest(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

def carry(out):
    # Preserve all Siso and Ninja state in this dedicated out directory. The
    # exact filenames evolve; reject a tree with no substantial output at all.
    if not (out/'obj').is_dir() or not any(out.glob('.siso*')):
        raise ValueError('No reusable built objects or Siso state')
    if any(p.is_symlink() and not p.resolve().is_relative_to(out.resolve())
           for p in out.rglob('*')):
        # Avoid carrying external symlinks. GN/rebuild can regenerate them but
        # silently dropping them here would make the snapshot incomplete.
        raise ValueError('Compile output references an out-of-tree symlink')

def save(out, target, identity, status):
    target.mkdir(parents=True,exist_ok=False)
    receipt={**identity,'status':status}
    if status=='slice_expired':
        carry(out)
        archive=target/'output.tar.zst'
        if shutil.disk_usage(target).free < 8*1024**3:
            raise ValueError('Under 8 GiB free for experiment checkpoint')
        subprocess.run(['timeout','--kill-after=30s','7m','tar','--format=pax','--use-compress-program=zstd -1 -T4',
                        '-cf',str(archive),'-C',str(out.parent),out.name],check=True)
        receipt.update(sha256=digest(archive),bytes=archive.stat().st_size)
    (target/'receipt.json').write_text(json.dumps(receipt,sort_keys=True)+'\n')

def receipt_at(target, identity):
    f=target/'receipt.json'
    if f.is_symlink() or not f.is_file():
        raise ValueError('Missing previous experiment slice receipt')
    r=json.loads(f.read_text())
    if any(r.get(k)!=v for k,v in identity.items()):
        raise ValueError('Experiment slice receipt does not match workflow and build inputs')
    if r.get('status') not in ('done','slice_expired'):
        raise ValueError('Previous slice is not resumable')
    return r

def restore(out, target, r, args):
    archive=target/'output.tar.zst'
    if (archive.is_symlink() or not archive.is_file() or
        archive.stat().st_size!=r['bytes'] or digest(archive)!=r['sha256']):
        raise ValueError('Missing or changed experiment checkpoint bytes')
    if sorted(p.name for p in out.iterdir())!=['args.gn']:
        raise ValueError('Existing compile output would obstruct deterministic restore')
    if shutil.disk_usage(out).free < 15*1024**3:
        raise ValueError('Under 15 GiB free to extract experiment checkpoint')
    mtimes={}
    def check(info,path):
        p=Path(info.name)
        if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0]!=out.name:
            raise ValueError('Unsafe experiment archive entry: '+info.name)
        if not (info.isfile() or info.isdir() or info.issym() or info.islnk()):
            raise ValueError('Unsupported experiment archive entry')
        accepted=tarfile.data_filter(info,path)
        if accepted is not None:
            stamp=info.pax_headers.get('mtime',str(info.mtime))
            mtimes[p]=int(Decimal(stamp)*1_000_000_000)
        return accepted
    # Stream the zstd payload through Python's validating tar extractor and
    # retain output mtimes for Siso. Do not extract anything outside this out/.
    with subprocess.Popen(['zstd','-dc',str(archive)],stdout=subprocess.PIPE) as zstd:
        try:
            with tarfile.open(fileobj=zstd.stdout,mode='r|') as tar:
                tar.extractall(out.parent,filter=check)
            while zstd.stdout.read(1024*1024):
                pass
        except BaseException:
            zstd.kill()
            raise
        if zstd.wait()!=0:
            raise ValueError('Experiment checkpoint decompression failed')
    for name,ns in sorted(mtimes.items(), key=lambda item: -len(item[0].parts)):
        file=out.parent/name
        if not file.parent.resolve().is_relative_to(out.parent.resolve()):
            raise ValueError('Unsafe timestamp destination')
        os.utime(file,ns=(file.lstat().st_atime_ns,ns),follow_symlinks=False)
    if (out/'args.gn').read_bytes()!=args:
        raise ValueError('Restored output build args changed')
    carry(out)
