#!/usr/bin/env python3
"""Exercise ordered, immutable source-delta assembly and lineage rejection."""
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "sandium_source_shards", ROOT / ".circleci/scripts/sandium-source-shards.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def shard_item(name: str, data: bytes, root_path: str) -> dict:
    return {"name": name, "size_bytes": len(data), "sha256": digest(data),
            "root_paths": [root_path]}


def manifest(stage: int, items: list[dict]) -> bytes:
    return (json.dumps({"schema_version": MODULE.SCHEMA,
                        "format": "sandium-brave-source-only-shards",
                        "stage": stage, "ready": False, "shards": items},
                       sort_keys=True, indent=2) + "\n").encode()


with tempfile.TemporaryDirectory(prefix="sandium-delta-test-") as tmp:
    root = Path(tmp)
    base_dir = root / "brave-source-checkpoint.base.shards"
    base_dir.mkdir()
    base_a = b"base-a"
    (base_dir / "source-shard-01.tar.zst").write_bytes(base_a)
    base_items = [shard_item("source-shard-01.tar.zst", base_a, "brave-work/src/.git")]
    base_bytes = manifest(0, base_items)
    (root / "brave-source-checkpoint.base.manifest.json").write_bytes(base_bytes)

    # Stage 1 changes shard 01 and adds shard 02.
    stage1_dir = root / "brave-source-checkpoint.deltas/stage-1"
    (stage1_dir / "shards").mkdir(parents=True)
    a1, b1 = b"stage1-a", b"stage1-b"
    (stage1_dir / "shards/source-shard-01.tar.zst").write_bytes(a1)
    (stage1_dir / "shards/source-shard-02.tar.zst").write_bytes(b1)
    items1 = [shard_item("source-shard-01.tar.zst", a1, "brave-work/src/.git"),
              shard_item("source-shard-02.tar.zst", b1, "brave-work/src/third_party")]
    result1 = manifest(1, items1)
    MODULE.write_delta_record(root, 1, base_bytes, json.loads(base_bytes),
                              result1, json.loads(result1), items1, [], stage1_dir / "shards")

    # Stage 2 is a no-op delta but advances the ordered manifest lineage.
    stage2_dir = root / "brave-source-checkpoint.deltas/stage-2"
    stage2_dir.mkdir(parents=True)
    result2 = manifest(2, items1)
    MODULE.write_delta_record(root, 2, result1, json.loads(result1),
                              result2, json.loads(result2), [], [], stage2_dir)

    assembled = MODULE.assemble_deltas(root, 2, zstd_test=False)
    out = root / MODULE.SHARDS_NAME
    assert (out / "source-shard-01.tar.zst").read_bytes() == a1
    assert (out / "source-shard-02.tar.zst").read_bytes() == b1
    assert (root / MODULE.MANIFEST_NAME).read_bytes() == result2
    assert assembled["stage"] == 2

    # A broken parent pointer must fail closed, never produce a partial checkpoint.
    delta2 = stage2_dir / "delta-manifest.json"
    broken = json.loads(delta2.read_text())
    broken["parent_manifest_sha256"] = "0" * 64
    delta2.write_text(json.dumps(broken, sort_keys=True, indent=2) + "\n")
    try:
        MODULE.assemble_deltas(root, 2, zstd_test=False)
    except SystemExit:
        pass
    else:
        raise AssertionError("delta lineage mismatch was not rejected")

config = (ROOT / ".circleci/config.yml").read_text(encoding="utf-8")
stage_job = config.split("  brave-source-preparation-stage:", 1)[1].split("  promote-brave-pinned-source-reference:", 1)[0]
assert "assemble-deltas --root" in stage_job
assert "through-stage 5" in stage_job
assert "brave-source-checkpoint.deltas/stage-<< parameters.stage_index >>" in stage_job
assert "sandium-brave-pinning-progress-v3-" in stage_job
assert "save_cache:" in stage_job
assert "restore_cache:" in stage_job
assert "brave-source-checkpoint.base.shards" not in stage_job.split("persist_to_workspace:", 1)[-1]
assert "prepare-source-delta-base.sh" in stage_job
print("SOURCE_DELTA_ASSEMBLY_TEST=PASS ordered_deltas=2 no_op_delta=verified parent_mismatch=rejected")
