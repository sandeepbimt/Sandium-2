#!/usr/bin/env python3
"""Regression checks for the guarded Chromium partial-clone capability probe."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
probe = (ROOT / ".circleci/scripts/probe-chromium-partial-clone.sh").read_text(encoding="utf-8")
prepare = (ROOT / ".circleci/scripts/prepare-brave-source.sh").read_text(encoding="utf-8")
stage = (ROOT / ".circleci/scripts/source-prep-stage.sh").read_text(encoding="utf-8")

assert "git -C \"$REPO\" -c protocol.version=2 fetch --filter=blob:none --depth=1" in probe
assert 'remote.origin.promisor' in probe
assert 'remote.origin.partialclonefilter' in probe
assert 'extensions.partialClone origin' in probe
assert 'git -C "$REPO" cat-file -e "$BLOB"' in probe
assert 'restored checkout unchanged' in probe
assert 'SERVER_CAPABILITY_CONFIRMED_AND_CONFIGURED' not in probe
assert 'git -C "$SRC" config' not in probe
assert 'CHROMIUM_PARTIAL_CLONE_PROBE=UNSUPPORTED_OR_UNAVAILABLE' in probe
assert 'CHROMIUM_PARTIAL_CLONE_PROBE=PASS' in probe
assert 'COMMIT" != "$SHA"' in probe
assert 'GIT_NO_LAZY_FETCH=1' in probe
assert 'cat-file -e "$BLOB"' in probe
assert 'probe-chromium-partial-clone.sh' in prepare
assert 'PROBE_MARKER' in prepare
assert 'BRAVE_CHROMIUM_PARTIAL_CLONE=ENABLED' in prepare
assert 'BRAVE_CHROMIUM_PARTIAL_CLONE=DISABLED' in prepare
assert 'SANDIUM_ENABLE_CHROMIUM_PARTIAL_CLONE:-false' in prepare
assert 'SANDIUM_ENABLE_CHROMIUM_PARTIAL_CLONE:-false' in prepare
assert 'git -C "$SRC" config --unset-all remote.origin.partialclonefilter' in prepare
assert 'reason=full-checkout-default-no-filter' in prepare
assert 'explicit experiment opt-in verified' in prepare
assert 'SUPPORTED_NOT_ENABLED' not in prepare
assert 'source-sync-no-progress' in stage

print("CHROMIUM_PARTIAL_CLONE_PROBE_TEST=PASS endpoint_filter=verified_lazy_blob_backfill=verified_unsupported_fallback=nonbreaking")
