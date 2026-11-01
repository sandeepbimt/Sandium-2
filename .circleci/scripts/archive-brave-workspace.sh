#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-}"
ROOT="${CIRCLE_WORKING_DIRECTORY:-$(pwd)}"
WORK="$ROOT/brave-work"
ARCHIVE="$ROOT/brave-workspace-checkpoint.tar.zst"
TMP="$ARCHIVE.tmp"
OUT="$WORK/src/out/android_Release_arm64"
LEDGER="$WORK/.sandium/action-ledger.json"
MANIFEST="$WORK/.sandium/checkpoint-manifest.txt"

fail() {
  echo "BRAVE_WORKSPACE_ARCHIVE=FAIL $*" >&2
  exit 1
}

ensure_zstd() {
  if ! command -v zstd >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y zstd
  fi
  command -v zstd >/dev/null 2>&1 || fail "zstd is unavailable"
}

validate_ledger() {
  [ -s "$LEDGER" ] || fail "missing action ledger: $LEDGER"
  python3 - "$LEDGER" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as stream:
    ledger = json.load(stream)
if ledger.get("schema_version") != 2:
    raise SystemExit("BRAVE_WORKSPACE_ARCHIVE=FAIL unsupported ledger schema")
if ledger.get("active_stage"):
    raise SystemExit("BRAVE_WORKSPACE_ARCHIVE=FAIL an action stage is still active")
total = int(ledger.get("planned_total", -1))
completed = len(ledger.get("completed", {}))
pending = ledger.get("next_pending_action_keys")
remaining = total - completed
if total < 0 or completed > total or not isinstance(pending, list):
    raise SystemExit("BRAVE_WORKSPACE_ARCHIVE=FAIL invalid action-ledger fields")
if len(pending) != remaining or len(set(pending)) != remaining:
    raise SystemExit("BRAVE_WORKSPACE_ARCHIVE=FAIL pending action set does not reconcile with total-completed")
print("BRAVE_WORKSPACE_ACTION_LEDGER=PASS completed=%d total=%d pending=%d" %
      (completed, total, remaining))
PY
}

case "$MODE" in
  restore)
    ensure_zstd
    if [ -s "$ARCHIVE" ]; then
      echo "BRAVE_WORKSPACE_ARCHIVE_RESTORE=START bytes=$(stat -c '%s' "$ARCHIVE")"
      zstd -t "$ARCHIVE" >/dev/null || fail "checkpoint archive failed zstd integrity test"
      zstd -dc "$ARCHIVE" | tar -xf - -C "$ROOT"
      [ -s "$WORK/.gclient" ] || fail "restored archive is missing brave-work/.gclient"
      [ -s "$OUT/build.ninja" ] || fail "restored archive is missing the pinned build graph"
      validate_ledger
      mkdir -p "$WORK/.sandium"
      touch "$WORK/.sandium/workspace-checkpoint-restored"
      echo "BRAVE_WORKSPACE_ARCHIVE_RESTORE=PASS checkpoint=RESTORED"
    elif [ -s "$WORK/.gclient" ] && [ -s "$OUT/build.ninja" ]; then
      # One-time migration path when CircleCI restored the previous v3
      # direct-directory cache instead of the new single-file archive.
      echo "BRAVE_WORKSPACE_ARCHIVE_RESTORE=LEGACY_DIRECT_CACHE stage=${BRAVE_STAGE_INDEX:-unknown}"
    elif [ "${BRAVE_STAGE_INDEX:-1}" = "1" ]; then
      echo "BRAVE_WORKSPACE_ARCHIVE_RESTORE=FIRST_BUILD no prior checkpoint; source initialization will create the baseline"
    else
      fail "no workspace archive or legacy checkpoint was restored for stage ${BRAVE_STAGE_INDEX:-unknown}"
    fi
    ;;
  archive)
    [ -d "$WORK/src" ] || fail "missing $WORK/src"
    [ -s "$WORK/.gclient" ] || fail "missing $WORK/.gclient"
    [ -s "$OUT/build.ninja" ] || fail "missing $OUT/build.ninja"
    [ -s "$MANIFEST" ] || fail "missing validated checkpoint manifest"
    grep -qx "CHECKPOINT_VALID=true" "$MANIFEST" || fail "checkpoint manifest is not marked valid"
    validate_ledger
    ensure_zstd
    rm -f "$TMP"
    echo "BRAVE_WORKSPACE_ARCHIVE_CREATE=START"
    echo "BRAVE_WORKSPACE_ARCHIVE_SOURCE=$WORK"
    echo "BRAVE_WORKSPACE_ARCHIVE_OUTPUT=$TMP"
    START="$(date +%s)"
    tar -c \
      --format=posix \
      --pax-option='delete=atime,delete=ctime' \
      --warning=no-file-changed \
      -C "$ROOT" brave-work \
      | zstd -T0 -1 -q -o "$TMP"
    [ -s "$TMP" ] || fail "tar/zstd produced an empty checkpoint"
    zstd -t "$TMP" >/dev/null || fail "new checkpoint failed zstd integrity test"
    mv "$TMP" "$ARCHIVE"
    END="$(date +%s)"
    {
      echo "ARCHIVE_VALID=true"
      echo "ARCHIVE_FORMAT=tar+zstd+pax"
      echo "ARCHIVE_SIZE_BYTES=$(stat -c '%s' "$ARCHIVE")"
      echo "ARCHIVE_SHA256=$(sha256sum "$ARCHIVE" | awk '{print $1}')"
      echo "ARCHIVE_SECONDS=$((END - START))"
      echo "ACTION_LEDGER_TOTAL=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["planned_total"])' "$LEDGER")"
      echo "ACTION_LEDGER_COMPLETED=$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["completed"]))' "$LEDGER")"
    } > "$ROOT/brave-workspace-checkpoint.meta"
    cat "$ROOT/brave-workspace-checkpoint.meta"
    echo "BRAVE_WORKSPACE_ARCHIVE_CREATE=PASS"
    ;;
  *)
    fail "usage: $0 {restore|archive}"
    ;;
esac
