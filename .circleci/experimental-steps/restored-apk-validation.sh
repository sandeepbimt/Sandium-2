set -euo pipefail
ROOT="$CIRCLE_WORKING_DIRECTORY"
OUT="$ROOT/brave-work/src/out/android_Release_arm64"
APK="$OUT/apks/BraveMonoarm64.apk"
TOOLS="$ROOT/brave-work/src/third_party/android_sdk/public/build-tools/37.0.0"
mkdir -p "$ROOT/brave-work/.sandium"
rm -f "$ROOT/brave-work/.sandium/restored-apk-valid"
if [ ! -s "$APK" ]; then
  echo "BRAVE_RESTORED_APK=ABSENT"
  exit 0
fi
MANIFEST="$ROOT/brave-work/.sandium/checkpoint-manifest.txt"
CURRENT_REVISION="${CIRCLE_SHA1:-${CIRCLE_SHA1}}"
REFERENCE_REVISION="$(sed -n 's/^REFERENCE_SOURCE_REVISION=//p' "$MANIFEST" | head -n 1)"
if [ -z "$REFERENCE_REVISION" ] || [ "$REFERENCE_REVISION" != "$CURRENT_REVISION" ]; then
  echo "BRAVE_RESTORED_APK=STALE_REFERENCE; reference_revision=${REFERENCE_REVISION:-missing} current_revision=$CURRENT_REVISION"
  rm -f "$APK"
  exit 0
fi
VALID=true
if ! python3 -c 'import sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); bad=z.testzip(); z.close(); sys.exit(1 if bad else 0)' "$APK"; then VALID=false; fi
if [ "$VALID" = true ] && [ -x "$TOOLS/apksigner" ] && [ -x "$TOOLS/aapt" ]; then
  "$TOOLS/apksigner" verify "$APK" >/dev/null 2>&1 || VALID=false
  if [ "$VALID" = true ]; then
    "$TOOLS/aapt" dump badging "$APK" > "$ROOT/brave-work/.sandium/restored-apk-badging.txt" 2>/dev/null || VALID=false
  fi
  PACKAGE=""
  APP_LABEL=""
  if [ "$VALID" = true ]; then
    PACKAGE="$(sed -n "s/^package: name='\\([^']*\\)'.*/\\1/p" "$ROOT/brave-work/.sandium/restored-apk-badging.txt" 2>/dev/null | head -n 1)"
    APP_LABEL="$(sed -n "s/^application-label:'\\(.*\\)'$/\\1/p" "$ROOT/brave-work/.sandium/restored-apk-badging.txt" 2>/dev/null | head -n 1)"
    [ "$PACKAGE" = "com.brave.browser_default" ] || VALID=false
    [ "$APP_LABEL" = "Sandium" ] || VALID=false
  fi
else
  VALID=false
fi
if [ "$VALID" = true ]; then
  touch "$ROOT/brave-work/.sandium/restored-apk-valid"
  echo "BRAVE_RESTORED_APK=VALID package=com.brave.browser_default label=Sandium bytes=$(stat -c '%s' "$APK")"
else
  echo "BRAVE_RESTORED_APK=INVALID; reopening only the APK output action."
  rm -f "$APK"
fi
