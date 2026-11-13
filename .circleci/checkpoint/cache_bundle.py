from progress import advance
"""Real local filesystem layer export/import for native cache directory payloads.

No network client, cache discovery or distributed promotion is implemented.
Exports stream whole-file blobs; no base64 or mock storage is involved.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile

from checkpoint import CheckpointError, Store, digest, encoded, valid_id, verify_blob, atomic_json
from circleci_plan import restore_steps, verify_envelope


def regular(path):
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            raise CheckpointError("Payload must be a regular file: " + str(path))
    except FileNotFoundError as exc:
        raise CheckpointError("Missing payload file: " + str(path)) from exc


def slot_paths(root, index):
    if not isinstance(index, int) or not 0 <= index < 8:
        raise CheckpointError("Slot outside bounded plan")
    root = Path(root)
    if root.is_symlink():
        raise CheckpointError("Transport root cannot be a symlink")
    return root / f"slot-{index}", root / f"slot-{index}.json"


def export_layer(store, head, compatibility, transport_root, slot, cache_key, link_blobs=False):
    advance(phase="export-layer")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,220}", cache_key):
        raise CheckpointError("Unsafe cache key")
    valid_id(head)
    # Validate full logical source identity before computing transport delta.
    store.reconstruct(head, compatibility)
    manifest_path = store.path / "manifests" / head
    raw = manifest_path.read_bytes()
    layer = json.loads(raw)
    parent_entries = store.reconstruct(layer["parent"], compatibility)
    available = {e["blob"] for e in parent_entries.values() if e["kind"] == "file"}
    needed = {e["blob"]: e for e in layer["changed"].values()
              if e["kind"] == "file" and e["blob"] not in available}
    directory, header = slot_paths(transport_root, slot)
    if directory.exists() or directory.is_symlink() or header.exists() or header.is_symlink():
        raise CheckpointError("Export slot must be absent")
    directory.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".export-", dir=directory.parent))
    renamed = False
    try:
        (staging / "blobs").mkdir()
        (staging / "manifest.json").write_bytes(raw)
        blobs = {}
        for blob, entry in sorted(needed.items()):
            source = store.path / "blobs" / blob
            regular(source)
            verify_blob(source, entry)
            if link_blobs:
                os.link(source, staging / "blobs" / blob)
            else:
                shutil.copyfile(source, staging / "blobs" / blob)
            if link_blobs:
                # Same immutable inode, already byte-verified immediately above.
                if not os.path.samefile(source, staging / "blobs" / blob):
                    raise CheckpointError("Export hardlink identity mismatch")
            else:
                verify_blob(staging / "blobs" / blob, entry)
            blobs[blob] = entry["size"]
            advance(items=1)
        envelope = {"schema": 1, "cache_key": cache_key, "slot": slot, "head": head,
                    "parent": layer["parent"], "compatibility": compatibility, "blobs": blobs}
        os.rename(staging, directory)
        renamed = True
        # Header is published last. A native save must run only after success.
        atomic_json(header, envelope)
        return {"key": cache_key, "sha256": digest(encoded(envelope)), "head": head,
                "parent": layer["parent"], "slot": slot,
                "paths": [str(header), str(directory)],
                "content_bytes": sum(blobs.values())}
    finally:
        if not renamed:
            shutil.rmtree(staging)


def validate_bundles(plan, transport_root, compatibility):
    restore_steps(plan)  # same bounds, duplicate/key/digest validation as generator
    previous = None
    advance(phase="validate-bundles")
    bundles = []
    for index, spec in enumerate(plan["layers"]):
        directory, header = slot_paths(transport_root, index)
        regular(header)
        if directory.is_symlink() or not directory.is_dir() or (directory / "blobs").is_symlink():
            raise CheckpointError("Unsafe or missing bundle directory")
        envelope = verify_envelope(header, spec["key"], spec["sha256"])
        if envelope["schema"] != 1 or envelope["slot"] != index or envelope["compatibility"] != compatibility:
            raise CheckpointError("Bundle scope or slot mismatch")
        if envelope["parent"] != previous:
            raise CheckpointError("Unordered or mixed bundle chain")
        head = valid_id(envelope["head"])
        manifest_path = directory / "manifest.json"
        regular(manifest_path)
        raw = manifest_path.read_bytes()
        if digest(raw) != head:
            raise CheckpointError("Bundle manifest hash mismatch")
        layer = json.loads(raw)
        if layer["parent"] != previous or layer["compatibility"] != compatibility:
            raise CheckpointError("Manifest chain differs from envelope")
        for blob, size in envelope["blobs"].items():
            valid_id(blob)
            if not isinstance(size, int) or size < 0:
                raise CheckpointError("Invalid blob size")
            path = directory / "blobs" / blob
            regular(path)
            verify_blob(path, {"blob": blob, "size": size})
        bundles.append((directory, envelope, raw))
        previous = head
    if previous != plan["head"]:
        raise CheckpointError("Plan head differs from full chain")
    return bundles


def import_restore(plan, transport_root, compatibility, destination):
    """Fresh-job reconstruction; no persistent prior Store is required."""
    bundles = validate_bundles(plan, transport_root, compatibility)
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink():
        raise CheckpointError("Destination must be absent")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".import-store-", dir=destination.parent) as tmp:
        store = Store(tmp)
        for directory, envelope, raw in bundles:
            for blob, size in envelope["blobs"].items():
                target = store.path / "blobs" / blob
                if target.exists():
                    verify_blob(target, {"blob": blob, "size": size})
                else:
                    shutil.copyfile(directory / "blobs" / blob, target)
                    verify_blob(target, {"blob": blob, "size": size})
            (store.path / "manifests" / envelope["head"]).write_bytes(raw)
        store.restore(plan["head"], compatibility, destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export")
    export.add_argument("--store", required=True)
    export.add_argument("--head", required=True)
    export.add_argument("--compatibility", required=True)
    export.add_argument("--transport-root", default=".checkpoint-transport")
    export.add_argument("--slot", type=int, required=True)
    export.add_argument("--key", required=True)
    restore = sub.add_parser("restore")
    restore.add_argument("--plan", required=True)
    restore.add_argument("--transport-root", default=".checkpoint-transport")
    restore.add_argument("--compatibility", required=True)
    restore.add_argument("--destination", required=True)
    args = parser.parse_args()
    if args.command == "export":
        print(json.dumps(export_layer(Store(args.store), args.head, args.compatibility,
                                      args.transport_root, args.slot, args.key)))
    else:
        with open(args.plan) as f:
            import_restore(json.load(f), args.transport_root, args.compatibility, args.destination)
        print("Complete chain reconstructed and verified")


if __name__ == "__main__":
    main()
