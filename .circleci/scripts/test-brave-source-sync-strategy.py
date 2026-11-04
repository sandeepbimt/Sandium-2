#!/usr/bin/env python3
"""Guard resumable Brave source sync against forced or repeated initialization."""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
source = (ROOT / ".circleci/scripts/prepare-brave-source.sh").read_text(encoding="utf-8")

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
assert 'if [ "$BRAVE_STAGE_INDEX" = "1" ] && [ ! -s "$ROOT/brave-work/.sandium/source-pins.env" ]; then' in source
assert "BRAVE_CHROMIUM_PIN_REUSE=PASS restored request pin=" in source
assert "BRAVE_CHROMIUM_REMOTE_LOOKUP=PERFORMED stage=1" in source
assert "source-runhooks-complete" in source

print("BRAVE_SOURCE_SYNC_STRATEGY_TEST=PASS resumable_checkpoint=resume incremental_sync=no_force missing_checkout=init_fallback")
