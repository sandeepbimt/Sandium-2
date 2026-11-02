#!/usr/bin/env python3
"""Create/verify proof that this CircleCI stage produced a complete 8-shard archive."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MANIFEST_NAME = "brave-workspace-checkpoint.manifest.json"
SHARD_DIR_NAME = "brave-workspace-checkpoint.shards"
RECEIPT_RELATIVE = Path("brave-work/.sandium/workspace-archive-created-this-run")
EXPECTED_SHARDS = [f"shard-{index:02d}-of-08.tar.zst" for index in range(1, 9)]
HEX_256 = re.compile(r"^[0-9a-f]{64}$")


class GateError(Exception):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_and_check_manifest(root: Path) -> tuple[dict[str, Any], str]:
    manifest_path = root / MANIFEST_NAME
    shard_dir = root / SHARD_DIR_NAME
    if not manifest_path.is_file() or manifest_path.stat().st_size == 0:
        raise GateError(f"shard manifest missing or empty: {manifest_path}")
    if not shard_dir.is_dir():
        raise GateError(f"shard directory missing: {shard_dir}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"cannot parse shard manifest: {exc}") from exc

    if manifest.get("schema_version") != 2:
        raise GateError("unsupported shard manifest schema")
    if manifest.get("format") != "independent-tar+zstd-shards":
        raise GateError("unexpected shard archive format")
    if manifest.get("workspace_root") != "brave-work":
        raise GateError("manifest workspace root mismatch")
    if manifest.get("workers") != 8:
        raise GateError(f"expected 8 archived workers, found {manifest.get('workers')!r}")
    if manifest.get("compression") != "zstd --fast=5 -T1 per worker":
        raise GateError("unexpected checkpoint compression metadata")

    shards = manifest.get("shards")
    if not isinstance(shards, list) or len(shards) != 8:
        raise GateError(f"expected exactly 8 shard records, found {len(shards) if isinstance(shards, list) else 'invalid'}")
    names = [item.get("name") if isinstance(item, dict) else None for item in shards]
    if sorted(names) != EXPECTED_SHARDS:
        raise GateError(f"shard names do not match the complete 8-shard set: {names!r}")

    total = 0
    for item in shards:
        name = item["name"]
        size = item.get("size_bytes")
        digest = item.get("sha256")
        if not isinstance(size, int) or size <= 0:
            raise GateError(f"invalid recorded size for {name}")
        if not isinstance(digest, str) or not HEX_256.fullmatch(digest):
            raise GateError(f"invalid recorded SHA256 for {name}")
        path = shard_dir / name
        if not path.is_file():
            raise GateError(f"shard file missing: {name}")
        actual_size = path.stat().st_size
        if actual_size != size:
            raise GateError(f"shard size mismatch for {name}: manifest={size} disk={actual_size}")
        total += size

    if manifest.get("archive_bytes") != total:
        raise GateError(
            f"aggregate archive size mismatch: manifest={manifest.get('archive_bytes')} shards={total}"
        )
    if not isinstance(manifest.get("created_at"), str) or not manifest["created_at"]:
        raise GateError("manifest creation timestamp missing")
    return manifest, sha256(manifest_path)


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("write", "verify"))
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--stage", required=True, type=int, choices=range(1, 6))
    parser.add_argument("--workflow-id", required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    receipt_path = root / RECEIPT_RELATIVE
    try:
        manifest, manifest_sha = load_and_check_manifest(root)
        if args.operation == "write":
            receipt = {
                "schema_version": 1,
                "archive_created": True,
                "stage": args.stage,
                "workflow_id": args.workflow_id,
                "manifest_sha256": manifest_sha,
                "manifest_created_at": manifest["created_at"],
                "shard_count": len(manifest["shards"]),
                "archive_bytes": manifest["archive_bytes"],
                "receipt_created_at": datetime.now(timezone.utc).isoformat(),
            }
            atomic_write(receipt_path, receipt)
            print(
                "FINAL_STAGE_ARCHIVE_RECEIPT=WRITTEN stage=%d workflow=%s shards=%d bytes=%d manifest_sha256=%s"
                % (args.stage, args.workflow_id, receipt["shard_count"],
                   receipt["archive_bytes"], manifest_sha)
            )
            return 0

        if not receipt_path.is_file() or receipt_path.stat().st_size == 0:
            raise GateError(f"stage archive receipt missing or empty: {receipt_path}")
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise GateError(f"cannot parse stage archive receipt: {exc}") from exc

        expected = {
            "schema_version": 1,
            "archive_created": True,
            "stage": args.stage,
            "workflow_id": args.workflow_id,
            "manifest_sha256": manifest_sha,
            "manifest_created_at": manifest["created_at"],
            "shard_count": 8,
            "archive_bytes": manifest["archive_bytes"],
        }
        mismatches = [
            key for key, value in expected.items() if receipt.get(key) != value
        ]
        if mismatches:
            raise GateError("stage receipt mismatch: " + ", ".join(mismatches))
        print(
            "FINAL_STAGE_ARCHIVE_RECEIPT=PASS stage=%d workflow=%s shards=8 bytes=%d manifest_sha256=%s"
            % (args.stage, args.workflow_id, manifest["archive_bytes"], manifest_sha)
        )
        return 0
    except (OSError, GateError) as exc:
        print(f"FINAL_STAGE_ARCHIVE_RECEIPT=FAIL {exc}", file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
