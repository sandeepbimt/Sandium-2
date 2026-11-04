#!/usr/bin/env python3
"""Regression checks for resumable 30-minute source-only preparation."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
stage = (ROOT / ".circleci/scripts/source-prep-stage.sh").read_text(encoding="utf-8")
prepare = (ROOT / ".circleci/scripts/prepare-brave-source.sh").read_text(encoding="utf-8")
config = (ROOT / ".circleci/config.yml").read_text(encoding="utf-8")
restore = (ROOT / ".circleci/scripts/restore-brave-source-checkpoint.sh").read_text(encoding="utf-8")
verify = (ROOT / ".circleci/scripts/verify-pinned-source-reference.sh").read_text(encoding="utf-8")
for marker in ("source-sync-complete", "source-runhooks-complete", "source-configure-complete", "source-gn-complete"):
    assert marker in stage
assert "SANDIUM_PIN_SLICE_SECONDS" in stage and "1800" in stage
assert "--signal=INT --kill-after=30s" in stage
assert "SANDIUM_PINNING_ARCHIVE=PASS" in stage and "--ready --zstd-test" in stage
assert "BRAVE_SOURCE_PINS=RECORDED before sync" in prepare
assert "BRAVE_SOURCE_SYNC=REUSE" in prepare and "source-runhooks-complete" in prepare
assert "install-build-deps.sh --android" not in prepare
assert "SOURCE_PREP_BASE=PINNING_PROGRESS" in restore
assert "PINNING_READY=true" in config and "persist_to_workspace:" in config and "attach_workspace:" in config
assert "sandium-brave-pinning-progress-v2-" in config
assert "promote-brave-pinned-source-reference:" in config
assert "verify-pinned-source-reference.sh" in config
assert "sandium-brave-pinned-source-v2-" in config
assert "architecture/separate-brave-source-preparation" in config
assert "Restore independent pinned Brave/Chromium reference at every build stage" in config
assert "PIN_REFERENCE_OUTDATED=FAIL" in verify
assert "Do not overlay the source archive on compiled state" in verify
assert "circleci-agent step halt" in config
print("SANDIUM_RESUMABLE_PINNING_TEST=PASS 30-minute slices; stage checkpoint resume; early exits; separate Fast/Full source validation")
