#!/usr/bin/env bash
set -euo pipefail

PHASE="${1:?usage: capture-brave-siso-checkpoint.sh <restore|before-build|after-build|checkpoint-ready>}"
case "$PHASE" in
  restore|before-build|after-build|checkpoint-ready) ;;
  *) echo "BRAVE_SISO_DIAGNOSTICS=FAIL invalid phase=$PHASE" >&2; exit 2 ;;
esac

ROOT="$(printenv CIRCLE_WORKING_DIRECTORY)"
STAGE="$(printenv BRAVE_STAGE_INDEX)"
BUILD_NUM="$(printenv CIRCLE_BUILD_NUM || echo local)"
WORKFLOW_ID="$(printenv CIRCLE_WORKFLOW_ID || echo local)"
SAFE_RUN_ID="$(printf '%s' "$BUILD_NUM-$WORKFLOW_ID" | tr -c 'A-Za-z0-9._-' '_')"
OUT="$ROOT/brave-work/src/out/android_Release_arm64"
DIAG_ROOT="$ROOT/brave-work/.sandium/checkpoint-diagnostics"
STAGE_DIR="$DIAG_ROOT/stage-$STAGE"
mkdir -p "$STAGE_DIR"
REPORT="$STAGE_DIR/$SAFE_RUN_ID-$PHASE.txt"
TMP="$REPORT.tmp"

record_file() {
  label="$1"
  path="$2"
  hash_mode="${3:-yes}"
  if [ -f "$path" ]; then
    printf '%s_EXISTS=true\n' "$label"
    printf '%s_SIZE_BYTES=%s\n' "$label" "$(stat -c '%s' "$path")"
    printf '%s_MTIME_EPOCH=%s\n' "$label" "$(stat -c '%Y' "$path")"
    if [ "$hash_mode" = "yes" ]; then
      digest="$(sha256sum "$path" 2>/dev/null | awk '{print $1}' || true)"
      printf '%s_SHA256=%s\n' "$label" "${digest:-unavailable}"
    fi
  else
    printf '%s_EXISTS=false\n' "$label"
  fi
}

{
  echo "BRAVE_SISO_DIAGNOSTICS=START"
  echo "PHASE=$PHASE"
  echo "STAGE=$STAGE"
  echo "CIRCLE_BUILD_NUM=$BUILD_NUM"
  echo "CIRCLE_WORKFLOW_ID=$WORKFLOW_ID"
  echo "CAPTURED_AT_UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "OUT_EXISTS=$([ -d "$OUT" ] && echo true || echo false)"
  if [ -d "$OUT" ]; then
    record_file BUILD_NINJA "$OUT/build.ninja"
    record_file ARGS_GN "$OUT/args.gn"
    record_file ARGS_GENERATED "$OUT/args_generated.gni"
    record_file SISO_STATE "$OUT/.siso_fs_state"
    record_file SISO_JOURNAL "$OUT/.siso_fs_state.journal"
    record_file NINJA_LOG "$OUT/.ninja_log"
    record_file NINJA_DEPS "$OUT/.ninja_deps"
    record_file SISO_INFO "$OUT/siso.INFO" no
    record_file SISO_OUTPUT "$OUT/siso_output" no
    if [ -s "$OUT/build.ninja" ]; then
      echo "BUILD_NINJA_EDGE_COUNT=$(grep -c '^build ' "$OUT/build.ninja" || true)"
    else
      echo "BUILD_NINJA_EDGE_COUNT=0"
    fi
    if [ -d "$OUT/obj" ]; then
      echo "OBJ_DIRECTORY_BYTES=$(du -sb "$OUT/obj" | awk '{print $1}')"
    else
      echo "OBJ_DIRECTORY_BYTES=0"
    fi
    if [ -d "$OUT/gen" ]; then
      echo "GEN_DIRECTORY_BYTES=$(du -sb "$OUT/gen" | awk '{print $1}')"
    else
      echo "GEN_DIRECTORY_BYTES=0"
    fi
    python3 - "$OUT" <<'PY'
import os
import sys

out = sys.argv[1]
def measure(root, suffixes=None):
    count = 0
    total = 0
    suffix_counts = {suffix: 0 for suffix in (suffixes or [])}
    suffix_bytes = {suffix: 0 for suffix in (suffixes or [])}
    if not os.path.isdir(root):
        return count, total, suffix_counts, suffix_bytes
    for base, _, files in os.walk(root):
        for name in files:
            path = os.path.join(base, name)
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            count += 1
            total += size
            for suffix in suffix_counts:
                if name.endswith(suffix):
                    suffix_counts[suffix] += 1
                    suffix_bytes[suffix] += size
    return count, total, suffix_counts, suffix_bytes

obj_count, obj_bytes, obj_counts, obj_sizes = measure(
    os.path.join(out, "obj"), [".o", ".dwo", ".d", ".pcm"]
)
gen_count, gen_bytes, _, _ = measure(os.path.join(out, "gen"))
apk_count, apk_bytes, _, _ = measure(os.path.join(out, "apks"))
print("OBJ_FILE_COUNT=%d" % obj_count)
print("OBJ_TOTAL_BYTES=%d" % obj_bytes)
for suffix, key in [(".o", "OBJ_O"), (".dwo", "OBJ_DWO"), (".d", "OBJ_DEP"), (".pcm", "OBJ_PCM")]:
    print("%s_COUNT=%d" % (key, obj_counts[suffix]))
    print("%s_BYTES=%d" % (key, obj_sizes[suffix]))
print("GEN_FILE_COUNT=%d" % gen_count)
print("GEN_TOTAL_BYTES=%d" % gen_bytes)
print("APK_FILE_COUNT=%d" % apk_count)
print("APK_TOTAL_BYTES=%d" % apk_bytes)
PY
    echo "=== SISO PROGRESS / ACTION SUMMARY ==="
    if [ -f "$OUT/siso_output" ]; then
      grep -aE 'Regenerating ninja files|loading build\.ninja|load siso config|schedule pending:|build start:|noexec:|Build (Failure|Finished)|Build Success' "$OUT/siso_output" | tail -n 80 || true
    elif [ -d "$OUT/siso_output" ]; then
      echo "SISO_OUTPUT_IS_DIRECTORY=true"
      find "$OUT/siso_output" -maxdepth 2 -type f -printf '%s %p\n' | sort -nr | head -n 20 || true
    fi
    echo "=== SISO INFO STATE / JOURNAL EVENTS ==="
    if [ -f "$OUT/siso.INFO" ]; then
      grep -aEi 'journal|state|reconcile|manifest|startup|load|restore|scan' "$OUT/siso.INFO" | tail -n 80 || true
    fi
    SRC="$ROOT/brave-work/src"
    if [ -s "$SRC/DEPS" ]; then
      grep -n "'siso_version'" "$SRC/DEPS" || true
    fi
  fi
  echo "BRAVE_SISO_DIAGNOSTICS=END"
} > "$TMP"

mv "$TMP" "$REPORT"
echo "BRAVE_SISO_DIAGNOSTICS_REPORT=$REPORT"
grep -E '^(PHASE|STAGE|BUILD_NINJA_EDGE_COUNT|SISO_STATE_(EXISTS|SIZE_BYTES|SHA256)|SISO_JOURNAL_(EXISTS|SIZE_BYTES|SHA256)|NINJA_(LOG|DEPS)_(EXISTS|SIZE_BYTES|SHA256)|OBJ_O_COUNT|OBJ_DWO_COUNT|OBJ_PCM_COUNT|GEN_FILE_COUNT|GEN_TOTAL_BYTES|APK_FILE_COUNT)=' "$REPORT" || true

if [ "$PHASE" = "restore" ] && [ "$STAGE" -gt 1 ]; then
  PREV_STAGE="$((STAGE - 1))"
  PREV_DIR="$DIAG_ROOT/stage-$PREV_STAGE"
  COMPARISON="$STAGE_DIR/$SAFE_RUN_ID-handoff-comparison.txt"
  python3 - "$PREV_DIR" "$REPORT" "$COMPARISON" "$PREV_STAGE" "$STAGE" <<'PY'
import glob
import os
import sys

prev_dir, current_path, comparison_path, prev_stage, stage = sys.argv[1:]
candidates = glob.glob(os.path.join(prev_dir, "*-checkpoint-ready.txt"))
candidates = [p for p in candidates if os.path.isfile(p)]
candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
keys = [
    "BUILD_NINJA_SHA256", "ARGS_GN_SHA256", "SISO_STATE_SHA256",
    "SISO_JOURNAL_SHA256", "NINJA_LOG_SHA256", "NINJA_DEPS_SHA256",
    "OBJ_O_COUNT", "OBJ_DWO_COUNT", "OBJ_PCM_COUNT", "OBJ_TOTAL_BYTES",
    "GEN_FILE_COUNT", "GEN_TOTAL_BYTES"
]
def read_values(path):
    result = {}
    with open(path, encoding="utf-8", errors="replace") as source:
        for line in source:
            if "=" in line:
                key, value = line.rstrip("\n").split("=", 1)
                result[key] = value
    return result

with open(comparison_path, "w", encoding="utf-8") as report:
    report.write("PREVIOUS_STAGE=%s\nCURRENT_STAGE=%s\n" % (prev_stage, stage))
    if not candidates:
        report.write("HANDOFF_COMPARISON=NO_PREVIOUS_CHECKPOINT_READY_REPORT\n")
    else:
        previous_path = candidates[0]
        previous = read_values(previous_path)
        current = read_values(current_path)
        report.write("PREVIOUS_REPORT=%s\n" % previous_path)
        for key in keys:
            left = previous.get(key, "<missing>")
            right = current.get(key, "<missing>")
            if left == "<missing>" or right == "<missing>":
                status = "NOT_COMPARABLE"
            elif left == right:
                status = "MATCH"
            else:
                status = "DIFFERENT"
            report.write("%s=%s previous=%s current=%s\n" % (key, status, left, right))
        report.write("HANDOFF_COMPARISON=COMPLETE\n")
print(open(comparison_path, encoding="utf-8").read(), end="")
PY
fi

if [ "$PHASE" = "after-build" ]; then
  BEFORE_REPORT="$STAGE_DIR/$SAFE_RUN_ID-before-build.txt"
  if [ -f "$BEFORE_REPORT" ]; then
    BEFORE_BYTES="$(sed -n 's/^SISO_OUTPUT_SIZE_BYTES=//p' "$BEFORE_REPORT" | head -n 1)"
    NOW_BYTES="$(sed -n 's/^SISO_OUTPUT_SIZE_BYTES=//p' "$REPORT" | head -n 1)"
    if [ -n "$BEFORE_BYTES" ] && [ -n "$NOW_BYTES" ]; then
      if [ "$NOW_BYTES" -ge "$BEFORE_BYTES" ]; then
        echo "SISO_OUTPUT_DELTA_BYTES=$((NOW_BYTES - BEFORE_BYTES))" | tee -a "$REPORT"
      else
        echo "SISO_OUTPUT_RESET_OR_ROTATED=true" | tee -a "$REPORT"
      fi
    fi
  fi
fi
