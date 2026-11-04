#!/usr/bin/env python3
"""Regression checks for the five-phase source-only workflow."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
prepare = (ROOT / ".circleci/scripts/prepare-brave-source.sh").read_text(encoding="utf-8")
stage = (ROOT / ".circleci/scripts/source-prep-stage.sh").read_text(encoding="utf-8")
config = (ROOT / ".circleci/config.yml").read_text(encoding="utf-8")
archive = (ROOT / ".circleci/scripts/archive-brave-workspace.sh").read_text(encoding="utf-8")

assert 'SOURCE_PREP_PHASE="${SANDIUM_SOURCE_PREP_PHASE:-all}"' in prepare
assert "run_brave_sync --target_os=android --target_arch=arm64 --no-history --nohooks" in prepare
assert "run_brave_sync --init --target_os=android --target_arch=arm64 --no-history --nohooks" in prepare
assert 'if [ "$SOURCE_PREP_PHASE" = "hooks" ]; then' in prepare
assert '"$CORE_DIR/vendor/depot_tools/gclient" runhooks' in prepare
assert 'if [ "$SOURCE_PREP_PHASE" = "configure" ] || [ "$BRAVE_STAGE_INDEX" = "1" ]; then' in prepare
assert 'if [ "$SOURCE_PREP_PHASE" = "gn" ] || [ "$BRAVE_STAGE_INDEX" = "1" ]; then' in prepare
assert "--ninja=n" in prepare
assert 'SOURCE_PREP_PHASE" = "final"' in prepare
assert "SANDIUM_SOURCE_PREP_STAGE=1 action=sync-chromium-nohooks" in stage
assert "SANDIUM_SOURCE_PREP_STAGE=2 action=runhooks" in stage
assert "SANDIUM_SOURCE_PREP_STAGE=3 action=host-deps-and-siso-environment" in stage
assert "SANDIUM_SOURCE_PREP_STAGE=4 action=generate-gn-graph-no-compilation" in stage
assert "SANDIUM_SOURCE_READY=PASS" in stage
assert "sandium-source-shards.py" in stage
assert "BRAVE_SOURCE_READY_REUSE=PASS" in prepare
assert "brave-source-checkpoint.manifest.json" in archive
assert "source-ready-restored" in archive
assert "enum: [full, fast, source-prep]" in config
assert "sandium-source-preparation:" in config
for i in range(1, 6):
    assert "name: SANDIUM-SOURCE-PREP-stage-%d" % i in config
assert "sandium-brave-pinned-source-v1-v1.99.54-157.0.8103.30-" in config
assert "equal: [source-prep, << pipeline.parameters.sandium_build_mode >>]" in config

print("SANDIUM_SOURCE_PREP_PHASES_TEST=PASS sync,nohooks -> runhooks -> Siso/host config -> GN graph -> verified source-only promotion")
