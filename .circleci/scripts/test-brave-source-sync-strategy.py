#!/usr/bin/env python3
"""Guard Brave source upgrades against unnecessary forced full initialization."""
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

assert "BRAVE_CHECKPOINT_PRESERVATION=PASS" in reuse
assert "pnpm run sync --target_os=android --target_arch=arm64 --no-history --sync_chromium=false" in reuse
assert "BRAVE_SOURCE_INCREMENTAL_SYNC=START" in incremental
assert "pnpm run sync --target_os=android --target_arch=arm64 --no-history" in incremental
assert "BRAVE_SOURCE_INCREMENTAL_SYNC=PASS" in incremental
assert "pnpm run init" not in incremental
assert "pnpm run sync" in incremental and "pnpm run sync" not in incremental.replace(
    "pnpm run sync --target_os=android --target_arch=arm64 --no-history", ""
)
assert "no complete Chromium checkout" in fallback
assert "pnpm run init --target_os=android --target_arch=arm64 --no-history" in fallback
assert "SOURCE_INIT_SECONDS" in fallback
assert '[ -d "$SRC_DIR/third_party" ]' in incremental
assert '[ -d "$SRC_DIR/build" ]' in incremental

print("BRAVE_SOURCE_SYNC_STRATEGY_TEST=PASS pinned_checkpoint=noop existing_old_checkout=incremental_sync_without_force missing_checkout=init_fallback")
