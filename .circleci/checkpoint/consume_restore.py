"""Restore a quiescent downloaded blob set without duplicating unique file bytes.

Caller must delete input blob/payload links BEFORE allowing build writers. Shared
content paths inside the restored tree get independent copies, never shared inodes.
"""
from progress import advance
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
from checkpoint import CheckpointError, scan, verify_blob


def copy_measured(source, target):
    """Bound each copy operation so large duplicate files report real work."""
    with source.open("rb") as src, target.open("xb") as dst:
        while chunk := src.read(1024 * 1024):
            dst.write(chunk)
            advance(bytes_done=len(chunk))


def restore_consuming(store, head, compatibility, destination):
    destination = Path(destination)
    if destination.exists() or destination.is_symlink():
        raise CheckpointError("Destination exists")
    entries = store.reconstruct(head, compatibility)
    advance(phase="restore-verify-inputs")
    seen = set()
    duplicate_bytes = 0
    for entry in entries.values():
        if entry["kind"] == "file":
            verify_blob(store.path / "blobs" / entry["blob"], entry)
            if entry["blob"] in seen:
                duplicate_bytes += entry["size"]
            seen.add(entry["blob"])
        advance(items=1)
    free = shutil.disk_usage(destination.parent).free
    print(f"FLOW_RESTORE_DISK free={free} duplicate_bytes={duplicate_bytes} reserve={32 * 1024**2}", flush=True)
    if free < duplicate_bytes + 32 * 1024**2:
        raise CheckpointError("Insufficient space for independent duplicate-content paths")
    stage = Path(tempfile.mkdtemp(prefix=".flow-restore-", dir=destination.parent))
    linked = set()
    try:
        advance(phase="restore-materialize")
        for name, entry in sorted(entries.items(), key=lambda kv:(len(PurePosixPath(kv[0]).parts), kv[0])):
            path = stage / name
            if entry["kind"] == "directory":
                path.mkdir()
            elif entry["kind"] == "symlink":
                os.symlink(entry["target"], path)
            elif entry["blob"] not in linked:
                os.link(store.path / "blobs" / entry["blob"], path)
                linked.add(entry["blob"])
            else:
                copy_measured(store.path / "blobs" / entry["blob"], path)
            advance(items=1)
        advance(phase="restore-metadata")
        for name, entry in sorted(entries.items(), key=lambda kv:len(PurePosixPath(kv[0]).parts), reverse=True):
            path = stage / name
            if entry["kind"] != "symlink":
                os.chmod(path, entry["mode"])
            os.utime(path, ns=(entry["mtime_ns"],entry["mtime_ns"]),follow_symlinks=False)
            advance(items=1)
        if scan(stage) != entries:
            raise CheckpointError("Reconstructed state differs")
        os.rename(stage,destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
