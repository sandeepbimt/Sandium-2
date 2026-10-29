#!/usr/bin/env bash
# Shared SS2 fast-path predicate. Exit 0 only for a complete, compatible APK handoff.
set -euo pipefail
ROOT="${1:?usage: ss2-validate-apk-handoff.sh ROOT [CHROMIUM_TAG]}"
CHROMIUM_TAG="${2:-151.0.7922.38}"
shopt -s nullglob
for candidate in "$ROOT"/ss2-apk/stage-*; do
  APK="$candidate/ChromePublic.apk"
  STATUS="$candidate/status.txt"
  [ -s "$APK" ] && [ -s "$STATUS" ] || continue
  grep -Fxq 'BUILD_FINISHED=true' "$STATUS" || continue
  grep -Fxq 'APK_ARCHIVE_VALID=true' "$STATUS" || continue
  grep -Fxq "CHROMIUM_TAG=$CHROMIUM_TAG" "$STATUS" || continue
  test -d "$ROOT/afterbird-delta/.git" || continue
  CURRENT_DELTA_SHA="$(git -C "$ROOT/afterbird-delta" rev-parse HEAD)"
  EXPECTED_DELTA_SHA="$(sed -n 's/^AFTERBIRD_SHA=//p' "$STATUS" | tail -n 1)"
  [ -n "$EXPECTED_DELTA_SHA" ] && [ "$CURRENT_DELTA_SHA" = "$EXPECTED_DELTA_SHA" ] || continue
  CURRENT_ARGS_SHA="$(sha256sum "$ROOT/afterbird-delta/.build/args/release.gn" | awk '{print $1}')"
  EXPECTED_ARGS_SHA="$(sed -n 's/^RELEASE_ARGS_SHA256=//p' "$STATUS" | tail -n 1)"
  [ -n "$EXPECTED_ARGS_SHA" ] && [ "$CURRENT_ARGS_SHA" = "$EXPECTED_ARGS_SHA" ] || continue
  EXPECTED_SHA="$(sed -n 's/^APK_SHA256=//p' "$STATUS" | tail -n 1)"
  [ -n "$EXPECTED_SHA" ] || continue
  ACTUAL_SHA="$(sha256sum "$APK" | awk '{print $1}')"
  [ "$ACTUAL_SHA" = "$EXPECTED_SHA" ] || continue
  if python3 -c 'import sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); bad=z.testzip(); sys.exit(1 if bad else 0)' "$APK"; then
    echo "SS2_FAST_EXIT=PASS candidate=$(basename "$candidate") sha256=$ACTUAL_SHA"
    exit 0
  fi
done
echo "SS2_FAST_EXIT=MISS no compatible verified APK handoff found"
exit 1
