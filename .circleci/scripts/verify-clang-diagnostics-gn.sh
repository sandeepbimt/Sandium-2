#!/usr/bin/env bash
set -euo pipefail

ROOT="$CIRCLE_WORKING_DIRECTORY"
if [ -z "$ROOT" ]; then
  echo "CLANG_DIAGNOSTIC_GN_GATE=FAIL CIRCLE_WORKING_DIRECTORY is required" >&2
  exit 1
fi
SRC="$ROOT/brave-work/src"
OUT="$SRC/out/android_Release_arm64"
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
ARGS_GENERATED="$OUT/args_generated.gni"
test -s "$ARGS_GENERATED" || {
  echo "BRAVE_RELEASE_GN_GATE=FAIL args_generated.gni missing" >&2
  exit 1
}
require_release_arg() {
  if ! grep -Fqx "$1" "$ARGS_GENERATED"; then
    echo "BRAVE_RELEASE_GN_GATE=FAIL missing generated GN arg: $1" >&2
    exit 1
  fi
}
require_release_arg 'is_debug=false'
require_release_arg 'is_official_build=false'
require_release_arg 'is_component_build=false'
require_release_arg 'is_java_debug=false'
require_release_arg 'symbol_level=1'
require_release_arg 'enable_android_secondary_abi=false'
require_release_arg 'enable_updater=false'
require_release_arg 'enable_update_notifications=false'
require_release_arg 'android_channel="default"'
require_release_arg 'chrome_public_manifest_package="com.brave.browser_default"'
require_release_arg 'brave_channel="development"'
require_release_arg 'target_android_output_format="apk"'
echo "BRAVE_RELEASE_GN_GATE=PASS"

test -s "$SRC/.gn" || {
  echo "CLANG_DIAGNOSTIC_GN_GATE=FAIL Chromium source-root marker missing: $SRC/.gn" >&2
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

# GN resolves the Chromium root from the current directory (or --root). Each
# CircleCI run step starts at the repository root, so explicitly enter SRC.
# This is essential when the helper is called by the checkpoint-validation
# step, which runs in a fresh shell after source preparation has completed.
cd "$SRC"
echo "CLANG_DIAGNOSTIC_GN_ROOT=$(pwd)"

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
    payload = json.load(sys.stdin)
except Exception as exc:
    raise SystemExit("CLANG_DIAGNOSTIC_GN_GATE=FAIL gn desc did not return valid JSON: %s" % exc)

# GN --format=json always wraps the selected target/config in a dictionary
# keyed by its fully qualified label, even when only one label was requested.
if isinstance(payload, dict) and isinstance(payload.get("cflags"), list):
    # Retain compatibility with direct-property JSON from older GN versions.
    flags = payload["cflags"]
elif isinstance(payload, dict) and len(payload) == 1:
    label, description = next(iter(payload.items()))
    if not isinstance(description, dict) or "cflags" not in description:
        raise SystemExit(
            "CLANG_DIAGNOSTIC_GN_GATE=FAIL GN JSON entry for %s has no cflags property; keys=%r"
            % (label, sorted(description.keys()) if isinstance(description, dict) else type(description).__name__)
        )
    flags = description["cflags"]
else:
    raise SystemExit(
        "CLANG_DIAGNOSTIC_GN_GATE=FAIL unexpected GN cflags JSON root: %s"
        % (list(payload.keys()) if isinstance(payload, dict) else type(payload).__name__)
    )

if not isinstance(flags, list) or not all(isinstance(flag, str) for flag in flags):
    raise SystemExit("CLANG_DIAGNOSTIC_GN_GATE=FAIL GN cflags property is not a string list")

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
