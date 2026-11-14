set -euo pipefail
ROOT="$CIRCLE_WORKING_DIRECTORY"
OUT="$ROOT/brave-work/src/out/android_Release_arm64"
STATUS_DIR="$ROOT/brave-work/.sandium"
mkdir -p "$STATUS_DIR"
BUILD_STATUS="$STATUS_DIR/build-stage-status.txt"
SMOKE_STATUS="$STATUS_DIR/remote-smoke-status.txt"
if [ -s "$STATUS_DIR/restored-apk-valid" ]; then
  echo "BRAVE_APK=ALREADY_PRESENT_AND_VERIFIED"
  printf 'BUILD_EXIT_CODE=0\nBUILD_REASON=RESTORED_VALID_APK\n' > "$BUILD_STATUS"
  exit 0
fi
if [ ! -s "$OUT/build.ninja" ]; then
  echo "BRAVE_BUILD_GRAPH_GATE=FAIL missing $OUT/build.ninja" >&2
  exit 1
fi
if [ -z "$(printenv BUILDBUDDY_API_KEY 2>/dev/null || true)" ]; then
  echo "MISSING_REQUIRED_SECRET=BUILDBUDDY_API_KEY" >&2
  exit 1
fi
if ! grep -Eq '^REMOTE_SMOKE=(PASS|WARNING|SKIPPED_VALID_APK)$' "$SMOKE_STATUS" 2>/dev/null; then
  echo "BRAVE_REMOTE_SMOKE_STATUS=UNKNOWN; refusing to start a build without a recorded preflight outcome." >&2
  exit 2
fi
if grep -qx 'REMOTE_SMOKE=WARNING' "$SMOKE_STATUS"; then
  echo "BRAVE_REMOTE_SMOKE=WARNING; not blocking compilation. The Android APK build will run with -strict_remote and its own Siso metrics will be audited."
fi
ROOT_SRC="$ROOT/brave-work/src"
BRAVE_DEPOT_TOOLS="$ROOT_SRC/brave/vendor/depot_tools"
test -s "$ROOT/brave-work/.gclient" || { echo "BRAVE_GCLIENT_ROOT_GATE=FAIL missing .gclient" >&2; exit 1; }
test -s "$ROOT/brave-work/.gclient_entries" || { echo "BRAVE_GCLIENT_ROOT_GATE=FAIL missing .gclient_entries" >&2; exit 1; }
test -x "$BRAVE_DEPOT_TOOLS/autoninja" || { echo "BRAVE_GCLIENT_ROOT_GATE=FAIL Brave autoninja missing" >&2; exit 1; }
export PATH="$BRAVE_DEPOT_TOOLS:$PATH"
export DEPOT_TOOLS_UPDATE=0
cd "$ROOT_SRC"
export PYTHONPATH="$ROOT_SRC/brave/script:$ROOT_SRC/tools/grit/grit/extern:$ROOT_SRC/brave/vendor/requests:$ROOT_SRC/build:$BRAVE_DEPOT_TOOLS${PYTHONPATH:+:$PYTHONPATH}"
"$ROOT_SRC/third_party/cpython3/host/bin/python3" -c 'from brave_version_utils import generate_base_version_code; assert generate_base_version_code(1, 2) > 0; print("BRAVE_PYTHONPATH_GATE=PASS")'
python3 -c 'import os,sys,gclient_paths; expected=os.path.realpath(sys.argv[1]); actual=gclient_paths.GetPrimarySolutionPath(); assert actual is not None and os.path.realpath(actual)==expected, "BRAVE_GCLIENT_ROOT_GATE=FAIL expected=%s actual=%s" % (expected,actual); print("BRAVE_GCLIENT_ROOT_GATE=PASS src=%s" % actual)' "$ROOT_SRC"
export BRAVE_STAGE_INDEX="${SANDIUM_STAGE}"
bash "$ROOT/.circleci/scripts/capture-brave-siso-checkpoint.sh" before-build
BUILD_RC=0
INITIAL_BUILD_RC=0
CAS_RECOVERY_COUNT=0
trap 'rc=$?; BRAVE_BUILD_EXIT_CODE="${BUILD_RC:-$rc}" BRAVE_BUILD_INITIAL_EXIT_CODE="${INITIAL_BUILD_RC:-not_set}" BRAVE_BUILD_INITIAL_TIMEOUT="$([ "${INITIAL_BUILD_RC:-0}" -eq 124 ] && echo true || ([ "${INITIAL_BUILD_RC:-0}" -eq 130 ] && echo true || echo false))" bash "$ROOT/.circleci/scripts/capture-brave-siso-checkpoint.sh" after-build || echo "BRAVE_SISO_DIAGNOSTICS=WARNING after-build capture failed"; exit "$rc"' EXIT
export SISO_LIMITS="local=8,remote=80"
METRICS_PREFIX="sandium-brave-siso-stage-${SANDIUM_STAGE}-build-${CIRCLE_BUILD_NUM:-local}-attempt-"
METRICS_FILE="${METRICS_PREFIX}0.jsonl"
BUILD_MODE="full"
STAGE_BUILD_BUDGET_SECONDS="$(python3 "$ROOT/.circleci/checkpoint/full_job_budget.py" "$ROOT")"
STAGE_BUILD_DEADLINE=$((SECONDS + STAGE_BUILD_BUDGET_SECONDS))
echo "BRAVE_BUILD_MODE=full"
echo "SANDIUM_CI_NAME=SANDIUM-FULL-MODE"
echo "BRAVE_BUILD_SLICE_BUDGET_SECONDS=$STAGE_BUILD_BUDGET_SECONDS metrics=$METRICS_FILE"
timeout --signal=INT --kill-after=60s "${STAGE_BUILD_BUDGET_SECONDS}s" autoninja -strict_remote -metrics_json "$METRICS_FILE" -C "$OUT" -j80 brave || BUILD_RC=$?
INITIAL_BUILD_RC="$BUILD_RC"
while [ "$BUILD_RC" -ne 0 ] && [ "$BUILD_RC" -ne 124 ] && [ "$BUILD_RC" -ne 130 ] \
  && [ "$CAS_RECOVERY_COUNT" -lt 2 ] \
  && [ -s "$OUT/siso_output" ] \
  && grep -Eq 'rpc error: code = FailedPrecondition desc = download inputs: could not (fetch inputs|get input tree): Digest hash:.*not found' "$OUT/siso_output"; do
  CAS_RECOVERY_COUNT=$((CAS_RECOVERY_COUNT + 1))
  echo "BRAVE_CAS_LOCAL_RECOVERY_ATTEMPT=$CAS_RECOVERY_COUNT"
  LOCAL_RECOVERY_METRICS_FILE="${METRICS_PREFIX}${CAS_RECOVERY_COUNT}-local-recovery.jsonl"
  REMAINING_STAGE_SECONDS=$((STAGE_BUILD_DEADLINE - SECONDS))
  if [ "$REMAINING_STAGE_SECONDS" -le 0 ]; then
    BUILD_RC=124
    echo "BRAVE_BUILD_RESUME=SKIPPED stage build budget exhausted before CAS recovery."
    break
  fi
  if timeout --signal=INT --kill-after=60s "${REMAINING_STAGE_SECONDS}s" bash "$ROOT/.circleci/scripts/recover-siso-missing-cas-inputs.sh" "$OUT" "$LOCAL_RECOVERY_METRICS_FILE"; then
    REMAINING_STAGE_SECONDS=$((STAGE_BUILD_DEADLINE - SECONDS))
    if [ "$REMAINING_STAGE_SECONDS" -le 0 ]; then
      BUILD_RC=124
      echo "BRAVE_BUILD_RESUME=SKIPPED stage build budget exhausted after CAS recovery."
      break
    fi
    echo "BRAVE_BUILD_RESUME=START mode=strict-remote timeout_seconds=$REMAINING_STAGE_SECONDS (remaining stage budget)"
    RESUME_METRICS_FILE="${METRICS_PREFIX}${CAS_RECOVERY_COUNT}-resume.jsonl"
    BUILD_RC=0
    timeout --signal=INT --kill-after=60s "${REMAINING_STAGE_SECONDS}s" autoninja -strict_remote -metrics_json "$RESUME_METRICS_FILE" -C "$OUT" -j80 brave || BUILD_RC=$?
  else
    BUILD_RC=$?
    echo "BRAVE_CAS_LOCAL_RECOVERY=FAIL exit=$BUILD_RC; preserving outputs and metrics."
    break
  fi
done
REMOTE_EXECUTION_AUDIT=NOT_AVAILABLE
if [ -s "$OUT/$METRICS_FILE" ]; then
  if python3 "$ROOT/.circleci/scripts/verify-brave-remote-metrics.py" --audit "$OUT/$METRICS_FILE"; then
    REMOTE_EXECUTION_AUDIT=PASS
  else
    REMOTE_AUDIT_RC=$?
    REMOTE_EXECUTION_AUDIT="WARNING_EXIT_$REMOTE_AUDIT_RC"
    echo "BRAVE_REMOTE_EXECUTION_AUDIT=WARNING exit=$REMOTE_AUDIT_RC; preserving build metrics and continuing stage handoff."
  fi
else
  echo "BRAVE_REMOTE_EXECUTION_AUDIT=NOT_AVAILABLE main_metrics=$OUT/$METRICS_FILE"
fi
BUILD_TIME_SLICE_EXPIRED=false
BUILD_COMMAND_SUCCEEDED=false
BUILD_SLICE_INCOMPLETE=true
# GNU timeout returns 124 when the stage budget expires. Signal-like
# exit codes (130/137/143) alone are NOT proof of a time-slice expiry:
# a local OOM killer or an externally killed compiler can return them
# much earlier than the budget. Classify those as failed work instead.
if [ "$BUILD_RC" -eq 0 ]; then
  BUILD_REASON="BUILD_COMMAND_SUCCESS"
  BUILD_COMMAND_SUCCEEDED=true
  BUILD_SLICE_INCOMPLETE=false
elif [ "$BUILD_RC" -eq 124 ] || [ "$SECONDS" -ge "$STAGE_BUILD_DEADLINE" ]; then
  BUILD_TIME_SLICE_EXPIRED=true
  BUILD_REASON="TIME_SLICE_COMPLETE"
else
  BUILD_REASON="ACTION_FAILED_HANDOFF"
  echo "BRAVE_BUILD_COMMAND=INCOMPLETE exit=$BUILD_RC; no APK success is claimed. "
  echo "Completed actions may be checkpointed; failed actions must remain pending for the next stage."
fi
{
  echo "BUILD_EXIT_CODE=$BUILD_RC"
  echo "BUILD_INITIAL_EXIT_CODE=$INITIAL_BUILD_RC"
  echo "BUILD_REASON=$BUILD_REASON"
  echo "BUILD_TIME_SLICE_EXPIRED=$BUILD_TIME_SLICE_EXPIRED"
  echo "BUILD_COMMAND_SUCCEEDED=$BUILD_COMMAND_SUCCEEDED"
  echo "BUILD_SLICE_INCOMPLETE=$BUILD_SLICE_INCOMPLETE"
  echo "BUILD_HANDOFF_ALLOWED=true"
  echo "STAGE_BUILD_BUDGET_SECONDS=$STAGE_BUILD_BUDGET_SECONDS"
  echo "REMOTE_EXECUTION_AUDIT=$REMOTE_EXECUTION_AUDIT"
  echo "CAS_RECOVERY_ATTEMPTS=$CAS_RECOVERY_COUNT"
  echo "BUILD_WINDOW_FINISHED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$BUILD_STATUS"
if [ "$BUILD_COMMAND_SUCCEEDED" = true ]; then
  echo "BRAVE_BUILD_STAGE_STATUS=COMMAND_SUCCESS exit=$BUILD_RC reason=$BUILD_REASON remote_audit=$REMOTE_EXECUTION_AUDIT"
else
  echo "BRAVE_BUILD_STAGE_STATUS=INCOMPLETE exit=$BUILD_RC reason=$BUILD_REASON "
  echo "build_budget_seconds=$STAGE_BUILD_BUDGET_SECONDS; time_slice_expired=$BUILD_TIME_SLICE_EXPIRED; "
  echo "The build did not finish in this slice; the next stage will resume using Ninja/Siso native state."
fi
