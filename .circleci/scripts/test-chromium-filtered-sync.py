"""Regression checks for the filtered Chromium fetch -> Brave DEPS-only sync handoff."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
prepare = (ROOT / ".circleci/scripts/prepare-brave-source.sh").read_text(encoding="utf-8")
fetch = (ROOT / ".circleci/scripts/fetch-pinned-chromium.sh").read_text(encoding="utf-8")
probe = (ROOT / ".circleci/scripts/probe-chromium-partial-clone.sh").read_text(encoding="utf-8")

assert 'SANDIUM_ENABLE_CHROMIUM_PARTIAL_CLONE:-true' in prepare
assert "CHROMIUM_PARTIAL_CLONE_ACTIVE=true" in prepare
assert 'fetch-pinned-chromium.sh' in prepare
assert 'run_brave_sync --target_os=android --target_arch=arm64 --no-history --nohooks --sync_chromium=true' in prepare
assert 'run_brave_sync --target_os=android --target_arch=arm64 --no-history --sync_chromium=true' in prepare
assert 'BRAVE_CHROMIUM_SYNC=FILTERED_PIN_ALREADY_CHECKED_OUT' in prepare
assert 'BRAVE_CHROMIUM_FILTERED_FETCH=FALLBACK' in prepare

assert 'fetch --filter=blob:none --no-tags --depth=1 origin' in fetch
assert 'refs/tags/$TAG:refs/tags/$TAG' in fetch
assert 'rev-parse "$TAG^{commit}"' in fetch
assert '[ "$RESOLVED" = "$EXPECTED_SHA" ]' in fetch
assert 'checkout --force --detach "$EXPECTED_SHA"' in fetch
assert 'remote.origin.promisor true' in fetch
assert 'remote.origin.partialclonefilter blob:none' in fetch
assert 'CHROMIUM_FILTERED_FETCH=PASS' in fetch
assert 'unexpected origin=' in fetch
assert 'CHECKOUT_MAX_ATTEMPTS=4' in fetch
assert 'CHROMIUM_LAZY_HYDRATION=RETRY' in fetch
assert 'CHROMIUM_LAZY_HYDRATION=PASS' in fetch
assert 'http.maxRequests 2' in fetch
assert 'no unfiltered fallback attempted' in fetch
assert 'sleep "$((CHECKOUT_ATTEMPT * 10))"' in fetch
assert "HTTP 5[0-9][0-9]" in fetch
assert 'CHROMIUM_PARTIAL_CLONE_PROBE=PASS' in probe
# set -u must not encounter the stale, undefined SRC variable after probe success.
assert 'git -C "$SRC_DIR" config extensions.partialClone origin' in prepare
assert 'git -C "$SRC_DIR" config remote.origin.promisor true' in prepare
assert 'git -C "$SRC_DIR" config remote.origin.partialclonefilter blob:none' in prepare
assert 'git -C "$SRC" config' not in prepare

print("CHROMIUM_FILTERED_SYNC_TEST=PASS exact_pin=verified blob_filter=enabled lazy_hydration=probe_gated duplicate_chromium_sync=avoided fallback=preserved")
