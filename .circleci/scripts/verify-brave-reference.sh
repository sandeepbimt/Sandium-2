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
STAGE="${BRAVE_STAGE_INDEX:-1}"
case "$STAGE" in
  1|2|3|4|5) ;;
  *) fail "invalid BRAVE_STAGE_INDEX=$STAGE" ;;
esac
python3 - "$MANIFEST" "$SHARDS" "$STAGE" <<'PY'
import json
import sys
from pathlib import Path

manifest_path, shard_dir, stage = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
data = json.loads(manifest_path.read_text(encoding="utf-8"))
if data.get("schema_version") != 2 or data.get("format") != "independent-tar+zstd-shards":
    raise SystemExit("SANDIUM_REFERENCE_GATE=FAIL unsupported shard manifest")
checkpoint = data.get("checkpoint_manifest", {})
required = {
    "CHECKPOINT_VALID": "true",
    "REFERENCE_MODE": "reference",
    "CHROMIUM_SHA": "d331de35ca8ab1358c7a17e4bd41627d55eaef51",
    "BRAVE_CORE_TAG": "v1.98.62",
    "TARGET": "android-arm64",
    "BUILD_TYPE": "Release",
}
if stage == 1:
    required.update({"APK_VALIDATED": "true", "REFERENCE_READY": "true"})
else:
    # Continuation handoffs are valid before APK creation. APK_VALIDATED is a
    # completion marker, not a prerequisite for restoring useful build state.
    if checkpoint.get("APK_VALIDATED") not in ("true", "false"):
        raise SystemExit("SANDIUM_REFERENCE_GATE=FAIL continuation manifest has invalid APK_VALIDATED state")
    if checkpoint.get("APK_VALIDATED") == "true" and checkpoint.get("REFERENCE_READY") != "true":
        raise SystemExit("SANDIUM_REFERENCE_GATE=FAIL APK is marked validated but reference is not ready")
for key, value in required.items():
    if checkpoint.get(key) != value:
        raise SystemExit("SANDIUM_REFERENCE_GATE=FAIL checkpoint manifest %s=%r expected=%r" %
                         (key, checkpoint.get(key), value))

workers = data.get("workers")
shards = data.get("shards")
expected_names = [f"shard-{i:02d}-of-08.tar.zst" for i in range(1, 9)]
if workers != 8 or not isinstance(shards, list) or len(shards) != 8:
    raise SystemExit("SANDIUM_REFERENCE_GATE=FAIL expected exactly eight shard records")
if sorted(item.get("name") for item in shards if isinstance(item, dict)) != expected_names:
    raise SystemExit("SANDIUM_REFERENCE_GATE=FAIL shard names do not match expected eight-shard set")
total = 0
for item in shards:
    name = item["name"]
    path = shard_dir / name
    if not path.is_file():
        raise SystemExit("SANDIUM_REFERENCE_GATE=FAIL missing shard " + name)
    actual_size = path.stat().st_size
    if actual_size != item.get("size_bytes"):
        raise SystemExit("SANDIUM_REFERENCE_GATE=FAIL shard size mismatch " + name)
    # The immediately preceding archive restore invokes
    # sandium-checkpoint-shards.py restore, which verifies every shard's
    # recorded SHA256 before extraction. Avoid hashing the entire 26 GiB
    # reference a second time in this lightweight post-restore gate.
    total += actual_size
if total != data.get("archive_bytes"):
    raise SystemExit("SANDIUM_REFERENCE_GATE=FAIL aggregate archive size mismatch")
if stage == 1:
    print("SANDIUM_REFERENCE_MANIFEST=PASS stage=1 canonical_APK_validated=true workers=8 source_bytes=%s archive_bytes=%s" %
          (data.get("source_bytes"), data.get("archive_bytes")))
else:
    print("SANDIUM_HANDOFF_MANIFEST=PASS stage=%d APK_VALIDATED=%s workers=8 source_bytes=%s archive_bytes=%s" %
          (stage, checkpoint["APK_VALIDATED"], data.get("source_bytes"), data.get("archive_bytes")))
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
