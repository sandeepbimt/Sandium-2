#!/usr/bin/env bash
set -euo pipefail

ROOT="$CIRCLE_WORKING_DIRECTORY"
STAGE="$BRAVE_STAGE_INDEX"
SRC="$ROOT/brave-work/src"
OUT="$SRC/out/android_Release_arm64"
DEPOT_TOOLS="$SRC/brave/vendor/depot_tools"
PYTHON_REMOTE_WRAPPER="$SRC/buildtools/reclient_cfgs/python/python_remote_wrapper"
SISO_BRAVE_CONFIG="$SRC/build/config/siso/brave_siso_config.star"
DIAGNOSTICS="$ROOT/brave-apk/siso-diagnostics"

# Run the worker compatibility preflight exactly once, in Stage 2.
# Stages 3-5 inherit the validated Stage 2 workspace; do not re-clobber the
# expensive host-tool dependency graph on every checkpoint transition.
if [ "$STAGE" != "2" ]; then
  echo "BRAVE_REMOTE_SMOKE=SKIP stage=$STAGE reason=stage-2-preflight-only"
  exit 0
fi

test -s "$OUT/build.ninja" || { echo "BRAVE_REMOTE_SMOKE=FAIL missing build.ninja" >&2; exit 1; }
bash "$ROOT/.circleci/scripts/verify-clang-diagnostics-gn.sh"
test -s "$OUT/args.gn" || { echo "BRAVE_REMOTE_SMOKE=FAIL missing args.gn anchor input" >&2; exit 1; }
test -x "$DEPOT_TOOLS/autoninja" || { echo "BRAVE_REMOTE_SMOKE=FAIL Brave autoninja is not executable" >&2; exit 1; }
test -s "$PYTHON_REMOTE_WRAPPER" || { echo "BRAVE_REMOTE_SMOKE=FAIL Brave Python remote wrapper missing" >&2; exit 1; }
test -x "$PYTHON_REMOTE_WRAPPER" || { echo "BRAVE_REMOTE_SMOKE=FAIL Brave Python remote wrapper lacks executable mode" >&2; exit 1; }
grep -Fq 'rule["canonicalize_dir"] = True' "$SISO_BRAVE_CONFIG" || {
  echo "BRAVE_REMOTE_SMOKE=FAIL Siso output-directory canonicalization must remain enabled" >&2
  exit 1
}
grep -Fq '"./args.gn"' "$SISO_BRAVE_CONFIG" || {
  echo "BRAVE_REMOTE_SMOKE=FAIL Siso rules do not include the explicit ./args.gn working-directory anchor" >&2
  exit 1
}

export PATH="$DEPOT_TOOLS:$PATH"
export PYTHONPATH="$SRC/brave/script:$SRC/tools/grit/grit/extern:$SRC/brave/vendor/requests:$SRC/build:$DEPOT_TOOLS"
# Match the remote capacity observed in earlier successful BuildBuddy runs.
# autoninja -j maps to Siso --remote_jobs when remote execution is enabled.
# A value of 1 serializes the ~500 host-tool prerequisites and cannot meet a
# short smoke-test timeout.
REMOTE_JOBS="${SANDIUM_REMOTE_SMOKE_JOBS:-40}"
case "$REMOTE_JOBS" in
  ''|*[!0-9]*|0) echo "BRAVE_PROTO_REMOTE_SMOKE=FAIL invalid remote job limit: $REMOTE_JOBS" >&2; exit 1 ;;
esac
if [ "$REMOTE_JOBS" -gt 80 ]; then
  echo "BRAVE_PROTO_REMOTE_SMOKE=FAIL remote job limit exceeds pipeline cap: $REMOTE_JOBS" >&2
  exit 1
fi
export SISO_LIMITS="local=1,remote=$REMOTE_JOBS"
cd "$SRC"

# Force the exact Perfetto generated-header action implicated in the earlier
# GLIBC failure. This pulls in Chromium's clang_x64/protoc and cppgen_plugin.
PROTO_SMOKE_TARGET="clang_x64/gen/third_party/perfetto/protos/perfetto/config/priority_boost/priority_boost_config.gen.h"
PROTO_SMOKE_OUTPUT="$OUT/$PROTO_SMOKE_TARGET"

FAILED_REMOTE_TARGET="worker preflight not started"
collect_diagnostics() {
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    mkdir -p "$DIAGNOSTICS"
    for file in siso.INFO siso_output siso_failed_commands.sh; do
      if [ -e "$OUT/$file" ]; then
        cp -a "$OUT/$file" "$DIAGNOSTICS/"
      fi
    done
    {
      echo "BRAVE_REMOTE_SMOKE=FAIL"
      echo "STAGE=$STAGE"
      echo "FAILED_TARGET=$FAILED_REMOTE_TARGET"
      echo "PROTO_TARGET=$PROTO_SMOKE_TARGET"
      echo "GENERIC_TARGET=$SMOKE_TARGET"
      echo "WRAPPER_MODE=$(stat -c '%a' "$PYTHON_REMOTE_WRAPPER" 2>/dev/null || echo unavailable)"
      echo "SISO_CANONICALIZE_DIR=true"
      echo "SISO_WORKDIR_ANCHOR=./args.gn"
      date -u +"FAILED_AT=%Y-%m-%dT%H:%M:%SZ"
    } > "$DIAGNOSTICS/remote-smoke-status.txt"
    echo "Siso diagnostics copied to $DIAGNOSTICS" >&2
  fi
  return "$rc"
}
trap collect_diagnostics EXIT

FAILED_REMOTE_TARGET="$PROTO_SMOKE_TARGET"
echo "BRAVE_PROTO_REMOTE_SMOKE=START target=$PROTO_SMOKE_TARGET strict_remote=true remote_jobs=$REMOTE_JOBS timeout_seconds=600"
# The first pass compiles the host protoc/cppgen prerequisites as well as the
# generator action. Use the remote pool in parallel; keep a bounded 10m cap.
timeout --signal=INT --kill-after=30s 600s \
  autoninja -strict_remote -C "$OUT" "-j$REMOTE_JOBS" --clobber "$PROTO_SMOKE_TARGET"

test -s "$PROTO_SMOKE_OUTPUT" || {
  echo "BRAVE_PROTO_REMOTE_SMOKE=FAIL target completed without $PROTO_SMOKE_OUTPUT" >&2
  exit 1
}
echo "BRAVE_PROTO_REMOTE_SMOKE=PASS target=$PROTO_SMOKE_TARGET output=$PROTO_SMOKE_OUTPUT"
