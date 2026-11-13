#!/usr/bin/env python3
"""Local proof of concept. Not a CircleCI storage adapter or production backup."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile


class CheckpointError(Exception):
    pass


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def valid_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise CheckpointError("Invalid object ID")
    return value


def valid_path(value):
    p = PurePosixPath(value)
    if not value or p.is_absolute() or ".." in p.parts or str(p) != value or value == ".":
        raise CheckpointError("Unsafe relative path")


def fingerprint(st):
    return (st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_mode)


def scan(root, store=None):
    """Caller MUST stop all writers. Double scan detects, but cannot prevent, races."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise CheckpointError("Source must be a real directory")
    entries = {}
    def visit(directory):
        for p in sorted(directory.iterdir()):
            name = p.relative_to(root).as_posix()
            valid_path(name)
            before = p.lstat()
            if os.listxattr(p, follow_symlinks=False):
                raise CheckpointError("Extended attributes unsupported: " + name)
            meta = {"mode": stat.S_IMODE(before.st_mode), "mtime_ns": before.st_mtime_ns}
            if stat.S_ISLNK(before.st_mode):
                meta.update(kind="symlink", target=os.readlink(p))
            elif stat.S_ISDIR(before.st_mode):
                meta.update(kind="directory")
                visit(p)
            elif stat.S_ISREG(before.st_mode):
                # Streaming avoids holding multi-gigabyte shared libraries in RAM.
                h = hashlib.sha256()
                tmp = None
                if store:
                    fd, tmp = tempfile.mkstemp(dir=store / "blobs")
                    output = os.fdopen(fd, "wb")
                else:
                    output = contextlib.nullcontext()
                try:
                    with output as out, p.open("rb") as source:
                        while chunk := source.read(1024 * 1024):
                            h.update(chunk)
                            if out:
                                out.write(chunk)
                        if out:
                            out.flush()
                            os.fsync(out.fileno())
                    meta.update(kind="file", blob=h.hexdigest(), size=before.st_size)
                    if tmp:
                        target = store / "blobs" / meta["blob"]
                        if target.exists():
                            verify_blob(target, meta)
                        else:
                            os.link(tmp, target)  # immutable publication
                finally:
                    if tmp and os.path.exists(tmp):
                        os.unlink(tmp)
            else:
                raise CheckpointError("Special file unsupported: " + name)
            if fingerprint(before) != fingerprint(p.lstat()):
                raise CheckpointError("Source changed during capture: " + name)
            entries[name] = meta
    visit(root)
    return entries


def verify_blob(path, entry):
    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            while chunk := f.read(1024 * 1024):
                h.update(chunk)
        if h.hexdigest() != entry["blob"] or path.stat().st_size != entry["size"]:
            raise CheckpointError("Corrupt blob")
    except FileNotFoundError as exc:
        raise CheckpointError("Missing blob") from exc


def atomic_json(path, value):
    fd, temp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(encoded(value))
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
        fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


class Store:
    def __init__(self, path):
        self.path = Path(path).resolve()
        for sub in ("blobs", "manifests", "refs"):
            (self.path / sub).mkdir(parents=True, exist_ok=True)

    def ref_path(self, name):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in (".", ".."):
            raise CheckpointError("Unsafe reference name")
        return self.path / "refs" / name

    def head(self, name):
        path = self.ref_path(name)
        return json.loads(path.read_text())["head"] if path.exists() else None

    def reconstruct(self, head, compatibility):
        chain, seen = [], set()
        current = head
        while current:
            valid_id(current)
            if current in seen or len(seen) >= 1000:
                raise CheckpointError("Invalid or excessive chain")
            seen.add(current)
            try:
                raw = (self.path / "manifests" / current).read_bytes()
            except FileNotFoundError as exc:
                raise CheckpointError("Missing layer") from exc
            if digest(raw) != current:
                raise CheckpointError("Corrupt manifest")
            layer = json.loads(raw)
            if layer["schema"] != 1 or layer["compatibility"] != compatibility:
                raise CheckpointError("Incompatible checkpoint")
            chain.append(layer)
            current = layer["parent"]
        entries = {}
        for layer in reversed(chain):
            for name in layer["deleted"]:
                valid_path(name)
                if name not in entries:
                    raise CheckpointError("Invalid deletion")
                del entries[name]
            for name, entry in layer["changed"].items():
                valid_path(name)
                if entry["kind"] not in ("file", "directory", "symlink"):
                    raise CheckpointError("Invalid entry type")
                if entry["kind"] == "file":
                    valid_id(entry["blob"])
                entries[name] = entry
            if digest(encoded(entries)) != layer["state_hash"]:
                raise CheckpointError("State hash mismatch")
        for name in entries:
            for parent in PurePosixPath(name).parents:
                if str(parent) != "." and entries.get(str(parent), {}).get("kind") != "directory":
                    raise CheckpointError("Entry parent is not a directory")
        return entries

    def capture(self, source, ref, compatibility, expected_parent, revision, fail_before_publish=False):
        source = Path(source).resolve()
        if source == self.path or source in self.path.parents:
            raise CheckpointError("Store cannot be inside source")
        # Local-only CAS lock. Distributed storage needs real conditional publication.
        with (self.path / "publish.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if self.head(ref) != expected_parent:
                raise CheckpointError("Reference advanced; stale writer rejected")
            old = self.reconstruct(expected_parent, compatibility)
            before_blobs = set(p.name for p in (self.path / "blobs").iterdir())
            new = scan(source, self.path)
            if scan(source) != new:
                raise CheckpointError("Source changed during capture")
            changed = {k: v for k, v in new.items() if old.get(k) != v}
            deleted = sorted(old.keys() - new.keys())
            layer = {"schema": 1, "parent": expected_parent, "compatibility": compatibility,
                     "revision": revision, "changed": changed, "deleted": deleted,
                     "state_hash": digest(encoded(new))}
            raw = encoded(layer)
            ident = digest(raw)
            target = self.path / "manifests" / ident
            if not target.exists():
                atomic_json(target, layer)
            for e in new.values():
                if e["kind"] == "file":
                    verify_blob(self.path / "blobs" / e["blob"], e)
            if fail_before_publish:
                raise CheckpointError("Simulated interruption before publication")
            atomic_json(self.ref_path(ref), {"head": ident})
            uploaded = [p for p in (self.path / "blobs").iterdir() if p.name not in before_blobs]
            return {"head": ident, "changed_entries": len(changed), "deleted_entries": len(deleted),
                    "new_blob_bytes": sum(p.stat().st_size for p in uploaded), "manifest_bytes": len(raw)}

    def restore(self, head, compatibility, destination):
        destination = Path(destination).absolute()
        if destination.exists() or destination.is_symlink():
            raise CheckpointError("Destination must not exist")
        entries = self.reconstruct(head, compatibility)
        for e in entries.values():
            if e["kind"] == "file":
                verify_blob(self.path / "blobs" / e["blob"], e)
        destination.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".checkpoint-restore-", dir=destination.parent))
        try:
            # Directories first; no entry may descend through a symlink.
            for name, e in sorted(entries.items(), key=lambda kv: (len(PurePosixPath(kv[0]).parts), kv[0])):
                p = stage / name
                if e["kind"] == "directory":
                    p.mkdir()
                elif e["kind"] == "file":
                    shutil.copyfile(self.path / "blobs" / e["blob"], p)
                else:
                    os.symlink(e["target"], p)
            for name, e in sorted(entries.items(), key=lambda kv: len(PurePosixPath(kv[0]).parts), reverse=True):
                p = stage / name
                if e["kind"] != "symlink":
                    os.chmod(p, e["mode"])
                os.utime(p, ns=(e["mtime_ns"], e["mtime_ns"]), follow_symlinks=False)
            if scan(stage) != entries:
                raise CheckpointError("Restored state differs")
            os.rename(stage, destination)
        finally:
            if stage.exists():
                shutil.rmtree(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    cap = sub.add_parser("capture")
    cap.add_argument("source")
    cap.add_argument("--ref", required=True)
    cap.add_argument("--compatibility", required=True)
    cap.add_argument("--parent", default=None)
    cap.add_argument("--revision", required=True)
    res = sub.add_parser("restore")
    res.add_argument("destination")
    res.add_argument("--head", required=True)
    res.add_argument("--compatibility", required=True)
    head = sub.add_parser("head")
    head.add_argument("ref")
    args = parser.parse_args()
    store = Store(args.store)
    if args.command == "capture":
        print(json.dumps(store.capture(args.source, args.ref, args.compatibility, args.parent, args.revision)))
    elif args.command == "restore":
        store.restore(args.head, args.compatibility, args.destination)
        print("Verified restore complete")
    else:
        print(store.head(args.ref))


if __name__ == "__main__":
    main()
