#!/usr/bin/env python3
"""Tests the final archive receipt against real manifest/shard metadata."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

SCRIPT = Path(__file__).with_name("checkpoint-stage-receipt.py")
SHARDS = [f"shard-{index:02d}-of-08.tar.zst" for index in range(1, 9)]


def run(root: Path, operation: str, *, stage: int = 1,
        workflow: str = "workflow-test", expected: int = 0) -> str:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), operation, "--root", str(root),
         "--stage", str(stage), "--workflow-id", workflow],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if result.returncode != expected:
        raise AssertionError(
            f"{operation}: expected exit={expected}, got={result.returncode}\n{result.stdout}"
        )
    return result.stdout


def fixture(root: Path) -> None:
    shard_dir = root / "brave-workspace-checkpoint.shards"
    shard_dir.mkdir(parents=True)
    rows = []
    for index, name in enumerate(SHARDS, 1):
        data = (f"fixture shard {index}\n" * index).encode()
        (shard_dir / name).write_bytes(data)
        rows.append({
            "name": name,
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "root_paths": [f"brave-work/fixture-{index}"],
        })
    manifest = {
        "schema_version": 2,
        "format": "independent-tar+zstd-shards",
        "workspace_root": "brave-work",
        "created_at": "2026-11-02T00:00:00+00:00",
        "workers": 8,
        "max_workers": 8,
        "compression": "zstd --fast=5 -T1 per worker",
        "archive_bytes": sum(item["size_bytes"] for item in rows),
        "shards": rows,
    }
    (root / "brave-workspace-checkpoint.manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sandium-final-gate-") as temporary:
        root = Path(temporary)
        fixture(root)

        # Regression for the actual bug: a touch-created zero-byte marker
        # failed the prior test -s check, despite a valid archive.
        marker = root / "brave-work/.sandium/workspace-archive-created-this-run"
        marker.parent.mkdir(parents=True)
        marker.touch()
        assert marker.stat().st_size == 0
        run(root, "verify", expected=1)

        written = run(root, "write")
        assert "FINAL_STAGE_ARCHIVE_RECEIPT=WRITTEN stage=1" in written
        assert marker.stat().st_size > 0
        passed = run(root, "verify")
        assert "FINAL_STAGE_ARCHIVE_RECEIPT=PASS stage=1" in passed

        # Do not accept a receipt from another stage or workflow.
        run(root, "verify", stage=2, expected=1)
        run(root, "verify", workflow="different-workflow", expected=1)

        # The manifest is part of the receipt binding.
        manifest_path = root / "brave-workspace-checkpoint.manifest.json"
        original = manifest_path.read_text(encoding="utf-8")
        manifest_path.write_text(original + "\n", encoding="utf-8")
        run(root, "verify", expected=1)
        manifest_path.write_text(original, encoding="utf-8")

        # Missing or size-truncated shards must never produce a green gate.
        shard = root / "brave-workspace-checkpoint.shards" / SHARDS[0]
        data = shard.read_bytes()
        shard.write_bytes(data + b"tamper")
        run(root, "verify", expected=1)
        shard.write_bytes(data)

        # A valid receipt becomes green again after the exact original files return.
        run(root, "verify")

    print("SANDIUM_FINAL_ARCHIVE_GATE_TEST=PASS nonempty receipt + stage/workflow binding + manifest/shard validation")


if __name__ == "__main__":
    main()
