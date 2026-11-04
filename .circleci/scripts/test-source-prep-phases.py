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
assert "PINNING_BOOTSTRAP=REQUIRED stage=1" in stage
assert 'if [ "$STAGE" = "1" ]; then' in stage
assert "resolves its exact upstream SHA" in stage
assert "refusing to guess pins" in stage
assert 'if [ "$STAGE" = "1" ]; then' in stage and "PINNING_GATE=FAIL source-pins.env missing after stage checkpoint restore" in stage
assert "--signal=INT --kill-after=30s" in stage
assert "SANDIUM_PINNING_ARCHIVE=PASS" in stage and "--ready --zstd-test" in stage
assert "--skip-if-unchanged" in stage and "source-archive-unchanged" in stage
assert 'rm -f "$PINS" "$STATE/source-sync-complete"' in stage
assert 'SANDIUM_PINNING_STAGE_INDEX="$STAGE"' in stage
assert "BRAVE_RELEASE_PIN=LATEST_STABLE_RESOLVED" in prepare
assert "https://api.github.com/repos/brave/brave-browser/releases/latest" in prepare
assert "BRAVE_CORE_SHA=" in prepare and "REFRESH_REQUEST_ID=$REQUEST_ID" in prepare
assert "PINNING_REFRESH_REQUEST=NEW" in stage
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
canonical_order = [
    config.index("sandium-brave-handoff-v2-sandium/fix-archive-completion-gate-d0bc6af6-e2a7-451e-8561-3c90eb48c2e1-stage-%d" % stage)
    for stage in (5, 4, 3, 2, 1)
]
assert canonical_order == sorted(canonical_order), "canonical reference must restore the highest cumulative completed stage first"
for stage, expected in ((3, (2, 1)), (4, (3, 2, 1)), (5, (4, 3, 2, 1))):
    name = "name: Restore source-preparation Stage %d checkpoint" % (stage - 1)
    start = config.index(name)
    end = config.index("\\n      - when:", start)
    block = config[start:end]
    positions = [block.index("-stage-%d" % prior) for prior in expected]
    assert positions == sorted(positions), "Stage %d must fall back to the latest available earlier checkpoint" % stage
assert "Avoid duplicate upload when this source slice made no reusable progress" in config
assert "PINNING_REFERENCE_PROMOTION=FAIL" in config and '"v1.99.54"' not in config
assert "PIN_REFERENCE_OUTDATED=FAIL" in verify
assert "Do not overlay the source archive on compiled state" in verify
assert "circleci-agent step halt" in config
print("SANDIUM_RESUMABLE_PINNING_TEST=PASS 30-minute slices; stage checkpoint resume; early exits; separate Fast/Full source validation")
