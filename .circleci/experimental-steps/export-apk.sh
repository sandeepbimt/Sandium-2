set -uo pipefail
ROOT="$CIRCLE_WORKING_DIRECTORY"
SRC="$ROOT/brave-work/src"
OUT="$SRC/out/android_Release_arm64"
APK="$OUT/apks/BraveMonoarm64.apk"
TOOLS="$SRC/third_party/android_sdk/public/build-tools/37.0.0"
DIAGNOSTICS="$ROOT/brave-apk/siso-diagnostics"
mkdir -p "$ROOT/brave-apk" "$DIAGNOSTICS"
for file in siso.INFO siso_output siso_failed_commands.sh; do
  if [ -e "$OUT/$file" ]; then cp -a "$OUT/$file" "$DIAGNOSTICS/"; fi
done
for file in "$OUT"/sandium-brave-siso-metrics*.json "$OUT"/sandium-brave-siso-stage-*.jsonl; do
  if [ -f "$file" ]; then cp -a "$file" "$DIAGNOSTICS/"; fi
done
CHECKPOINT_DIAGNOSTICS="$ROOT/brave-work/.sandium/checkpoint-diagnostics"
if [ -d "$CHECKPOINT_DIAGNOSTICS" ]; then cp -a "$CHECKPOINT_DIAGNOSTICS" "$ROOT/brave-apk/"; fi
ARCHIVE_VALID=false
SIGNATURE_VALID=not_checked
PACKAGE_VALID=false
BRANDING_VALID=false
APK_ERROR=""
if [ -s "$APK" ]; then
  # Keep a diagnostic copy even if later validation fails.
  # This is NOT a verified release APK.
  cp "$APK" "$ROOT/brave-apk/Sandium-unverified.apk"
  sha256sum "$APK" > "$ROOT/brave-apk/Sandium-unverified.apk.sha256"
  echo "BRAVE_APK_DIAGNOSTIC_COPY=SAVED; release validation still required"
  if python3 -c 'import sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); bad=z.testzip(); z.close(); sys.exit(1 if bad else 0)' "$APK"; then
    ARCHIVE_VALID=true
  else
    APK_ERROR="ZIP integrity check failed"
  fi
  if [ "$ARCHIVE_VALID" = true ]; then
    if [ ! -x "$TOOLS/apksigner" ] || [ ! -x "$TOOLS/aapt" ]; then
      APK_ERROR="pinned Android apksigner/aapt tools are missing"
    elif "$TOOLS/apksigner" verify --verbose --print-certs "$APK" > "$ROOT/brave-apk/apk-signature.txt" 2>&1; then
      SIGNATURE_VALID=true
      if "$TOOLS/aapt" dump badging "$APK" > "$ROOT/brave-apk/apk-badging.txt" 2>&1; then
        PACKAGE="$(sed -n "s/^package: name='\\([^']*\\)'.*/\\1/p" "$ROOT/brave-apk/apk-badging.txt" | head -n 1)"
        APP_LABEL="$(sed -n "s/^application-label:'\\(.*\\)'$/\\1/p" "$ROOT/brave-apk/apk-badging.txt" | head -n 1)"
        if [ "$PACKAGE" = "com.brave.browser_default" ]; then
          PACKAGE_VALID=true
        else
          APK_ERROR="expected package com.brave.browser_default; got ${PACKAGE:-<missing>}"
        fi
        if [ "$APP_LABEL" = "Sandium" ]; then
          BRANDING_VALID=true
          echo "SANDIUM_APK_LABEL_GATE=PASS label=$APP_LABEL"
        else
          APK_ERROR="expected app label Sandium; got ${APP_LABEL:-<missing>}"
          echo "SANDIUM_APK_LABEL_GATE=FAIL $APK_ERROR"
        fi
      else
        APK_ERROR="aapt could not read the APK manifest"
      fi
    else
      APK_ERROR="APK signature verification failed"
    fi
  fi
fi
if [ -s "$APK" ] && [ "$ARCHIVE_VALID" = true ] && [ "$SIGNATURE_VALID" = true ] && [ "$PACKAGE_VALID" = true ] && [ "$BRANDING_VALID" = true ] && python3 "$ROOT/.circleci/scripts/apk_recipe.py" record --root "$ROOT"; then
  cp "$APK" "$ROOT/brave-apk/Sandium-Brave-test.apk"
  {
    echo "BUILD_FINISHED=true"
    echo "APK_ARCHIVE_VALID=true"
    echo "APK_SIGNATURE_VALID=true"
    echo "APK_PACKAGE_ID_VALID=true"
    echo "APK_BRANDING_VALID=true"
    echo "APK_PACKAGE_ID=com.brave.browser_default"
    echo "APK_SIZE_BYTES=$(stat -c '%s' "$APK")"
  } > "$ROOT/brave-apk/status.txt"
  echo "BRAVE_APK_VALIDATION=PASS"
else
  {
    echo "BUILD_FINISHED=false"
    echo "APK_ARCHIVE_VALID=$ARCHIVE_VALID"
    echo "APK_SIGNATURE_VALID=$SIGNATURE_VALID"
    echo "APK_PACKAGE_ID_VALID=$PACKAGE_VALID"
    echo "APK_BRANDING_VALID=$BRANDING_VALID"
    echo "APK_VALIDATION_ERROR=${APK_ERROR:-APK not produced}"
  } > "$ROOT/brave-apk/status.txt"
  echo "BRAVE_APK_VALIDATION=FAIL ${APK_ERROR:-APK not produced}"
fi
