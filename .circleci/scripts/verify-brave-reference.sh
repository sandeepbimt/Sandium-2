#!/usr/bin/env bash
set -euo pipefail

ROOT="${CIRCLE_WORKING_DIRECTORY:?CIRCLE_WORKING_DIRECTORY is required}"
WORK="$ROOT/brave-work"
MANIFEST="$ROOT/brave-workspace-checkpoint.manifest.json"
SHARDS="$ROOT/brave-workspace-checkpoint.shards"
SRC="$WORK/src"
CORE="$SRC/brave"
OUT="$SRC/out/android_Release_arm64"
EXPECTED_BRAVE_CORE_TAG="${EXPECTED_BRAVE_CORE_TAG-v1.99.54}"
EXPECTED_CHROMIUM_TAG="${EXPECTED_CHROMIUM_TAG-157.0.8103.30}"
EXPECTED_CHROMIUM_SHA="${EXPECTED_CHROMIUM_SHA-}"
EXPECTED_VANILLA_RELEASE="${EXPECTED_VANILLA_RELEASE-true}"
fail() { echo "BRAVE_REFERENCE_GATE=FAIL $*" >&2; exit 1; }

[ -d "$SHARDS" ] || fail "restored parallel reference shard directory is missing"
[ -s "$MANIFEST" ] || fail "restored parallel reference manifest is missing"
[ -s "$WORK/.sandium/checkpoint-manifest.txt" ] || fail "restored workspace checkpoint manifest is missing"

python3 - "$MANIFEST" "$EXPECTED_BRAVE_CORE_TAG" "$EXPECTED_CHROMIUM_TAG" "$EXPECTED_CHROMIUM_SHA" <<'PY'
import json
import re
import sys
from pathlib import Path

path, expected_brave, expected_chromium, expected_sha = sys.argv[1:]
data = json.loads(Path(path).read_text(encoding="utf-8"))
if data.get("schema_version") != 2 or data.get("format") != "independent-tar+zstd-shards":
    raise SystemExit("BRAVE_REFERENCE_GATE=FAIL unsupported shard manifest")
checkpoint = data.get("checkpoint_manifest", {})
required = {
    "CHECKPOINT_VALID": "true",
    "REFERENCE_MODE": "reference",
    "APK_VALIDATED": "true",
    "REFERENCE_READY": "true",
    "BRAVE_CORE_TAG": expected_brave,
    "TARGET": "android-arm64",
    "BUILD_TYPE": "Release",
}
for key, value in required.items():
    if checkpoint.get(key) != value:
        raise SystemExit(
            "BRAVE_REFERENCE_GATE=FAIL checkpoint manifest %s=%r expected=%r"
            % (key, checkpoint.get(key), value)
        )
sha = checkpoint.get("CHROMIUM_SHA", "")
if not re.fullmatch(r"[0-9a-f]{40}", sha):
    raise SystemExit("BRAVE_REFERENCE_GATE=FAIL missing or malformed Chromium SHA")
if expected_sha and sha != expected_sha:
    raise SystemExit(
        "BRAVE_REFERENCE_GATE=FAIL checkpoint Chromium SHA=%s expected=%s"
        % (sha, expected_sha)
    )
if expected_chromium and checkpoint.get("CHROMIUM_TAG") != expected_chromium:
    raise SystemExit(
        "BRAVE_REFERENCE_GATE=FAIL checkpoint Chromium tag=%r expected=%r"
        % (checkpoint.get("CHROMIUM_TAG"), expected_chromium)
    )
if len(data.get("shards", [])) != int(data.get("workers", 0)) or not data.get("shards"):
    raise SystemExit("BRAVE_REFERENCE_GATE=FAIL shard count does not match worker count")
print(
    "BRAVE_REFERENCE_MANIFEST=PASS workers=%d chromium=%s sha=%s source_bytes=%s archive_bytes=%s"
    % (data["workers"], checkpoint.get("CHROMIUM_TAG", "legacy"), sha,
       data.get("source_bytes"), data.get("archive_bytes"))
)
PY

[ -s "$SRC/.git/HEAD" ] || fail "Chromium Git metadata missing"
[ -s "$CORE/.git/HEAD" ] || fail "Brave Git metadata missing"
ACTUAL_CHROMIUM_SHA="$(git -C "$SRC" rev-parse HEAD)"
ACTUAL_BRAVE_TAG="$(git -C "$CORE" describe --tags --exact-match 2>/dev/null || true)"
[ "$ACTUAL_BRAVE_TAG" = "$EXPECTED_BRAVE_CORE_TAG" ] || fail "Brave checkout tag=$ACTUAL_BRAVE_TAG expected=$EXPECTED_BRAVE_CORE_TAG"

MANIFEST_CHROMIUM_SHA="$(sed -n 's/^CHROMIUM_SHA=//p' "$WORK/.sandium/checkpoint-manifest.txt" | head -n 1)"
[ -n "$MANIFEST_CHROMIUM_SHA" ] || fail "workspace manifest has no Chromium SHA"
[ "$ACTUAL_CHROMIUM_SHA" = "$MANIFEST_CHROMIUM_SHA" ] || fail "Chromium checkout SHA=$ACTUAL_CHROMIUM_SHA differs from checkpoint=$MANIFEST_CHROMIUM_SHA"
if [ -n "$EXPECTED_CHROMIUM_SHA" ]; then
  [ "$ACTUAL_CHROMIUM_SHA" = "$EXPECTED_CHROMIUM_SHA" ] || fail "Chromium SHA=$ACTUAL_CHROMIUM_SHA expected=$EXPECTED_CHROMIUM_SHA"
fi

if [ "$EXPECTED_VANILLA_RELEASE" = "true" ]; then
  [ -s "$WORK/.sandium/source-pins.env" ] || fail "vanilla release source-pins.env missing"
  grep -Fx "BRAVE_CORE_TAG=$EXPECTED_BRAVE_CORE_TAG" "$WORK/.sandium/source-pins.env" >/dev/null || fail "source-pins.env Brave tag mismatch"
  grep -Fx "CHROMIUM_TAG=$EXPECTED_CHROMIUM_TAG" "$WORK/.sandium/source-pins.env" >/dev/null || fail "source-pins.env Chromium tag mismatch"
  grep -Fx "CHROMIUM_SHA=$ACTUAL_CHROMIUM_SHA" "$WORK/.sandium/source-pins.env" >/dev/null || fail "source-pins.env Chromium SHA mismatch"
fi

[ -s "$OUT/build.ninja" ] || fail "Ninja build graph missing"
[ -s "$OUT/args.gn" ] || fail "GN args missing"
[ -s "$OUT/args_generated.gni" ] || fail "generated GN args missing"
[ -s "$SRC/build/config/siso/.sisorc" ] || fail "Siso config missing"
[ -s "$SRC/build/config/siso/.sisoenv" ] || fail "Siso environment missing"
[ -s "$SRC/build/config/siso/backend_config/backend.star" ] || fail "Siso backend missing"
if [ ! -s "$OUT/.siso_fs_state" ] && [ ! -s "$OUT/.siso_fs_state.journal" ]; then
  fail "neither Siso filesystem state nor its journal is present"
fi

if [ "$EXPECTED_VANILLA_RELEASE" = "true" ]; then
  ARGS="$OUT/args_generated.gni"
  grep -Eq '^[[:space:]]*is_official_build[[:space:]]*=[[:space:]]*true[[:space:]]*$' "$ARGS" || fail "official Brave Release build flag is not true"
  grep -Eq '^[[:space:]]*android_aab_to_apk[[:space:]]*=[[:space:]]*true[[:space:]]*$' "$ARGS" || fail "AAB-to-Universal-APK conversion is not enabled"
  grep -Eq '^[[:space:]]*target_android_output_format[[:space:]]*=[[:space:]]*"aab"[[:space:]]*$' "$ARGS" || fail "AAB output format is not selected"
  grep -Eq '^[[:space:]]*android_channel[[:space:]]*=[[:space:]]*"stable"[[:space:]]*$' "$ARGS" || fail "stable Android channel is not selected"
  grep -Eq '^[[:space:]]*chrome_public_manifest_package[[:space:]]*=[[:space:]]*"com.brave.browser"[[:space:]]*$' "$ARGS" || fail "official Brave Android package id is not selected"
  grep -Eq '^[[:space:]]*use_remoteexec[[:space:]]*=[[:space:]]*true[[:space:]]*$' "$ARGS" || fail "remote execution is not enabled"
  grep -Eq '^[[:space:]]*use_siso[[:space:]]*=[[:space:]]*true[[:space:]]*$' "$ARGS" || fail "Siso is not enabled"
  grep -Eq '^[[:space:]]*use_reclient[[:space:]]*=[[:space:]]*false[[:space:]]*$' "$ARGS" || fail "reclient must remain disabled"

  APK="$OUT/apks/Bravearm64Universal.apk"
  TOOLS="$SRC/third_party/android_sdk/public/build-tools/37.0.0"
  [ -s "$APK" ] || fail "Bravearm64Universal.apk missing from promoted reference"
  python3 "$ROOT/.circleci/scripts/analyze-brave-apk-size.py" "$APK" --require-arm64-only --output "$WORK/.sandium/reference-apk-size-report.txt"
  python3 - "$APK" <<'PY'
import sys
import zipfile
with zipfile.ZipFile(sys.argv[1]) as archive:
    bad = archive.testzip()
    if bad:
        raise SystemExit("BRAVE_REFERENCE_GATE=FAIL corrupt APK member: " + bad)
PY
  [ -x "$TOOLS/apksigner" ] && [ -x "$TOOLS/aapt" ] || fail "pinned Android APK verification tools missing"
  "$TOOLS/apksigner" verify "$APK" >/dev/null 2>&1 || fail "APK signature verification failed"
  BADGING="$WORK/.sandium/reference-apk-badging.txt"
  "$TOOLS/aapt" dump badging "$APK" > "$BADGING" 2>/dev/null || fail "aapt could not read the APK manifest"
  PACKAGE="$(sed -n "s/^package: name='\\([^']*\\)'.*/\\1/p" "$BADGING" | head -n 1)"
  APP_LABEL="$(sed -n "s/^application-label:'\\(.*\\)'$/\\1/p" "$BADGING" | head -n 1)"
  [ "$PACKAGE" = "com.brave.browser" ] || fail "APK package id=$PACKAGE expected=com.brave.browser"
  [ "$APP_LABEL" = "Brave" ] || fail "APK app label=$APP_LABEL expected=Brave"
  echo "VANILLA_BRAVE_APK_GATE=PASS package=$PACKAGE label=$APP_LABEL bytes=$(stat -c '%s' "$APK")"
fi

echo "BRAVE_REFERENCE_GATE=PASS"
echo "BRAVE_REFERENCE_CHROMIUM=$ACTUAL_CHROMIUM_SHA"
echo "BRAVE_REFERENCE_BRAVE=$ACTUAL_BRAVE_TAG"
echo "BRAVE_REFERENCE_SHARDS=$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["shards"]))' "$MANIFEST")"
echo "BRAVE_REFERENCE_ARCHIVE_BYTES=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["archive_bytes"])' "$MANIFEST")"
