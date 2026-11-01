#!/usr/bin/env bash
set -euo pipefail

ROOT="${CIRCLE_WORKING_DIRECTORY:?CIRCLE_WORKING_DIRECTORY is required}"
WORK="$ROOT/brave-work"
MANIFEST="$WORK/.sandium/checkpoint-manifest.txt"
ARCHIVE="$ROOT/brave-workspace-checkpoint.tar.zst"
META="$ROOT/brave-workspace-checkpoint.meta"
SRC="$WORK/src"
CORE="$SRC/brave"
OUT="$SRC/out/android_Release_arm64"

fail() {
  echo "SANDIUM_REFERENCE_GATE=FAIL $*" >&2
  exit 1
}

[ -s "$MANIFEST" ] || fail "restored reference manifest is missing"
[ -s "$ARCHIVE" ] || fail "restored reference archive is missing"
[ -s "$META" ] || fail "restored reference archive metadata is missing"

for pair in \
  "CHECKPOINT_VALID=true" \
  "REFERENCE_MODE=reference" \
  "APK_VALIDATED=true" \
  "REFERENCE_READY=true" \
  "CHROMIUM_SHA=d331de35ca8ab1358c7a17e4bd41627d55eaef51" \
  "BRAVE_CORE_TAG=v1.98.62" \
  "TARGET=android-arm64" \
  "BUILD_TYPE=Release"; do
  grep -Fx "$pair" "$MANIFEST" >/dev/null || fail "manifest lacks $pair"
done

grep -Fx "ARCHIVE_VALID=true" "$META" >/dev/null || fail "archive metadata is not marked valid"
EXPECTED_SHA="$(sed -n 's/^ARCHIVE_SHA256=//p' "$META" | head -n 1)"
ACTUAL_SHA="$(sha256sum "$ARCHIVE" | awk '{print $1}')"
[ -n "$EXPECTED_SHA" ] && [ "$EXPECTED_SHA" = "$ACTUAL_SHA" ] || fail "archive SHA256 does not match metadata"

[ -s "$SRC/.git/HEAD" ] || fail "Chromium Git metadata missing"
[ -s "$CORE/.git/HEAD" ] || fail "Brave Git metadata missing"
[ "$(git -C "$SRC" rev-parse HEAD)" = "d331de35ca8ab1358c7a17e4bd41627d55eaef51" ] || fail "Chromium checkout does not match reference"
[ "$(git -C "$CORE" describe --tags --exact-match 2>/dev/null || true)" = "v1.98.62" ] || fail "Brave checkout does not match reference"
[ -s "$OUT/build.ninja" ] || fail "Ninja build graph missing"
[ -s "$OUT/args.gn" ] || fail "GN args missing"
[ -s "$OUT/args_generated.gni" ] || fail "generated GN args missing"
[ -s "$SRC/build/config/siso/.sisorc" ] || fail "Siso config missing"
[ -s "$SRC/build/config/siso/.sisoenv" ] || fail "Siso environment missing"
[ -s "$SRC/build/config/siso/backend_config/backend.star" ] || fail "Siso backend missing"
if [ ! -s "$OUT/.siso_fs_state" ] && [ ! -s "$OUT/.siso_fs_state.journal" ]; then
  fail "neither Siso filesystem state nor its journal is present"
fi

echo "SANDIUM_REFERENCE_GATE=PASS"
echo "SANDIUM_REFERENCE_CHROMIUM=$(git -C "$SRC" rev-parse HEAD)"
echo "SANDIUM_REFERENCE_BRAVE=$(git -C "$CORE" describe --tags --exact-match)"
echo "SANDIUM_REFERENCE_ARCHIVE_BYTES=$(stat -c '%s' "$ARCHIVE")"
echo "SANDIUM_REFERENCE_ARCHIVE_SHA256=$ACTUAL_SHA"
