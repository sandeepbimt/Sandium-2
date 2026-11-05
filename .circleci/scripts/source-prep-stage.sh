#!/usr/bin/env bash
set -euo pipefail
STAGE="${1:?usage: source-prep-stage.sh <1..5>}"
case "$STAGE" in 1|2|3|4|5) ;; *) echo "SOURCE_PREP_STAGE=FAIL invalid stage=$STAGE" >&2; exit 2 ;; esac
ROOT="${CIRCLE_WORKING_DIRECTORY:?CIRCLE_WORKING_DIRECTORY is required}"
WORK="$ROOT/brave-work"; SRC="$WORK/src"; CORE="$SRC/brave"; STATE="$WORK/.sandium"
PINS="$STATE/source-pins.env"
REQUEST_FILE="$ROOT/.circleci/source-pin-refresh-id"
CURRENT_REQUEST_ID="$(tr -d '\r\n' < "$REQUEST_FILE")"
SLICE_SECONDS="${SANDIUM_PIN_SLICE_SECONDS:-3000}"
case "$SLICE_SECONDS" in ''|*[!0-9]*) echo "PINNING_SLICE=FAIL invalid seconds=$SLICE_SECONDS" >&2; exit 2 ;; esac
[ "$SLICE_SECONDS" -le 3000 ] || SLICE_SECONDS=3000
[ "$SLICE_SECONDS" -ge 60 ] || { echo "PINNING_SLICE=FAIL minimum 60 seconds" >&2; exit 2; }
mkdir -p "$STATE"
# A no-op source slice must not create another multi-gigabyte archive.
rm -f "$STATE/source-archive-unchanged"
OLD_REQUEST_ID="$(sed -n 's/^REFRESH_REQUEST_ID=//p' "$STATE/source-prep-progress.txt" 2>/dev/null | head -n 1 || true)"
PIN_REQUEST_ID="$(sed -n 's/^REFRESH_REQUEST_ID=//p' "$PINS" 2>/dev/null | head -n 1 || true)"

if [ "$STAGE" = "1" ]; then
  REQUEST_ID="$CURRENT_REQUEST_ID"
  if [ -z "$REQUEST_ID" ]; then
    echo "PINNING_REFRESH_REQUEST=FAIL current refresh request ID is empty" >&2
    exit 2
  fi
  if { [ -n "$OLD_REQUEST_ID" ] && [ "$OLD_REQUEST_ID" != "$REQUEST_ID" ]; } || \
     { [ -n "$PIN_REQUEST_ID" ] && [ "$PIN_REQUEST_ID" != "$REQUEST_ID" ]; }; then
    echo "PINNING_REFRESH_REQUEST=NEW previous_progress=${OLD_REQUEST_ID:-unknown} previous_pins=${PIN_REQUEST_ID:-legacy-or-missing} current=$REQUEST_ID"
    # Only Stage 1 may begin a new pin request. Later stages must never erase
    # a parent checkpoint because a branch file changed after Stage 1 began.
    rm -f "$PINS" "$STATE/source-sync-complete" "$STATE/source-runhooks-complete" \
      "$STATE/source-configure-complete" "$STATE/source-gn-complete" \
      "$STATE/source-ready-restored" "$STATE/source-ready" "$STATE/source-archive-unchanged" \
      "$STATE/source-sync-no-progress"
  fi
else
  # Stage 1 freezes the source refresh ID into both the pin file and progress
  # receipt. Child stages use that restored cumulative checkpoint ID and never
  # invalidate parent data based on the checked-out branch's request file.
  if [ ! -s "$PINS" ] || [ -z "$OLD_REQUEST_ID" ] || [ -z "$PIN_REQUEST_ID" ]; then
    echo "PINNING_HANDOFF=FAIL restored checkpoint lacks complete pin/progress metadata" >&2
    exit 1
  fi
  if [ "$OLD_REQUEST_ID" != "$PIN_REQUEST_ID" ]; then
    echo "PINNING_HANDOFF=FAIL parent progress ID=$OLD_REQUEST_ID differs from parent pin ID=$PIN_REQUEST_ID; checkpoint preserved" >&2
    exit 1
  fi
  REQUEST_ID="$OLD_REQUEST_ID"
  RECEIPT="$ROOT/pinning-status/stage-$((STAGE - 1))-result.env"
  if [ -s "$RECEIPT" ]; then
    RECEIPT_REQUEST_ID="$(sed -n 's/^REFRESH_REQUEST_ID=//p' "$RECEIPT" | head -n 1)"
    if [ -n "$RECEIPT_REQUEST_ID" ] && [ "$RECEIPT_REQUEST_ID" != "$REQUEST_ID" ]; then
      echo "PINNING_HANDOFF=FAIL previous stage receipt request ID differs; checkpoint preserved" >&2
      exit 1
    fi
  fi
  echo "PINNING_HANDOFF_REQUEST=RESTORED stage=$STAGE request=$REQUEST_ID parent_stage=$((STAGE - 1))"
fi
if [ -s "$STATE/source-sync-no-progress" ]; then
  echo "PINNING_NO_PROGRESS=STOP request=$REQUEST_ID; previous fetch produced no validated Git progress. Change the fetch strategy or explicitly start a new refresh request before retrying." >&2
  exit 75
fi
if [ ! -s "$PINS" ]; then
  if [ "$STAGE" = "1" ]; then
    # Stage 1 alone may bootstrap a new source pin. Resolve the latest stable
    # Brave release, derive its Chromium tag from Brave Core, and resolve that
    # exact Chromium tag to an immutable SHA before source synchronization.
    echo "PINNING_BOOTSTRAP=REQUIRED stage=1 reason=source-pins-missing-or-refresh-request-changed"
    rm -f "$STATE/source-sync-complete" "$STATE/source-runhooks-complete" \
      "$STATE/source-configure-complete" "$STATE/source-gn-complete" \
      "$STATE/source-ready-restored" "$STATE/source-ready" "$STATE/source-sync-no-progress"
  else
    echo "PINNING_GATE=FAIL source-pins.env missing after stage checkpoint restore; refusing to guess pins" >&2
    exit 1
  fi
fi
START_SECONDS=$SECONDS
DEADLINE=$((START_SECONDS + SLICE_SECONDS))
TIME_SLICE_EXPIRED=false

discard_interrupted_git_packs() {
  # Git's tmp_pack_* files are uncommitted index-pack temporaries, not a
  # resumable fetch checkpoint. timeout has returned (and reaped its process
  # group) before this function runs, so no active fetch owns these files.
  local count=0 bytes=0 size
  while IFS= read -r -d '' pack; do
    size="$(stat -c '%s' "$pack" 2>/dev/null || echo 0)"
    bytes=$((bytes + size))
    count=$((count + 1))
    rm -f -- "$pack"
  done < <(find "$SRC" -type f -path '*/objects/pack/tmp_pack_*' -print0 2>/dev/null)
  echo "BRAVE_GIT_INTERRUPTED_TEMP_PACKS=DISCARDED count=$count bytes=$bytes; only uncommitted temporary packs removed"
}

source_sync_progress_matches_parent() {
  python3 - "$ROOT" "$SRC" <<'PY'
import importlib.util
import json
import sys
from pathlib import Path

root, src = Path(sys.argv[1]), Path(sys.argv[2])
manifest_path = root / "brave-source-checkpoint.manifest.json"
if not manifest_path.is_file():
    print("PINNING_GIT_PROGRESS_COMPARE=FAIL parent manifest missing", file=sys.stderr)
    raise SystemExit(2)
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
source = manifest.get("source", {})
previous_all = source.get("git_progress_state")
previous = previous_all.get("chromium") if isinstance(previous_all, dict) else None
if previous is None:
    old = source.get("git_state", {}).get("chromium")
    if not isinstance(old, dict):
        print("PINNING_GIT_PROGRESS_COMPARE=FAIL parent Chromium Git state missing", file=sys.stderr)
        raise SystemExit(2)
    counts = old.get("counts", {})
    stable = [
        {"name": item["name"], "size_bytes": item["size_bytes"]}
        for item in old.get("packfiles", [])
        if item.get("name", "").endswith((".pack", ".idx"))
    ]
    previous = {
        "head": old.get("head"),
        "shallow": old.get("shallow"),
        "loose_object_count": counts.get("count", "0"),
        "loose_size_kib": counts.get("size", "0"),
        "packed_object_count": counts.get("in-pack", "0"),
        "pack_count": counts.get("packs", "0"),
        "packed_size_kib": counts.get("size-pack", "0"),
        "completed_packfiles": stable,
    }

spec = importlib.util.spec_from_file_location(
    "sandium_source_shards", root / ".circleci/scripts/sandium-source-shards.py"
)
if spec is None or spec.loader is None:
    print("PINNING_GIT_PROGRESS_COMPARE=FAIL cannot load source-state inspector", file=sys.stderr)
    raise SystemExit(2)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
current = module.git_repository_state(src)["progress_state"]
if current == previous:
    print("PINNING_GIT_PROGRESS_COMPARE=UNCHANGED; no completed pack, loose-object or HEAD advancement")
    raise SystemExit(0)
print("PINNING_GIT_PROGRESS_COMPARE=ADVANCED; validated Git object state changed")
raise SystemExit(10)
PY
}

run_phase() {
  local phase="$1" phase_stage="$2" marker="$3"
  if [ -s "$marker" ]; then echo "PINNING_PHASE=REUSE phase=$phase marker=$marker"; return 0; fi
  local remaining=$((DEADLINE - SECONDS))
  if [ "$remaining" -le 0 ]; then TIME_SLICE_EXPIRED=true; return 2; fi
  echo "PINNING_PHASE=START phase=$phase stage=$STAGE remaining_seconds=$remaining budget_seconds=$SLICE_SECONDS"
  set +e
  SANDIUM_PINNING_REQUEST_ID="$REQUEST_ID" BRAVE_STAGE_INDEX="$phase_stage" SANDIUM_PINNING_STAGE_INDEX="$STAGE" SANDIUM_SOURCE_PREP_PHASE="$phase" timeout --signal=INT --kill-after=30s "${remaining}s" bash "$ROOT/.circleci/scripts/prepare-brave-source.sh"
  local rc=$?
  set -e
  if [ "$rc" -eq 0 ]; then touch "$marker"; echo "PINNING_PHASE=PASS phase=$phase elapsed_seconds=$((SECONDS-START_SECONDS))"; return 0; fi
  if [ "$rc" -eq 124 ] || { { [ "$rc" -eq 130 ] || [ "$rc" -eq 137 ]; } && [ "$((SECONDS-START_SECONDS))" -ge "$((SLICE_SECONDS-30))" ]; }; then
    TIME_SLICE_EXPIRED=true
    if [ "$phase" = "sync" ]; then
      discard_interrupted_git_packs
      echo "PINNING_GIT_FETCH=INTERRUPTED; partial tmp_pack files are not treated as reusable Git progress"
    fi
    echo "PINNING_PHASE=SLICE_END phase=$phase elapsed_seconds=$((SECONDS-START_SECONDS)); preserving only validated reusable state"
    return 2
  fi
  echo "PINNING_PHASE=FAIL phase=$phase exit=$rc" >&2
  return "$rc"
}
run_phase sync 1 "$STATE/source-sync-complete" || { rc=$?; [ "$rc" -eq 2 ] || exit "$rc"; }
if [ "$TIME_SLICE_EXPIRED" = true ] && [ ! -s "$STATE/source-sync-complete" ]; then
  if source_sync_progress_matches_parent; then
    touch "$STATE/source-sync-no-progress"
    echo "PINNING_GIT_PROGRESS=NONE; next stage will stop before repeating this fetch"
  else
    rc=$?
    if [ "$rc" -eq 10 ]; then
      rm -f "$STATE/source-sync-no-progress"
      echo "PINNING_GIT_PROGRESS=ADVANCED; next stage may continue from validated Git objects"
    else
      echo "PINNING_GIT_PROGRESS=COMPARE_FAILED exit=$rc; refusing to assume progress" >&2
      exit "$rc"
    fi
  fi
fi
if [ "$TIME_SLICE_EXPIRED" = false ]; then run_phase hooks 2 "$STATE/source-runhooks-complete" || { rc=$?; [ "$rc" -eq 2 ] || exit "$rc"; }; fi
if [ "$TIME_SLICE_EXPIRED" = false ]; then run_phase configure 3 "$STATE/source-configure-complete" || { rc=$?; [ "$rc" -eq 2 ] || exit "$rc"; }; fi
if [ "$TIME_SLICE_EXPIRED" = false ]; then run_phase gn 4 "$STATE/source-gn-complete" || { rc=$?; [ "$rc" -eq 2 ] || exit "$rc"; }; fi
RESTORED_READY=false
if [ -s "$STATE/source-ready-restored" ] && [ "$PIN_REQUEST_ID" = "$REQUEST_ID" ]; then
  RESTORED_READY=true
fi
READY=false; PHASE=pinning-incomplete
if [ -s "$STATE/source-sync-complete" ] && [ -s "$STATE/source-runhooks-complete" ] && [ -s "$STATE/source-configure-complete" ] && [ -s "$STATE/source-gn-complete" ]; then
  test -s "$WORK/.gclient"; test -s "$WORK/.gclient_entries"; test -s "$PINS"
  test -s "$CORE/node_modules/.modules.yaml"; test -d "$CORE/node_modules/.pnpm"
  OUT="$SRC/out/android_Release_arm64"
  test -s "$OUT/build.ninja"; test -s "$OUT/args.gn"; test -s "$OUT/args_generated.gni"
  test -s "$SRC/build/config/siso/.sisoenv"; test -s "$SRC/build/config/siso/.sisorc"
  test -s "$SRC/build/config/siso/backend_config/backend.star"; test -s "$SRC/build/config/siso/brave_siso_config.star"
  test -x "$SRC/buildtools/reclient_cfgs/python/python_remote_wrapper"
  ACTUAL_BRAVE_TAG="$(git -C "$CORE" describe --tags --exact-match)"
  ACTUAL_CHROMIUM_SHA="$(git -C "$SRC" rev-parse HEAD)"
  EXPECTED_BRAVE_TAG="$(sed -n 's/^BRAVE_CORE_TAG=//p' "$PINS" | head -n 1)"
  EXPECTED_CHROMIUM_SHA="$(sed -n 's/^CHROMIUM_SHA=//p' "$PINS" | head -n 1)"
  test "$ACTUAL_BRAVE_TAG" = "$EXPECTED_BRAVE_TAG"; test "$ACTUAL_CHROMIUM_SHA" = "$EXPECTED_CHROMIUM_SHA"
  READY=true; PHASE=source-ready; touch "$STATE/source-ready"
  echo "SANDIUM_PINNING_REFERENCE=READY brave=$ACTUAL_BRAVE_TAG chromium_sha=$ACTUAL_CHROMIUM_SHA"
fi
{
  echo "STAGE=$STAGE"; echo "PHASE=$PHASE"; echo "WORKFLOW_ID=${CIRCLE_WORKFLOW_ID:-local}"
  echo "REFRESH_REQUEST_ID=$REQUEST_ID"; cat "$PINS"
  if [ "$RESTORED_READY" = true ] && [ "$READY" = true ]; then echo "READY_ALREADY=true"; fi
  echo "PINNING_SECONDS=$((SECONDS-START_SECONDS))"; echo "SAVED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$STATE/source-prep-progress.txt"
export SANDIUM_ARCHIVE_WORKERS=8
if [ "$READY" = true ]; then
  if [ "$RESTORED_READY" = true ]; then
    touch "$STATE/source-archive-unchanged"
    python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" archive --root "$ROOT" --workers 8 --stage "$STAGE" --ready --skip-if-unchanged --delta
    echo "SANDIUM_PINNING_ARCHIVE=REUSE already-verified-ready-reference=true stage=$STAGE; lineage delta recorded"
  else
    python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" archive --root "$ROOT" --workers 8 --stage "$STAGE" --ready --delta
    python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" verify --root "$ROOT" --workers 8 --ready --zstd-test
    echo "SANDIUM_PINNING_ARCHIVE=PASS ready=true stage=$STAGE; changed shards only"
  fi
else
  # Every stage, including Stage 1 retries, may reuse an identical verified
  # progress checkpoint. A new refresh request or changed durable state still
  # creates a new cumulative archive.
  python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" archive --root "$ROOT" --workers 8 --stage "$STAGE" --skip-if-unchanged --delta
  if [ -s "$STATE/source-archive-unchanged" ]; then
    echo "SANDIUM_PINNING_ARCHIVE=REUSE unchanged_source_state=true stage=$STAGE; do not upload duplicate shards"
  else
    python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" verify --root "$ROOT" --workers 8
    echo "SANDIUM_PINNING_ARCHIVE=PASS ready=false stage=$STAGE; next stage resumes"
  fi
fi
