"""Workflow-private transfer of the experiment's Siso output only."""
from decimal import Decimal
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import tarfile

def digest(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

SISO_LOG_NAMES = {f'siso.{level}' for level in ('INFO', 'WARNING', 'ERROR', 'FATAL')}

def transient_log(out, p):
    if p.parent != out or p.name not in SISO_LOG_NAMES or not p.is_symlink():
        return False
    raw = Path(os.readlink(p))
    level = p.suffix[1:]
    return raw.parent == Path('/tmp') and re.fullmatch(
        rf'siso\.[^/]+\.log\.{level}\.\d{{8}}-\d{{6}}\.\d+', raw.name) is not None

def outside_links(out, source):
    # Chromium can generate links to checkout files from its output tree.
    # Transfer those links as validated metadata, never as tar entries.
    links, ignored_logs = [], []
    for p in sorted(out.rglob('*')):
        if not p.is_symlink():
            continue
        if transient_log(out, p):
            ignored_logs.append(p.name)
            continue
        target = p.resolve()
        if target.is_relative_to(out) and not Path(os.readlink(p)).is_absolute():
            continue
        if not target.is_relative_to(source) or not target.exists():
            raise ValueError(f'Unsupported output symlink: {p.relative_to(out)} -> {os.readlink(p)}')
        links.append(dict(path=p.relative_to(out).as_posix(), link=os.readlink(p),
                          target=target.relative_to(source).as_posix(),
                          mtime_ns=p.lstat().st_mtime_ns))
    return links, ignored_logs

def carry(out):
    if not (out/'obj').is_dir() or not any(out.glob('.siso*')):
        raise ValueError('No reusable built objects or Siso state')

def save(out, target, identity, status, source):
    out, source = out.resolve(), source.resolve()
    if not out.is_relative_to(source):
        raise ValueError('Build output is not below the checkout root')
    target.mkdir(parents=True,exist_ok=False)
    receipt={**identity,'status':status}
    if status=='slice_expired':
        carry(out)
        links, ignored_logs=outside_links(out,source)
        archive=target/'output.tar.zst'
        if shutil.disk_usage(target).free < 8*1024**3:
            raise ValueError('Under 8 GiB free for experiment checkpoint')
        exclude=['--exclude='+out.name+'/'+name for name in [*ignored_logs, *(link['path'] for link in links)]]
        if ignored_logs:
            print('EXPERIMENT_CHECKPOINT_IGNORED_RUNNER_LOGS='+','.join(ignored_logs),flush=True)
        print(f'EXPERIMENT_CHECKPOINT_CHECKOUT_LINKS={len(links)}',flush=True)
        subprocess.run(['timeout','--kill-after=30s','7m','tar','--format=pax','--use-compress-program=zstd -1 -T4',
                        '-cf',str(archive),'--no-wildcards',*exclude,'-C',str(out.parent),out.name],check=True)
        receipt.update(sha256=digest(archive),bytes=archive.stat().st_size,checkout_links=links)
    (target/'receipt.json').write_text(json.dumps(receipt,sort_keys=True)+'\n')

def relative_path(value):
    p=Path(value)
    if p.is_absolute() or '..' in p.parts or not p.parts:
        raise ValueError('Invalid checkout symlink metadata path')
    return p

def restore_checkout_links(out, source, links):
    # Check all metadata against the freshly restored checkout before making
    # any symlinks, and only inside the dedicated output directory.
    entries={}
    for spec in links:
        rel=relative_path(spec['path'])
        path=out/rel
        target=source/relative_path(spec['target'])
        original=spec['link']
        if (path in entries or path.exists() or path.is_symlink()
                or not path.parent.is_dir() or path.parent.resolve()!=path.parent
                or not target.exists() or target.resolve()!=target
                or (path.parent/original).resolve()!=target):
            raise ValueError(f'Unsafe or changed restored checkout link: {rel}')
        entries[path]=spec
    parents={p.parent:p.parent.stat() for p in entries}
    for path,spec in entries.items():
        path.symlink_to(spec['link'])
        os.utime(path,ns=(path.lstat().st_atime_ns,spec['mtime_ns']),follow_symlinks=False)
    for path,st in parents.items():
        os.utime(path,ns=(st.st_atime_ns,st.st_mtime_ns))

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

def restore(out, target, r, args, source):
    out, source=out.resolve(),source.resolve()
    if not out.is_relative_to(source):
        raise ValueError('Build output is not below the checkout root')
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
        if ((p==Path(out.name) and not info.isdir()) or
                not (out.parent/p).parent.resolve().is_relative_to(out)
                and p!=Path(out.name)):
            raise ValueError('Checkpoint attempts to write outside its output tree')
        if info.issym():
            if Path(info.linkname).is_absolute() or not ((out.parent/p).parent/info.linkname).resolve().is_relative_to(out):
                raise ValueError('Unexpected external symlink in archive')
        if info.islnk() and not (out.parent/relative_path(info.linkname)).resolve().is_relative_to(out):
            raise ValueError('Unexpected external hardlink in archive')
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
    restore_checkout_links(out,source,r['checkout_links'])
