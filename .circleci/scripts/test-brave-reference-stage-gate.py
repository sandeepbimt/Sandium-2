#!/usr/bin/env python3
"""Test stage-aware checkpoint validation against synthetic 8-shard manifests."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile

script = Path(".circleci/scripts/verify-brave-reference.sh").read_text(encoding="utf-8")
marker = 'python3 - "$MANIFEST" "$SHARDS" "$STAGE" <<\'PY\'\n'
if script.count(marker) != 1:
    raise SystemExit("REFERENCE_STAGE_PREFLIGHT=FAIL expected exactly one manifest validation heredoc")
body, separator, _ = script.split(marker, 1)[1].partition("\nPY\n")
if not separator:
    raise SystemExit("REFERENCE_STAGE_PREFLIGHT=FAIL unterminated manifest validation heredoc")

def run(body, manifest_path, shard_dir, stage):
    return subprocess.run(
        [sys.executable, "-c", body, str(manifest_path), str(shard_dir), str(stage)],
        text=True, capture_output=True
    )

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    shard_dir = root / "shards"
    shard_dir.mkdir()
    shards = []
    total = 0
    for index in range(1, 9):
        name = f"shard-{index:02d}-of-08.tar.zst"
        payload = ("test-shard-%02d" % index).encode()
        (shard_dir / name).write_bytes(payload)
        total += len(payload)
        shards.append({
            "name": name,
            "size_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        })

    base = {
        "schema_version": 2,
        "format": "independent-tar+zstd-shards",
        "workers": 8,
        "shards": shards,
        "archive_bytes": total,
        "source_bytes": total * 10,
        "checkpoint_manifest": {
            "CHECKPOINT_VALID": "true",
            "REFERENCE_MODE": "reference",
            "CHROMIUM_SHA": "d331de35ca8ab1358c7a17e4bd41627d55eaef51",
            "BRAVE_CORE_TAG": "v1.98.62",
            "TARGET": "android-arm64",
            "BUILD_TYPE": "Release",
            "APK_VALIDATED": "false",
            "REFERENCE_READY": "false",
        },
    }
    manifest = root / "manifest.json"

    def write_checkpoint(apk_validated, reference_ready):
        data = json.loads(json.dumps(base))
        data["checkpoint_manifest"]["APK_VALIDATED"] = apk_validated
        data["checkpoint_manifest"]["REFERENCE_READY"] = reference_ready
        manifest.write_text(json.dumps(data), encoding="utf-8")

    write_checkpoint("true", "true")
    result = run(body, manifest, shard_dir, 1)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SANDIUM_REFERENCE_MANIFEST=PASS stage=1" in result.stdout

    write_checkpoint("false", "false")
    result = run(body, manifest, shard_dir, 2)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SANDIUM_HANDOFF_MANIFEST=PASS stage=2 APK_VALIDATED=false" in result.stdout

    write_checkpoint("true", "true")
    result = run(body, manifest, shard_dir, 3)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SANDIUM_HANDOFF_MANIFEST=PASS stage=3 APK_VALIDATED=true" in result.stdout

    write_checkpoint("false", "false")
    result = run(body, manifest, shard_dir, 1)
    assert result.returncode != 0, "Stage 1 incorrectly accepted an unvalidated canonical reference"

    missing = shard_dir / "shard-08-of-08.tar.zst"
    missing.unlink()
    result = run(body, manifest, shard_dir, 2)
    assert result.returncode != 0, "Continuation gate incorrectly accepted a missing shard"

print("REFERENCE_STAGE_PREFLIGHT=PASS canonical APK gate, incomplete continuation acceptance, and missing-shard rejection")
