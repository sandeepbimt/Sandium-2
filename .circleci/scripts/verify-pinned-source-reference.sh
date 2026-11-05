#!/usr/bin/env bash
set -euo pipefail
ROOT="${CIRCLE_WORKING_DIRECTORY:?CIRCLE_WORKING_DIRECTORY is required}"
WORK="$ROOT/brave-work"
SRC="$WORK/src"
CORE="$SRC/brave"
MANIFEST="$ROOT/brave-source-checkpoint.manifest.json"
SHARDS="$ROOT/brave-source-checkpoint.shards"

STAGE="${1:-${BRAVE_STAGE_INDEX:-}}"
EXPECTED_BRAVE_TAG="${EXPECTED_BRAVE_CORE_TAG:-}"
EXPECTED_BRAVE_SHA="${EXPECTED_BRAVE_CORE_SHA:-}"
EXPECTED_CHROMIUM_TAG="${EXPECTED_CHROMIUM_TAG:-}"
EXPECTED_CHROMIUM_SHA="${EXPECTED_CHROMIUM_SHA:-}"
REQUEST_FILE="$ROOT/.circleci/source-pin-refresh-id"

# The independent source-only archive is an optimization, not a prerequisite
# for the first Full Mode run. A restored compiled checkpoint may contain the
# complete source tree even when no separately promoted source-ready archive
# exists yet. Never overlay one archive on the compiled workspace.
if [ ! -d "$SHARDS" ] && [ ! -s "$MANIFEST" ]; then
  if [ -z "$STAGE" ] || [ -z "$EXPECTED_BRAVE_TAG" ] || [ -z "$EXPECTED_BRAVE_SHA" ] || [ -z "$EXPECTED_CHROMIUM_TAG" ] || [ -z "$EXPECTED_CHROMIUM_SHA" ]; then
    echo "PIN_REFERENCE_OUTDATED=FAIL independent source archive missing and expected pin contract was not supplied" >&2
    exit 1
  fi
  if [ "$STAGE" = "1" ]; then
    echo "PINNED_SOURCE_REFERENCE=BOOTSTRAP_REQUIRED stage=1; no independent source-ready archive exists for this new pin request."
    echo "PINNED_SOURCE_REFERENCE=COMPILED_WORKSPACE_PROTECTED; canonical reference validation and pinned source preparation follow."
    exit 0
  fi
  python3 - "$WORK" "$REQUEST_FILE" "$EXPECTED_BRAVE_TAG" "$EXPECTED_BRAVE_SHA" "$EXPECTED_CHROMIUM_TAG" "$EXPECTED_CHROMIUM_SHA" <<'PY'
import hashlib
import json
import subprocess
import sys
from pathlib import Path

work, request_file = Path(sys.argv[1]), Path(sys.argv[2])
expected_brave, expected_brave_sha, expected_chromium, expected_chromium_sha = sys.argv[3:]
pins_path = work / ".sandium/source-pins.env"
if not pins_path.is_file():
    raise SystemExit("PIN_REFERENCE_OUTDATED=FAIL Stage 2+ has no source-pins.env in restored compiled handoff")
pins = dict(line.split("=", 1) for line in pins_path.read_text(encoding="utf-8").splitlines() if "=" in line)
request = request_file.read_text(encoding="utf-8").strip()
src, core = work / "src", work / "src/brave"
required = [work / ".gclient", work / ".gclient_entries", src / ".git", core / ".git",
            core / "package.json", core / "node_modules/.modules.yaml", core / "node_modules/.pnpm"]
missing = [str(p) for p in required if not p.exists()]
if missing:
    raise SystemExit("PIN_REFERENCE_OUTDATED=FAIL Stage 2+ compiled handoff missing: " + ", ".join(missing))
actual_brave = subprocess.check_output(["git", "-C", str(core), "describe", "--tags", "--exact-match"], text=True).strip()
actual_brave_sha = subprocess.check_output(["git", "-C", str(core), "rev-parse", "HEAD"], text=True).strip()
actual_chromium_sha = subprocess.check_output(["git", "-C", str(src), "rev-parse", "HEAD"], text=True).strip()
package = json.loads((core / "package.json").read_text(encoding="utf-8"))
package_chromium = package["config"]["projects"]["chrome"]["tag"]
checks = {
    "refresh request": (pins.get("REFRESH_REQUEST_ID"), request),
    "Brave tag": (actual_brave, expected_brave),
    "Brave SHA": (actual_brave_sha, expected_brave_sha),
    "Chromium package tag": (package_chromium, expected_chromium),
    "Chromium pin tag": (pins.get("CHROMIUM_TAG"), expected_chromium),
    "Chromium pin SHA": (pins.get("CHROMIUM_SHA"), expected_chromium_sha),
    "Chromium checkout SHA": (actual_chromium_sha, expected_chromium_sha),
}
bad = [(k, a, e) for k, (a, e) in checks.items() if not a or a != e]
if bad:
    for key, actual, expected in bad:
        print("PIN_REFERENCE_MISMATCH item=%s actual=%s expected=%s" % (key, actual, expected), file=sys.stderr)
    raise SystemExit("PIN_REFERENCE_OUTDATED=FAIL restored Stage 2+ workspace is not the requested pinned source")
print("PINNED_SOURCE_REFERENCE=RESTORED_AND_VERIFIED_FROM_COMPILED_HANDOFF")
print("PINNED_SOURCE_PINS=PASS Brave=%s Chromium=%s sha=%s" % (actual_brave, expected_chromium, actual_chromium_sha))
PY
  exit 0
fi

# A half-restored archive is corruption, not a cache miss; fail closed.
[ -d "$SHARDS" ] && [ -s "$MANIFEST" ] || {
  echo "PIN_REFERENCE_OUTDATED=FAIL partial independent source-ready archive restored" >&2
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
