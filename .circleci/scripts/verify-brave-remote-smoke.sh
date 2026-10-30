#!/usr/bin/env bash
set -euo pipefail

ROOT="$CIRCLE_WORKING_DIRECTORY"
STAGE="$BRAVE_STAGE_INDEX"
SRC="$ROOT/brave-work/src"
OUT="$SRC/out/android_Debug_arm64"
DEPOT_TOOLS="$SRC/brave/vendor/depot_tools"
PYTHON_REMOTE_WRAPPER="$SRC/buildtools/reclient_cfgs/python/python_remote_wrapper"
SISO_BRAVE_CONFIG="$SRC/build/config/siso/brave_siso_config.star"
DIAGNOSTICS="$ROOT/brave-apk/siso-diagnostics"

if [ "$STAGE" = "1" ]; then
  echo "BRAVE_REMOTE_SMOKE=SKIP stage=1"
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
export SISO_LIMITS="local=1,remote=1"
cd "$SRC"

# Force the exact host-tool action family that failed in Stage 2.
# It executes Chromium's Linux host protoc via protoc_wrapper, under strict
# remote execution, and therefore validates worker glibc before the large build.
PROTO_SMOKE_TARGET="clang_x64/gen/third_party/perfetto/protos/perfetto/config/priority_boost/priority_boost_config.gen.h"
PROTO_SMOKE_OUTPUT="$OUT/$PROTO_SMOKE_TARGET"

# Keep a second generic remote action as a broad Siso/BuildBuddy sanity check.
SMOKE_TARGET="mojo/public/tools/bindings:precompile_ts_templates"
SMOKE_OUTPUT="$OUT/gen/mojo/public/tools/bindings/ts_templates.zip"

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
echo "BRAVE_PROTO_REMOTE_SMOKE=START target=$PROTO_SMOKE_TARGET strict_remote=true remote_jobs=1"
# This is deliberately a real Perfetto cpp_gen output from the failing log.
# --clobber guarantees protoc is launched remotely even if the output was
# restored in the previous checkpoint. Do not start the full build unless it
# succeeds against the configured Ubuntu 22.04 worker image.
timeout --signal=INT --kill-after=30s 180s \
  autoninja -strict_remote -C "$OUT" -j1 --clobber "$PROTO_SMOKE_TARGET"

test -s "$PROTO_SMOKE_OUTPUT" || {
  echo "BRAVE_PROTO_REMOTE_SMOKE=FAIL target completed without $PROTO_SMOKE_OUTPUT" >&2
  exit 1
}
echo "BRAVE_PROTO_REMOTE_SMOKE=PASS target=$PROTO_SMOKE_TARGET"

FAILED_REMOTE_TARGET="$SMOKE_TARGET"
echo "BRAVE_REMOTE_SMOKE=START target=$SMOKE_TARGET strict_remote=true remote_jobs=1 workdir_anchor=./args.gn"
# --clobber ensures this gate exercises a generic remote action too.
timeout --signal=INT --kill-after=30s 180s \
  autoninja -strict_remote -C "$OUT" -j1 --clobber "$SMOKE_TARGET"

test -s "$SMOKE_OUTPUT" || {
  echo "BRAVE_REMOTE_SMOKE=FAIL target completed without $SMOKE_OUTPUT" >&2
  exit 1
}
echo "BRAVE_REMOTE_SMOKE=PASS target=$SMOKE_TARGET output=$SMOKE_OUTPUT"
