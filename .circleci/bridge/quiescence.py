"""Scoped post-build quiescence, not blanket process termination."""
import json
import os
from pathlib import Path
import stat
import time


def inspect_writers(work):
    """Inspect every FD, so an unlinked log cannot hide a second live writer.

    An unlinked regular inode with nlink=0 is not part of the captured tree. Do not
    confuse it with a still-linked inode or merely infer safety from '(deleted)'.
    """
    work=Path(work).resolve();proc=Path('/proc');live=[];unlinked=[]
    if not proc.is_dir():raise ValueError('/proc unavailable; quiescence cannot be checked')
    for process in proc.iterdir():
        if not process.name.isdigit():continue
        try:descriptors=list((process/'fd').iterdir())
        except (FileNotFoundError,ProcessLookupError,PermissionError):continue
        for fd in descriptors:
            try:raw=os.readlink(fd)
            except (FileNotFoundError,ProcessLookupError,PermissionError):continue
            target=raw[:-10] if raw.endswith(' (deleted)') else raw
            if not os.path.isabs(target):continue
            try:
                if os.path.commonpath((str(work),os.path.normpath(target)))!=str(work):continue
            except ValueError:continue
            try:
                info=(process/'fdinfo'/fd.name).read_text()
                flags_line=next(line for line in info.splitlines() if line.startswith('flags:'))
                flags=int(flags_line.split(':',1)[1].strip(),8)
                if flags&os.O_ACCMODE==os.O_RDONLY:continue
                inode=fd.stat()
            except (FileNotFoundError,ProcessLookupError):continue
            except (PermissionError,ValueError,StopIteration) as exc:
                raise ValueError('Cannot inspect candidate workspace writer pid='+process.name) from exc
            try:command=(process/'comm').read_text().strip()
            except OSError:command='<unavailable>'
            try:executable=Path(os.readlink(process/'exe')).name
            except OSError:executable='<unavailable>'
            # Never log argv or environment, which may contain credentials.
            record=dict(pid=int(process.name),fd=int(fd.name),command=command,executable=executable,
                        path=os.path.relpath(target,work),inode=inode.st_ino,links=inode.st_nlink)
            if stat.S_ISREG(inode.st_mode) and inode.st_nlink==0:unlinked.append(record)
            else:live.append(record)
    return live,unlinked


def report(label,live,unlinked):
    print('FLOW_QUIESCENCE '+json.dumps(dict(phase=label,live_count=len(live),unlinked_count=len(unlinked),
        live=live[:20],unlinked=unlinked[:20])),flush=True)


def ensure_quiescent(work,legacy_module,settle_seconds=2.0):
    live,unlinked=inspect_writers(work);report('before-shutdown',live,unlinked)
    # Preserve the proven original narrow lifecycle action: only this workspace's
    # fast_local_dev_server.py with --exit-on-idle. No generic pkill/SIGKILL.
    try:legacy_module.stop_idle_build_servers(Path(work),timeout=10.0)
    except Exception:
        # Legacy exception includes raw argv. Replace it with sanitized FD records.
        live,unlinked=inspect_writers(work);report('shutdown-failed',live,unlinked)
        raise ValueError('Scoped Android build-server shutdown failed; checkpoint refused') from None
    deadline=time.monotonic()+settle_seconds
    while True:
        live,unlinked=inspect_writers(work)
        if not live:report('verified',live,unlinked);return
        if time.monotonic()>=deadline:
            report('blocked',live,unlinked)
            raise ValueError('Live workspace writers remain; checkpoint refused')
        time.sleep(min(0.1,max(0,deadline-time.monotonic())))
