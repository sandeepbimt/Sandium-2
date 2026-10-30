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
COMPILER_GNI="$SRC/build/config/compiler/compiler.gni"
test -s "$COMPILER_GNI" || { echo "BRAVE_REMOTE_SMOKE=FAIL compiler.gni missing" >&2; exit 1; }
grep -Fq 'clang_diagnostic_dir = "clang-crashreports"' "$COMPILER_GNI" || {
  echo "BRAVE_REMOTE_SMOKE=FAIL compiler.gni still uses a parent-relative crash diagnostics path" >&2
  exit 1
}
if grep -Fq 'clang_diagnostic_dir = rebase_path("//out/clang-crashreports", root_build_dir)' "$COMPILER_GNI"; then
  echo "BRAVE_REMOTE_SMOKE=FAIL upstream parent-relative clang diagnostics setting remains" >&2
  exit 1
fi
grep -Fq -- '-fcrash-diagnostics-dir=clang-crashreports' "$OUT/build.ninja" || {
  echo "BRAVE_REMOTE_SMOKE=FAIL generated build.ninja lacks normalized crash diagnostics flag" >&2
  exit 1
}
if grep -Fq -- '-fcrash-diagnostics-dir=../clang-crashreports' "$OUT/build.ninja"; then
  echo "BRAVE_REMOTE_SMOKE=FAIL generated build.ninja still contains forbidden parent-relative output path" >&2
  exit 1
fi
echo "CLANG_DIAGNOSTIC_NINJA_GRAPH_GATE=PASS"
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

SMOKE_TARGET="mojo/public/tools/bindings:precompile_ts_templates"
SMOKE_OUTPUT="$OUT/gen/mojo/public/tools/bindings/ts_templates.zip"

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
      echo "TARGET=$SMOKE_TARGET"
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

echo "BRAVE_REMOTE_SMOKE=START target=$SMOKE_TARGET strict_remote=true remote_jobs=1 workdir_anchor=./args.gn"
# --clobber ensures this gate exercises the remote worker instead of silently
# passing because a prior checkpoint already contains the generated output.
timeout --signal=INT --kill-after=30s 180s \
  autoninja -strict_remote -C "$OUT" -j1 --clobber "$SMOKE_TARGET"

test -s "$SMOKE_OUTPUT" || {
  echo "BRAVE_REMOTE_SMOKE=FAIL target completed without $SMOKE_OUTPUT" >&2
  exit 1
}
echo "BRAVE_REMOTE_SMOKE=PASS target=$SMOKE_TARGET output=$SMOKE_OUTPUT"
