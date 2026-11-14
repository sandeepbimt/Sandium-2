#!/usr/bin/env bash
set -euo pipefail
ROOT="${CIRCLE_WORKING_DIRECTORY:?}"
WORK="$ROOT/brave-work"
SRC="$WORK/src"
CORE="$SRC/brave"
OUT="$SRC/out/android_Release_arm64"
fail() { echo "SANDIUM_FLOW_STATE_GATE=FAIL $*" >&2; exit 1; }
python3 "$ROOT/.circleci/bridge/full_driver.py" verify-restored
[ -s "$SRC/.git/HEAD" ] || fail "Chromium Git metadata missing"
[ -s "$CORE/.git/HEAD" ] || fail "Brave Git metadata missing"
[ "$(git -C "$SRC" rev-parse HEAD)" = "d331de35ca8ab1358c7a17e4bd41627d55eaef51" ] || fail "Chromium checkout does not match reference"
[ "$(git -C "$CORE" describe --tags --exact-match 2>/dev/null || true)" = "v1.98.62" ] || fail "Brave checkout does not match reference"
EXPECTED_BRAVE_CORE_SHA="44a84b1f89d9a35287289d6a3d493e362f5a5123"
ACTUAL_BRAVE_CORE_SHA="$(git -C "$CORE" rev-parse HEAD)"
[ "$ACTUAL_BRAVE_CORE_SHA" = "$EXPECTED_BRAVE_CORE_SHA" ] || fail "Brave Core SHA does not match the v1.98.62 reference: expected=$EXPECTED_BRAVE_CORE_SHA actual=$ACTUAL_BRAVE_CORE_SHA"
[ -s "$OUT/build.ninja" ] || fail "Ninja build graph missing"
[ -s "$OUT/args.gn" ] || fail "GN args missing"
[ -s "$OUT/args_generated.gni" ] || fail "generated GN args missing"
[ -s "$SRC/build/config/siso/.sisorc" ] || fail "Siso config missing"
[ -s "$SRC/build/config/siso/.sisoenv" ] || fail "Siso environment missing"
[ -s "$SRC/build/config/siso/backend_config/backend.star" ] || fail "Siso backend missing"
if [ ! -s "$OUT/.siso_fs_state" ] && [ ! -s "$OUT/.siso_fs_state.journal" ]; then
  fail "neither Siso filesystem state nor its journal is present"
fi
echo "SANDIUM_REFERENCE_GATE=PASS"
echo "SANDIUM_REFERENCE_CHROMIUM=$(git -C "$SRC" rev-parse HEAD)"
echo "SANDIUM_REFERENCE_BRAVE=$(git -C "$CORE" describe --tags --exact-match)"
echo "SANDIUM_REFERENCE_BRAVE_SHA=$ACTUAL_BRAVE_CORE_SHA"
