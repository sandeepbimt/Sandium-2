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

# Do not grep build.ninja: GN stores compiler flags on the config/target,
# not necessarily as literal text in the top-level Ninja manifest.
# Query the effective GN compiler config after build.ts has regenerated the graph.
CFLAGS_JSON="$("$GN" desc "$OUT" //build/config/compiler:compiler cflags --format=json)"
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
