#!/usr/bin/env bash
set -euo pipefail

ROOT="$CIRCLE_WORKING_DIRECTORY"
if [ -z "$ROOT" ]; then
  echo "CLANG_DIAGNOSTIC_GN_GATE=FAIL CIRCLE_WORKING_DIRECTORY is required" >&2
  exit 1
fi
SRC="$ROOT/brave-work/src"
OUT="$SRC/out/android_Debug_arm64"
COMPILER_GNI="$SRC/build/config/compiler/compiler.gni"
GN="$SRC/buildtools/linux64/gn"

test -s "$COMPILER_GNI" || {
  echo "CLANG_DIAGNOSTIC_GN_GATE=FAIL missing $COMPILER_GNI" >&2
  exit 1
}
grep -Fqx '  clang_diagnostic_dir = "clang-crashreports"' "$COMPILER_GNI" || {
  echo "CLANG_DIAGNOSTIC_GN_GATE=FAIL compiler.gni is not normalized to clang-crashreports" >&2
  exit 1
}
if grep -Fq 'clang_diagnostic_dir = rebase_path("//out/clang-crashreports", root_build_dir)' "$COMPILER_GNI"; then
  echo "CLANG_DIAGNOSTIC_GN_GATE=FAIL parent-relative compiler.gni assignment remains" >&2
  exit 1
fi

test -s "$OUT/build.ninja" || {
  echo "CLANG_DIAGNOSTIC_GN_GATE=FAIL build.ninja missing; GN graph was not generated" >&2
  exit 1
}
test -x "$GN" || {
  echo "CLANG_DIAGNOSTIC_GN_GATE=FAIL GN executable missing: $GN" >&2
  exit 1
}

# GN evaluates Android version scripts with Chromium's bundled host Python.
# Those scripts import Brave's brave_version_utils from brave/script. The normal
# Brave build wrapper supplies these paths; this standalone GN diagnostic query
# must reproduce the same environment explicitly.
BRAVE_DEPOT_TOOLS="$SRC/brave/vendor/depot_tools"
export PYTHONPATH="$SRC/brave/script:$SRC/tools/grit/grit/extern:$SRC/brave/vendor/requests:$SRC/build:$BRAVE_DEPOT_TOOLS${PYTHONPATH:+:$PYTHONPATH}"
GN_HOST_PYTHON="$SRC/third_party/cpython3/host/bin/python3"
test -x "$GN_HOST_PYTHON" || {
  echo "CLANG_DIAGNOSTIC_BRAVE_PYTHONPATH_GATE=FAIL bundled host Python missing: $GN_HOST_PYTHON" >&2
  exit 1
}
"$GN_HOST_PYTHON" -c 'from brave_version_utils import generate_base_version_code; assert generate_base_version_code(1, 2) > 0; print("CLANG_DIAGNOSTIC_BRAVE_PYTHONPATH_GATE=PASS")'

# Do not grep build.ninja: GN stores compiler flags on the config/target,
# not necessarily as literal text in the top-level Ninja manifest.
# Query GN directly and preserve both output streams if the query itself fails.
# The previous command substitution swallowed GN stdout; with set -e, a nonzero
# exit ended the job without showing the reason or a CLANG_DIAGNOSTIC_GN_GATE marker.
echo "CLANG_DIAGNOSTIC_GN_QUERY=START label=//build/config/compiler:compiler field=cflags"
GN_QUERY_STDOUT="$(mktemp)"
GN_QUERY_STDERR="$(mktemp)"
if "$GN" desc "$OUT" //build/config/compiler:compiler cflags --format=json \
  >"$GN_QUERY_STDOUT" 2>"$GN_QUERY_STDERR"; then
  CFLAGS_JSON="$(cat "$GN_QUERY_STDOUT")"
  if [ -s "$GN_QUERY_STDERR" ]; then
    echo "CLANG_DIAGNOSTIC_GN_QUERY_STDERR_BEGIN"
    cat "$GN_QUERY_STDERR"
    echo "CLANG_DIAGNOSTIC_GN_QUERY_STDERR_END"
  fi
else
  GN_QUERY_STATUS=$?
  echo "CLANG_DIAGNOSTIC_GN_GATE=FAIL gn desc exited with status $GN_QUERY_STATUS" >&2
  echo "CLANG_DIAGNOSTIC_GN_STDOUT_BEGIN" >&2
  cat "$GN_QUERY_STDOUT" >&2
  echo "CLANG_DIAGNOSTIC_GN_STDOUT_END" >&2
  echo "CLANG_DIAGNOSTIC_GN_STDERR_BEGIN" >&2
  cat "$GN_QUERY_STDERR" >&2
  echo "CLANG_DIAGNOSTIC_GN_STDERR_END" >&2
  rm -f "$GN_QUERY_STDOUT" "$GN_QUERY_STDERR"
  exit 1
fi
rm -f "$GN_QUERY_STDOUT" "$GN_QUERY_STDERR"
printf '%s' "$CFLAGS_JSON" | python3 -c '
import json
import sys

try:
    flags = json.load(sys.stdin)
except Exception as exc:
    raise SystemExit("CLANG_DIAGNOSTIC_GN_GATE=FAIL gn desc did not return valid JSON: %s" % exc)

if isinstance(flags, dict):
    flags = flags.get("cflags")
if not isinstance(flags, list) or not all(isinstance(flag, str) for flag in flags):
    raise SystemExit("CLANG_DIAGNOSTIC_GN_GATE=FAIL unexpected GN cflags JSON shape")

diagnostic_flags = [
    flag for flag in flags
    if flag.startswith("-fcrash-diagnostics-dir")
]
expected = ["-fcrash-diagnostics-dir=clang-crashreports"]
if diagnostic_flags != expected:
    raise SystemExit(
        "CLANG_DIAGNOSTIC_GN_GATE=FAIL expected %r, got %r"
        % (expected, diagnostic_flags)
    )

print("CLANG_DIAGNOSTIC_GN_GATE=PASS effective_cflags=%s" % diagnostic_flags[0])
'
