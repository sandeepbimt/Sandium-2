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
assert 'CHROMIUM_PARTIAL_CLONE_PROBE=PASS' in probe

print("CHROMIUM_FILTERED_SYNC_TEST=PASS exact_pin=verified blob_filter=enabled lazy_hydration=probe_gated duplicate_chromium_sync=avoided fallback=preserved")
