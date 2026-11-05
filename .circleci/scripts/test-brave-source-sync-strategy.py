#!/usr/bin/env python3
"""Guard resumable Brave source sync against forced or repeated initialization."""
from __future__ import annotations
import importlib.util
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / ".circleci/scripts/prepare-brave-source.sh").read_text(encoding="utf-8")
stage_script = (ROOT / ".circleci/scripts/source-prep-stage.sh").read_text(encoding="utf-8")
shards_script = (ROOT / ".circleci/scripts/sandium-source-shards.py").read_text(encoding="utf-8")

reuse_start = source.index('if [ -s "$ROOT/brave-work/.gclient" ]')
incremental_start = source.index('elif [ -s "$ROOT/brave-work/.gclient" ]', reuse_start)
fallback_start = source.index('else\n    echo "BRAVE_SOURCE_REUSE=MISS; no complete Chromium checkout;', incremental_start)
pin_gate = source.index('ACTUAL_CHROMIUM_SHA="$(git -C "$SRC_DIR" rev-parse HEAD)"', fallback_start)

reuse = source[reuse_start:incremental_start]
incremental = source[incremental_start:fallback_start]
fallback = source[fallback_start:pin_gate]

assert "BRAVE_SOURCE_SYNC=REUSE" in reuse
assert "source-sync-complete" in reuse
assert "run_brave_sync --target_os=android --target_arch=arm64 --no-history --nohooks" in reuse
assert "BRAVE_SOURCE_INCREMENTAL_SYNC=START" in incremental
assert "run_brave_sync --target_os=android --target_arch=arm64 --no-history --nohooks" in incremental
assert "BRAVE_SOURCE_INCREMENTAL_SYNC=PASS" in incremental
assert "pnpm run init" not in incremental
assert "run_brave_sync" in incremental
assert "no complete Chromium checkout" in fallback
assert "run_brave_sync --init --target_os=android --target_arch=arm64 --no-history --nohooks" in fallback
assert "SOURCE_INIT_SECONDS" in fallback
assert '[ -d "$SRC_DIR/third_party" ]' in incremental
assert '[ -d "$SRC_DIR/build" ]' in incremental
assert "BRAVE_CORE_PIN_REUSE=PASS" in source
assert "BRAVE_PNPM_DEPENDENCIES=REUSE" in source
assert "pnpm install --frozen-lockfile --yes" in source
assert "BRAVE_UPSTREAM_SYNC_SECONDS=" in source
assert "BRAVE_SOURCE_PINS=RECORDED before sync" in source
assert 'if [ "$BRAVE_STAGE_INDEX" = "1" ]; then' in source
assert "BRAVE_RELEASE_PIN=LATEST_STABLE_RESOLVED" in source
assert "BRAVE_CHROMIUM_PIN_METADATA=RESTORED" in source
assert "BRAVE_CHROMIUM_CHECKOUT=NEEDS_UPDATE" in source
assert "BRAVE_CORE_SHA=" in source
assert "REFRESH_REQUEST_ID=$REQUEST_ID" in source
assert "BRAVE_CHROMIUM_PIN_REUSE=PASS" not in source
assert "BRAVE_CHROMIUM_REMOTE_LOOKUP=PERFORMED stage=1" in source
assert "source-runhooks-complete" in source

# A timed-out Git fetch is not a resumable checkpoint: discard its uncommitted
# temporary pack, and give the one fetch attempt the maximum safe stage window.
assert 'SLICE_SECONDS="${SANDIUM_PIN_SLICE_SECONDS:-2400}"' in stage_script
assert '[ "$SLICE_SECONDS" -le 2400 ] || SLICE_SECONDS=2400' in stage_script
assert "discard_interrupted_git_packs" in stage_script
assert '*/objects/pack/tmp_pack_*' in stage_script
assert "PINNING_GIT_FETCH=INTERRUPTED" in stage_script
assert 'archive --root "$ROOT" --workers 8 --stage "$STAGE" --skip-if-unchanged' in stage_script

# Checkpoint fingerprints must reflect only durable Git progress. Temporary
# pack size/mtime changes must not force another full source archive.
assert '"progress_state": progress_state' in shards_script
assert '"git_progress_state": metadata["git_progress_state"]' in shards_script
assert '"completed_packfiles": stable_packfiles' in shards_script
assert '"--exclude=tmp_pack_*"' in shards_script
assert '"git_state": metadata["git_state"]' not in shards_script
file_state_start = shards_script.index("def file_state(")
file_state_end = shards_script.index("\ndef ", file_state_start + 1)
file_state_function = shards_script[file_state_start:file_state_end]
assert "mtime_ns" not in file_state_function
assert 'result["sha256"] = sha256_file(path)' in file_state_function
assert 'result["link_target"] = os.readlink(path)' in file_state_function

# Exercise the actual fingerprint primitives: timestamps and interrupted
# temporary packs must not change durable progress, while same-size content
# changes must be detected.
spec = importlib.util.spec_from_file_location("sandium_source_shards", ROOT / ".circleci/scripts/sandium-source-shards.py")
assert spec and spec.loader
shards_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shards_module)

with tempfile.TemporaryDirectory(prefix="sandium-source-progress-test-") as temp:
    temp_root = Path(temp)
    work = temp_root / "brave-work"
    repo = work / "src"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Sandium Test"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "sandium-test@example.invalid"], check=True)
    sample = repo / "sample.txt"
    sample.write_text("alpha", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "sample.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "test"], check=True)
    subprocess.run(["git", "-C", str(repo), "gc", "--prune=now"], check=True)
    progress_before = shards_module.git_repository_state(repo)["progress_state"]
    pack_dir = repo / ".git" / "objects" / "pack"
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "tmp_pack_interrupted").write_bytes(b"partial pack")
    progress_after = shards_module.git_repository_state(repo)["progress_state"]
    assert progress_before == progress_after, "tmp_pack changed durable Git progress"

    critical = work / "critical.env"
    critical.write_text("alpha", encoding="utf-8")
    state_before = shards_module.file_state(critical, work)
    os.utime(critical, (critical.stat().st_atime + 60, critical.stat().st_mtime + 60))
    state_after_touch = shards_module.file_state(critical, work)
    assert state_before == state_after_touch, "mtime-only change altered source fingerprint"
    critical.write_text("bravo", encoding="utf-8")
    state_after_content = shards_module.file_state(critical, work)
    assert state_after_content != state_after_touch, "same-size content change was not detected"

print("BRAVE_SOURCE_SYNC_STRATEGY_TEST=PASS resumable_metadata=verified interrupted_tmp_pack=discarded durable_progress_fingerprint=only archive_reuse=no_duplicate_tmp_pack_archives")
