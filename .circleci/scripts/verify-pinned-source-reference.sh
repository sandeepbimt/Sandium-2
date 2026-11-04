#!/usr/bin/env bash
set -euo pipefail
ROOT="${CIRCLE_WORKING_DIRECTORY:?CIRCLE_WORKING_DIRECTORY is required}"
WORK="$ROOT/brave-work"
SRC="$WORK/src"
CORE="$SRC/brave"
MANIFEST="$ROOT/brave-source-checkpoint.manifest.json"
SHARDS="$ROOT/brave-source-checkpoint.shards"

[ -d "$SHARDS" ] && [ -s "$MANIFEST" ] || {
  echo "PIN_REFERENCE_OUTDATED=FAIL no independent source-ready archive restored; request source preparation." >&2
  exit 1
}
python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" verify --root "$ROOT" --workers 8 --ready --zstd-test
python3 - "$ROOT" "$WORK" "$MANIFEST" <<'PY'
import hashlib
import json
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
work = Path(sys.argv[2])
manifest = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
source = manifest.get("source", {})
if manifest.get("ready") is not True:
    raise SystemExit("PIN_REFERENCE_OUTDATED=FAIL restored archive is progress-only")
request_id = (root / ".circleci/source-pin-refresh-id").read_text(encoding="utf-8").strip()
if source.get("refresh_request_id") != request_id:
    raise SystemExit("PIN_REFERENCE_OUTDATED=FAIL a newer source refresh was requested but has not been promoted")

pins = {}
for line in (work / ".sandium/source-pins.env").read_text(encoding="utf-8").splitlines():
    if "=" in line:
        key, value = line.split("=", 1)
        pins[key] = value

src = work / "src"
core = src / "brave"
chromium_sha = subprocess.check_output(["git", "-C", str(src), "rev-parse", "HEAD"], text=True).strip()
brave_tag = subprocess.check_output(["git", "-C", str(core), "describe", "--tags", "--exact-match"], text=True).strip()

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

dependency_files = [core / "package.json", core / "pnpm-lock.yaml"]
if (core / ".npmrc").is_file():
    dependency_files.append(core / ".npmrc")
dependency_fingerprint = hashlib.sha256(
    "".join(sha256(path) for path in dependency_files).encode("ascii")
).hexdigest()

checks = {
    "Brave tag": (brave_tag, source.get("brave_core_tag")),
    "Chromium SHA": (chromium_sha, source.get("chromium_sha")),
    "source-pins Brave tag": (pins.get("BRAVE_CORE_TAG"), source.get("brave_core_tag")),
    "source-pins Chromium tag": (pins.get("CHROMIUM_TAG"), source.get("chromium_tag")),
    "source-pins Chromium SHA": (pins.get("CHROMIUM_SHA"), source.get("chromium_sha")),
    ".gclient_entries": (sha256(work / ".gclient_entries"), source.get("gclient_entries_sha256")),
    "Brave package dependency fingerprint": (dependency_fingerprint, source.get("brave_dependency_fingerprint")),
}
mismatches = [(name, actual, expected) for name, (actual, expected) in checks.items()
              if not actual or actual != expected]
if mismatches:
    for name, actual, expected in mismatches:
        print("PIN_REFERENCE_MISMATCH item=%s actual=%s expected=%s" % (name, actual, expected), file=sys.stderr)
    raise SystemExit(
        "PIN_REFERENCE_OUTDATED=FAIL compiled workspace and pinned-source reference differ. "
        "Do not overlay the source archive on compiled state. Refresh the pinning reference "
        "or use a compiled checkpoint built from matching source pins."
    )

print("PINNED_SOURCE_REFERENCE=RESTORED_AND_VERIFIED")
print("PINNED_SOURCE_PINS=PASS Brave=%s Chromium=%s sha=%s" %
      (brave_tag, source.get("chromium_tag"), chromium_sha))
print("PINNED_SOURCE_DEPENDENCIES=PASS fingerprint=%s" % dependency_fingerprint)
print("PINNED_SOURCE_COMPILED_STATE=PROTECTED; verified independently and not overlaid")
PY
