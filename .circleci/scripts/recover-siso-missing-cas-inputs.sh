#!/usr/bin/env bash
set -euo pipefail

OUT="${1:?usage: recover-siso-missing-cas-inputs.sh <out-dir> <metrics-jsonl>}"
METRICS_FILE="${2:?usage: recover-siso-missing-cas-inputs.sh <out-dir> <metrics-jsonl>}"
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
python3 - "$LOG" "$OUT" > "$TARGETS_FILE" <<'PY'
import re
import sys
from pathlib import Path

log_path, out_dir = sys.argv[1:]
outputs = []
text = Path(log_path).read_text(encoding="utf-8", errors="replace")
# Terminal formatting is not part of the Siso failure record.
text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
records = re.split(r"(?m)^FAILED: ", text)[1:]
signature = r'rpc error: code = FailedPrecondition desc = download inputs: could not (fetch inputs|get input tree): Digest hash:.*not found'
for record in records:
    header = record.splitlines()[0]
    match = re.search(r'"(\./[^"\s]+)"', header)
    if not match:
        raise SystemExit("BRAVE_CAS_LOCAL_RECOVERY=FAIL could not parse a FAILED output: " + header)
    target = match.group(1)[2:]
    parts = target.split("/")
    if (not re.fullmatch(r"obj/[A-Za-z0-9_.+/-]+", target)
            or any(part in ("", ".", "..") for part in parts)
            or not (Path(out_dir) / target).resolve().is_relative_to(Path(out_dir))):
        raise SystemExit("BRAVE_CAS_LOCAL_RECOVERY=FAIL unsafe failed target: " + target)
    # Each failed action must itself report missing remote input. A compiler error
    # alongside an unrelated CAS failure must not receive infrastructure recovery.
    if not re.search(r"(?m)^err: [^\n]*" + signature, record):
        raise SystemExit("BRAVE_CAS_LOCAL_RECOVERY=FAIL failed action is not missing-CAS: " + target)
    object_output = target.endswith(".o")
    java_output = (target.endswith(".javac.jar")
                   and re.search(r' ACTION //[^\s]+:([^\s:]+)__compile_java\(', header)
                   and re.search(r'(?m)^siso_rule: android/compile_java\s*$', record))
    if not (object_output or java_output):
        raise SystemExit("BRAVE_CAS_LOCAL_RECOVERY=FAIL refusing unsupported failed target: " + target)
    outputs.append(target)

unique = list(dict.fromkeys(outputs))
if not unique:
    raise SystemExit("BRAVE_CAS_LOCAL_RECOVERY=FAIL no supported failed outputs found")
if len(unique) > 50:
    raise SystemExit("BRAVE_CAS_LOCAL_RECOVERY=FAIL refusing recovery of more than 50 outputs: %d" % len(unique))
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
# failed object or verified Java compile outputs locally, then the caller resumes the strict-remote
# full target build. This avoids changing the normal remote execution policy.
export SISO_LIMITS="local=8"
timeout --signal=INT --kill-after=30s 600s \
  autoninja --offline -metrics_json "$METRICS_FILE" -C "$OUT" -j8 "${TARGETS[@]}" \
  2>&1 | tee "$DIAGNOSTICS/missing-cas-local-recovery-$STAMP.log"

for target in "${TARGETS[@]}"; do
  if [ ! -s "$OUT/$target" ]; then
    echo "BRAVE_CAS_LOCAL_RECOVERY=FAIL missing output after local rebuild: $OUT/$target" >&2
    exit 1
  fi
done

echo "BRAVE_CAS_LOCAL_RECOVERY=PASS rebuilt=${#TARGETS[@]} mode=offline-local"
