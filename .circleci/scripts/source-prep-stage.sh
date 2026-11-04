#!/usr/bin/env bash
set -euo pipefail
STAGE="${1:?usage: source-prep-stage.sh <1..5>}"
case "$STAGE" in 1|2|3|4|5) ;; *) echo "SOURCE_PREP_STAGE=FAIL invalid stage=$STAGE" >&2; exit 2 ;; esac
ROOT="${CIRCLE_WORKING_DIRECTORY:?CIRCLE_WORKING_DIRECTORY is required}"
WORK="$ROOT/brave-work"; SRC="$WORK/src"; CORE="$SRC/brave"; STATE="$WORK/.sandium"
PINS="$STATE/source-pins.env"
REQUEST_FILE="$ROOT/.circleci/source-pin-refresh-id"
REQUEST_ID="$(tr -d '\r\n' < "$REQUEST_FILE")"
SLICE_SECONDS="${SANDIUM_PIN_SLICE_SECONDS:-1800}"
case "$SLICE_SECONDS" in ''|*[!0-9]*) echo "PINNING_SLICE=FAIL invalid seconds=$SLICE_SECONDS" >&2; exit 2 ;; esac
[ "$SLICE_SECONDS" -le 1800 ] || SLICE_SECONDS=1800
[ "$SLICE_SECONDS" -ge 60 ] || { echo "PINNING_SLICE=FAIL minimum 60 seconds" >&2; exit 2; }
mkdir -p "$STATE"
# A no-op source slice must not create another multi-gigabyte archive.
rm -f "$STATE/source-archive-unchanged"
OLD_REQUEST_ID="$(sed -n 's/^REFRESH_REQUEST_ID=//p' "$STATE/source-prep-progress.txt" 2>/dev/null | head -n 1 || true)"
PIN_REQUEST_ID="$(sed -n 's/^REFRESH_REQUEST_ID=//p' "$PINS" 2>/dev/null | head -n 1 || true)"
if { [ -n "$OLD_REQUEST_ID" ] && [ "$OLD_REQUEST_ID" != "$REQUEST_ID" ]; } || \
   { [ -n "$PIN_REQUEST_ID" ] && [ "$PIN_REQUEST_ID" != "$REQUEST_ID" ]; }; then
  echo "PINNING_REFRESH_REQUEST=NEW previous_progress=${OLD_REQUEST_ID:-unknown} previous_pins=${PIN_REQUEST_ID:-legacy-or-missing} current=$REQUEST_ID"
  rm -f "$PINS" "$STATE/source-sync-complete" "$STATE/source-runhooks-complete" \
    "$STATE/source-configure-complete" "$STATE/source-gn-complete" \
    "$STATE/source-ready-restored" "$STATE/source-ready" "$STATE/source-archive-unchanged"
fi
if [ ! -s "$PINS" ]; then
  if [ "$STAGE" = "1" ]; then
    # Stage 1 alone may bootstrap a new source pin. Resolve the latest stable
    # Brave release, derive its Chromium tag from Brave Core, and resolve that
    # exact Chromium tag to an immutable SHA before source synchronization.
    echo "PINNING_BOOTSTRAP=REQUIRED stage=1 reason=source-pins-missing-or-refresh-request-changed"
    rm -f "$STATE/source-sync-complete" "$STATE/source-runhooks-complete" \
      "$STATE/source-configure-complete" "$STATE/source-gn-complete" \
      "$STATE/source-ready-restored" "$STATE/source-ready"
  else
    echo "PINNING_GATE=FAIL source-pins.env missing after stage checkpoint restore; refusing to guess pins" >&2
    exit 1
  fi
fi
START_SECONDS=$SECONDS
DEADLINE=$((START_SECONDS + SLICE_SECONDS))
TIME_SLICE_EXPIRED=false
run_phase() {
  local phase="$1" phase_stage="$2" marker="$3"
  if [ -s "$marker" ]; then echo "PINNING_PHASE=REUSE phase=$phase marker=$marker"; return 0; fi
  local remaining=$((DEADLINE - SECONDS))
  if [ "$remaining" -le 0 ]; then TIME_SLICE_EXPIRED=true; return 2; fi
  echo "PINNING_PHASE=START phase=$phase stage=$STAGE remaining_seconds=$remaining budget_seconds=$SLICE_SECONDS"
  set +e
  BRAVE_STAGE_INDEX="$phase_stage" SANDIUM_PINNING_STAGE_INDEX="$STAGE" SANDIUM_SOURCE_PREP_PHASE="$phase" timeout --signal=INT --kill-after=30s "${remaining}s" bash "$ROOT/.circleci/scripts/prepare-brave-source.sh"
  local rc=$?
  set -e
  if [ "$rc" -eq 0 ]; then touch "$marker"; echo "PINNING_PHASE=PASS phase=$phase elapsed_seconds=$((SECONDS-START_SECONDS))"; return 0; fi
  if [ "$rc" -eq 124 ] || { { [ "$rc" -eq 130 ] || [ "$rc" -eq 137 ]; } && [ "$((SECONDS-START_SECONDS))" -ge "$((SLICE_SECONDS-30))" ]; }; then
    TIME_SLICE_EXPIRED=true
    echo "PINNING_PHASE=SLICE_END phase=$phase elapsed_seconds=$((SECONDS-START_SECONDS)); preserving resumable state"
    return 2
  fi
  echo "PINNING_PHASE=FAIL phase=$phase exit=$rc" >&2
  return "$rc"
}
run_phase sync 1 "$STATE/source-sync-complete" || { rc=$?; [ "$rc" -eq 2 ] || exit "$rc"; }
if [ "$TIME_SLICE_EXPIRED" = false ]; then run_phase hooks 2 "$STATE/source-runhooks-complete" || { rc=$?; [ "$rc" -eq 2 ] || exit "$rc"; }; fi
if [ "$TIME_SLICE_EXPIRED" = false ]; then run_phase configure 3 "$STATE/source-configure-complete" || { rc=$?; [ "$rc" -eq 2 ] || exit "$rc"; }; fi
if [ "$TIME_SLICE_EXPIRED" = false ]; then run_phase gn 4 "$STATE/source-gn-complete" || { rc=$?; [ "$rc" -eq 2 ] || exit "$rc"; }; fi
RESTORED_READY=false
if [ -s "$STATE/source-ready-restored" ] && [ "$PIN_REQUEST_ID" = "$REQUEST_ID" ]; then
  RESTORED_READY=true
fi
READY=false; PHASE=pinning-incomplete
if [ -s "$STATE/source-sync-complete" ] && [ -s "$STATE/source-runhooks-complete" ] && [ -s "$STATE/source-configure-complete" ] && [ -s "$STATE/source-gn-complete" ]; then
  test -s "$WORK/.gclient"; test -s "$WORK/.gclient_entries"; test -s "$PINS"
  test -s "$CORE/node_modules/.modules.yaml"; test -d "$CORE/node_modules/.pnpm"
  OUT="$SRC/out/android_Release_arm64"
  test -s "$OUT/build.ninja"; test -s "$OUT/args.gn"; test -s "$OUT/args_generated.gni"
  test -s "$SRC/build/config/siso/.sisoenv"; test -s "$SRC/build/config/siso/.sisorc"
  test -s "$SRC/build/config/siso/backend_config/backend.star"; test -s "$SRC/build/config/siso/brave_siso_config.star"
  test -x "$SRC/buildtools/reclient_cfgs/python/python_remote_wrapper"
  ACTUAL_BRAVE_TAG="$(git -C "$CORE" describe --tags --exact-match)"
  ACTUAL_CHROMIUM_SHA="$(git -C "$SRC" rev-parse HEAD)"
  EXPECTED_BRAVE_TAG="$(sed -n 's/^BRAVE_CORE_TAG=//p' "$PINS" | head -n 1)"
  EXPECTED_CHROMIUM_SHA="$(sed -n 's/^CHROMIUM_SHA=//p' "$PINS" | head -n 1)"
  test "$ACTUAL_BRAVE_TAG" = "$EXPECTED_BRAVE_TAG"; test "$ACTUAL_CHROMIUM_SHA" = "$EXPECTED_CHROMIUM_SHA"
  READY=true; PHASE=source-ready; touch "$STATE/source-ready"
  echo "SANDIUM_PINNING_REFERENCE=READY brave=$ACTUAL_BRAVE_TAG chromium_sha=$ACTUAL_CHROMIUM_SHA"
fi
{
  echo "STAGE=$STAGE"; echo "PHASE=$PHASE"; echo "WORKFLOW_ID=${CIRCLE_WORKFLOW_ID:-local}"
  echo "REFRESH_REQUEST_ID=$REQUEST_ID"; cat "$PINS"
  if [ "$RESTORED_READY" = true ] && [ "$READY" = true ]; then echo "READY_ALREADY=true"; fi
  echo "PINNING_SECONDS=$((SECONDS-START_SECONDS))"; echo "SAVED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$STATE/source-prep-progress.txt"
export SANDIUM_ARCHIVE_WORKERS=8
if [ "$READY" = true ]; then
  if [ "$RESTORED_READY" = true ]; then
    touch "$STATE/source-archive-unchanged"
    echo "SANDIUM_PINNING_ARCHIVE=REUSE already-verified-ready-reference=true stage=$STAGE; no duplicate archive"
  else
    python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" archive --root "$ROOT" --workers 8 --stage "$STAGE" --ready
    python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" verify --root "$ROOT" --workers 8 --ready --zstd-test
    echo "SANDIUM_PINNING_ARCHIVE=PASS ready=true stage=$STAGE"
  fi
else
  if [ "$STAGE" = "1" ]; then
    python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" archive --root "$ROOT" --workers 8 --stage "$STAGE"
  else
    python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" archive --root "$ROOT" --workers 8 --stage "$STAGE" --skip-if-unchanged
  fi
  if [ -s "$STATE/source-archive-unchanged" ]; then
    echo "SANDIUM_PINNING_ARCHIVE=REUSE unchanged_source_state=true stage=$STAGE; do not upload duplicate shards"
  else
    python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" verify --root "$ROOT" --workers 8
    echo "SANDIUM_PINNING_ARCHIVE=PASS ready=false stage=$STAGE; next stage resumes"
  fi
fi
