set -uo pipefail
ROOT="$CIRCLE_WORKING_DIRECTORY"
mkdir -p "$ROOT/brave-work/.sandium"
STATUS="$ROOT/brave-work/.sandium/remote-smoke-status.txt"
if [ -s "$ROOT/brave-work/.sandium/restored-apk-valid" ]; then
  printf 'REMOTE_SMOKE=SKIPPED_VALID_APK\n' > "$STATUS"
  echo "BRAVE_REMOTE_SMOKE=SKIPPED reason=already-verified-apk"
else
  export BRAVE_STAGE_INDEX="${SANDIUM_STAGE}"
  if bash .circleci/scripts/verify-brave-remote-smoke.sh; then
    printf 'REMOTE_SMOKE=PASS\n' > "$STATUS"
    echo "BRAVE_REMOTE_SMOKE_STATUS=PASS"
  else
    RC=$?
    printf 'REMOTE_SMOKE=WARNING\nREMOTE_SMOKE_EXIT_CODE=%s\n' "$RC" > "$STATUS"
    echo "BRAVE_REMOTE_SMOKE_STATUS=WARNING exit=$RC; continuing to the real APK build under -strict_remote. Main APK metrics are authoritative."
  fi
fi
