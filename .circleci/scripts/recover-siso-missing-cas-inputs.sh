#!/usr/bin/env bash
set -euo pipefail

OUT="${1:?usage: recover-siso-missing-cas-inputs.sh <out-dir>}"
OUT="$(realpath "$OUT")"
ROOT="${CIRCLE_WORKING_DIRECTORY:?CIRCLE_WORKING_DIRECTORY must be set}"
LOG="$OUT/siso_output"
FAILED_COMMANDS="$OUT/siso_failed_commands.sh"
DIAGNOSTICS="$ROOT/brave-apk/siso-diagnostics"

if [ ! -s "$LOG" ]; then
  echo "BRAVE_CAS_LOCAL_RECOVERY=FAIL missing Siso log: $LOG" >&2
  exit 1
fi
if [ ! -s "$FAILED_COMMANDS" ]; then
  echo "BRAVE_CAS_LOCAL_RECOVERY=FAIL missing Siso failed-command script: $FAILED_COMMANDS" >&2
  exit 1
fi
if ! grep -Eq 'rpc error: code = FailedPrecondition desc = download inputs: could not (fetch inputs|get input tree): Digest hash:.*not found' "$LOG"; then
  echo "BRAVE_CAS_LOCAL_RECOVERY=FAIL log does not contain the expected missing-CAS-input signature" >&2
  exit 1
fi

mkdir -p "$DIAGNOSTICS"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
cp -a "$LOG" "$DIAGNOSTICS/siso_output.missing-cas-$STAMP.log"
cp -a "$FAILED_COMMANDS" "$DIAGNOSTICS/siso_failed_commands.missing-cas-$STAMP.sh"

TARGETS_FILE="$(mktemp)"
trap 'rm -f "$TARGETS_FILE"' EXIT
python3 - "$LOG" > "$TARGETS_FILE" <<'PY'
import re
import sys
from pathlib import PurePosixPath

log_path = sys.argv[1]
outputs = []
with open(log_path, encoding="utf-8", errors="replace") as stream:
    for line in stream:
        if not line.startswith("FAILED: "):
            continue
        match = re.search(r'"(\./[^"\s]+)"', line)
        if not match:
            raise SystemExit("BRAVE_CAS_LOCAL_RECOVERY=FAIL could not parse a FAILED output: " + line.rstrip())
        target = match.group(1)[2:]
        parts = PurePosixPath(target).parts
        if (not target.startswith("obj/") or not target.endswith(".o")
                or target.startswith("/") or ".." in parts):
            raise SystemExit("BRAVE_CAS_LOCAL_RECOVERY=FAIL refusing non-object or unsafe failed target: " + target)
        outputs.append(target)

unique = list(dict.fromkeys(outputs))
if not unique:
    raise SystemExit("BRAVE_CAS_LOCAL_RECOVERY=FAIL no failed object outputs found")
if len(unique) > 50:
    raise SystemExit("BRAVE_CAS_LOCAL_RECOVERY=FAIL refusing recovery of more than 50 object outputs: %d" % len(unique))
for target in unique:
    print(target)
PY

mapfile -t TARGETS < "$TARGETS_FILE"
if [ "${#TARGETS[@]}" -eq 0 ]; then
  echo "BRAVE_CAS_LOCAL_RECOVERY=FAIL no safe targets were extracted" >&2
  exit 1
fi

printf 'BRAVE_CAS_LOCAL_RECOVERY=START mode=offline-local targets=%s\n' "${#TARGETS[@]}"
printf 'BRAVE_CAS_LOCAL_RECOVERY_TARGET=%s\n' "${TARGETS[@]}"
command -v autoninja >/dev/null 2>&1 || {
  echo "BRAVE_CAS_LOCAL_RECOVERY=FAIL autoninja is not on PATH" >&2
  exit 1
}

# Siso treats REAPI FailedPrecondition as non-fallback. Rebuild only those
# failed object outputs locally, then the caller resumes the strict-remote
# full target build. This avoids changing the normal remote execution policy.
export SISO_LIMITS="local=8"
timeout --signal=INT --kill-after=30s 600s \
  autoninja --offline -C "$OUT" -j8 "${TARGETS[@]}" \
  2>&1 | tee "$DIAGNOSTICS/missing-cas-local-recovery-$STAMP.log"

for target in "${TARGETS[@]}"; do
  if [ ! -s "$OUT/$target" ]; then
    echo "BRAVE_CAS_LOCAL_RECOVERY=FAIL missing output after local rebuild: $OUT/$target" >&2
    exit 1
  fi
done

echo "BRAVE_CAS_LOCAL_RECOVERY=PASS rebuilt=${#TARGETS[@]} mode=offline-local"
