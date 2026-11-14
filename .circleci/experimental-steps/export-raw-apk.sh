#!/usr/bin/env bash
# Persist build output promptly; this is diagnostic, never a verified release.
set -euo pipefail
ROOT="${CIRCLE_WORKING_DIRECTORY:?}"
APK="$ROOT/brave-work/src/out/android_Release_arm64/apks/BraveMonoarm64.apk"
DEST="$ROOT/brave-apk-raw"
if [ ! -s "$APK" ]; then
  echo 'RAW_APK_ARTIFACT=ABSENT; no APK exists yet'
  exit 0
fi
mkdir -p "$DEST"
cp "$APK" "$DEST/Sandium-unverified-raw.apk"
sha256sum "$DEST/Sandium-unverified-raw.apk" > "$DEST/Sandium-unverified-raw.apk.sha256"
printf 'VERIFICATION=pending\nSOURCE_REVISION=%s\nNOTICE=Diagnostic build output, not a verified release. Use the separately validated brave-apk artifact only after its validation passes.\n' "${CIRCLE_SHA1:-unknown}" > "$DEST/UNVERIFIED.txt"
echo 'RAW_APK_ARTIFACT=COPIED_UNVERIFIED; native artifact upload follows before APK validation/checkpoint work'
