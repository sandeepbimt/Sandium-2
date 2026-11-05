#!/usr/bin/env bash
set -euo pipefail
ROOT="${CIRCLE_WORKING_DIRECTORY:?CIRCLE_WORKING_DIRECTORY is required}"
WORK="$ROOT/brave-work"
MANIFEST="$ROOT/brave-workspace-checkpoint.manifest.json"
SHARDS="$ROOT/brave-workspace-checkpoint.shards"
SRC="$WORK/src"
CORE="$SRC/brave"
OUT="$SRC/out/android_Release_arm64"
fail() { echo "SANDIUM_REFERENCE_GATE=FAIL $*" >&2; exit 1; }
[ -d "$SHARDS" ] || fail "restored parallel reference shard directory is missing"
[ -s "$MANIFEST" ] || fail "restored parallel reference manifest is missing"
python3 - "$MANIFEST" <<'PY'
import json
import sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if data.get("schema_version") != 2 or data.get("format") != "independent-tar+zstd-shards":
    raise SystemExit("SANDIUM_REFERENCE_GATE=FAIL unsupported shard manifest")
checkpoint = data.get("checkpoint_manifest", {})
required = {
    "CHECKPOINT_VALID": "true",
    "REFERENCE_MODE": "reference",
    "APK_VALIDATED": "true",
    "REFERENCE_READY": "true",
    "CHROMIUM_SHA": "d331de35ca8ab1358c7a17e4bd41627d55eaef51",
    "BRAVE_CORE_TAG": "v1.98.62",
    "TARGET": "android-arm64",
    "BUILD_TYPE": "Release",
}
for key, value in required.items():
    if checkpoint.get(key) != value:
        raise SystemExit("SANDIUM_REFERENCE_GATE=FAIL checkpoint manifest %s=%r expected=%r" %
                         (key, checkpoint.get(key), value))
if len(data.get("shards", [])) != int(data.get("workers", 0)) or not data.get("shards"):
    raise SystemExit("SANDIUM_REFERENCE_GATE=FAIL shard count does not match worker count")
print("SANDIUM_REFERENCE_MANIFEST=PASS workers=%d source_bytes=%s archive_bytes=%s" %
      (data["workers"], data.get("source_bytes"), data.get("archive_bytes")))
PY
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
echo "SANDIUM_REFERENCE_SHARDS=$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1]))["shards"]))' "$MANIFEST")"
echo "SANDIUM_REFERENCE_ARCHIVE_BYTES=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["archive_bytes"])' "$MANIFEST")"
