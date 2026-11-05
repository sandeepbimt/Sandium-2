#!/usr/bin/env bash
# Preserve the restored cumulative checkpoint as an immutable workspace base.
set -euo pipefail
ROOT="${CIRCLE_WORKING_DIRECTORY:?CIRCLE_WORKING_DIRECTORY is required}"
SHARDS="$ROOT/brave-source-checkpoint.shards"
MANIFEST="$ROOT/brave-source-checkpoint.manifest.json"
BASE_SHARDS="$ROOT/brave-source-checkpoint.base.shards"
BASE_MANIFEST="$ROOT/brave-source-checkpoint.base.manifest.json"
fail() { echo "SANDIUM_SOURCE_DELTA_BASE=FAIL $*" >&2; exit 1; }
test -d "$SHARDS" || fail "restored source shard directory missing"
test -s "$MANIFEST" || fail "restored source manifest missing"
if [ -e "$BASE_SHARDS" ] || [ -e "$BASE_MANIFEST" ]; then
  fail "base checkpoint path already exists; refusing to overwrite an existing lineage base"
fi
cp -al "$SHARDS" "$BASE_SHARDS"
cp -p "$MANIFEST" "$BASE_MANIFEST"
python3 - "$BASE_MANIFEST" "$BASE_SHARDS" <<'PY'
import hashlib, json, sys
from pathlib import Path
manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
shards = Path(sys.argv[2])
items = manifest.get("shards", [])
if not items:
    raise SystemExit("SANDIUM_SOURCE_DELTA_BASE=FAIL base manifest has no shards")
for item in items:
    path = shards / item["name"]
    if not path.is_file() or path.stat().st_size != int(item["size_bytes"]):
        raise SystemExit("SANDIUM_SOURCE_DELTA_BASE=FAIL missing or size-mismatched shard " + item["name"])
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    if h.hexdigest() != item["sha256"]:
        raise SystemExit("SANDIUM_SOURCE_DELTA_BASE=FAIL checksum mismatch " + item["name"])
print("SANDIUM_SOURCE_DELTA_BASE=PASS shards=%d manifest_sha256=%s" %
      (len(items), hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest()))
PY
