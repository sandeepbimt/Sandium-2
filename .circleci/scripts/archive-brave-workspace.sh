#!/usr/bin/env bash
set -euo pipefail
MODE="${1:-}"
ROOT="${CIRCLE_WORKING_DIRECTORY:-$(pwd)}"
WORK="$ROOT/brave-work"
ARCHIVE="$ROOT/brave-workspace-checkpoint.tar.zst"
SHARDS="$ROOT/brave-workspace-checkpoint.shards"
SHARD_MANIFEST="$ROOT/brave-workspace-checkpoint.manifest.json"
OUT="$WORK/src/out/android_Release_arm64"
MANIFEST="$WORK/.sandium/checkpoint-manifest.txt"
WORKERS="${SANDIUM_ARCHIVE_WORKERS:-8}"
fail() { echo "BRAVE_WORKSPACE_ARCHIVE=FAIL $*" >&2; exit 1; }
ensure_zstd() {
  if ! command -v zstd >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y zstd
  fi
  command -v zstd >/dev/null 2>&1 || fail "zstd is unavailable"
}
case "$MODE" in
  restore)
    ensure_zstd
    # New references and handoffs restore the same manifest + shard directory.
    if [ -e "$SHARDS" ] || [ -e "$SHARD_MANIFEST" ]; then
      [ -d "$SHARDS" ] && [ -s "$SHARD_MANIFEST" ] || fail "partial parallel checkpoint set: shard directory or manifest is missing"
      echo "BRAVE_WORKSPACE_ARCHIVE_RESTORE=PARALLEL_SHARDS workers=$WORKERS"
      python3 "$ROOT/.circleci/scripts/sandium-checkpoint-shards.py" restore --root "$ROOT" --workers "$WORKERS"
      [ -s "$WORK/.gclient" ] || fail "restored shards are missing brave-work/.gclient"
      [ -s "$OUT/build.ninja" ] || fail "restored shards are missing the pinned build graph"
      mkdir -p "$WORK/.sandium"
      touch "$WORK/.sandium/workspace-checkpoint-restored"
      echo "BRAVE_WORKSPACE_ARCHIVE_RESTORE=PASS checkpoint=PARALLEL_SHARDS"
    elif [ -s "$ROOT/brave-reference-ready.tar.zst" ] && [ ! -s "$ARCHIVE" ]; then
      # Migration path for v1 single-file references.
      cp "$ROOT/brave-reference-ready.tar.zst" "$ARCHIVE"
      [ ! -s "$ROOT/brave-reference-ready.meta" ] || cp "$ROOT/brave-reference-ready.meta" "$ROOT/brave-workspace-checkpoint.meta"
      zstd -t "$ARCHIVE" >/dev/null || fail "legacy reference archive failed zstd integrity test"
      zstd -dc "$ARCHIVE" | tar -xf - -C "$ROOT"
      mkdir -p "$WORK/.sandium"
      touch "$WORK/.sandium/workspace-checkpoint-restored"
      echo "BRAVE_WORKSPACE_ARCHIVE_RESTORE=PASS checkpoint=LEGACY_SINGLE_FILE"
    elif [ -s "$ARCHIVE" ]; then
      zstd -t "$ARCHIVE" >/dev/null || fail "legacy checkpoint archive failed zstd integrity test"
      zstd -dc "$ARCHIVE" | tar -xf - -C "$ROOT"
      mkdir -p "$WORK/.sandium"
      touch "$WORK/.sandium/workspace-checkpoint-restored"
      echo "BRAVE_WORKSPACE_ARCHIVE_RESTORE=PASS checkpoint=LEGACY_SINGLE_FILE"
    elif [ -s "$WORK/.gclient" ] && [ -s "$OUT/build.ninja" ]; then
      mkdir -p "$WORK/.sandium"
      touch "$WORK/.sandium/workspace-checkpoint-restored"
      echo "BRAVE_WORKSPACE_ARCHIVE_RESTORE=LEGACY_DIRECT_CACHE stage=$BRAVE_STAGE_INDEX"
    elif [ "$BRAVE_STAGE_INDEX" = "1" ]; then
      echo "BRAVE_WORKSPACE_ARCHIVE_RESTORE=FIRST_BUILD no prior checkpoint; source initialization will create the baseline"
    else
      fail "no parallel-shard, legacy archive or direct-cache checkpoint restored for stage $BRAVE_STAGE_INDEX"
    fi
    ;;
  archive)
    [ -d "$WORK/src" ] || fail "missing $WORK/src"
    [ -s "$WORK/.gclient" ] || fail "missing $WORK/.gclient"
    [ -s "$OUT/build.ninja" ] || fail "missing $OUT/build.ninja"
    [ -s "$MANIFEST" ] || fail "missing validated checkpoint manifest"
    grep -qx "CHECKPOINT_VALID=true" "$MANIFEST" || fail "checkpoint manifest is not marked valid"
    ensure_zstd
    echo "SANDIUM-FULL-MODE archive: parallel workers=$WORKERS"
    echo "BRAVE_WORKSPACE_ARCHIVE_INPUT_SIZE=$(du -sh "$WORK" | awk '{print $1}')"
    echo "BRAVE_WORKSPACE_ARCHIVE_OUTPUT_FILESYSTEM=$(df -h "$ROOT" | tail -n 1 | awk '{print $4 " available of " $2}')"
    python3 "$ROOT/.circleci/scripts/sandium-checkpoint-shards.py" archive --root "$ROOT" --workers "$WORKERS"
    [ -d "$SHARDS" ] || fail "parallel shard directory was not created"
    [ -s "$SHARD_MANIFEST" ] || fail "parallel shard manifest was not created"
    python3 "$ROOT/.circleci/scripts/checkpoint-stage-receipt.py" write \
      --root "$ROOT" \
      --stage "${BRAVE_STAGE_INDEX:?BRAVE_STAGE_INDEX is required for FULL MODE archive receipt}" \
      --workflow-id "${CIRCLE_WORKFLOW_ID:?CIRCLE_WORKFLOW_ID is required for FULL MODE archive receipt}"
    echo "BRAVE_WORKSPACE_ARCHIVE_CREATE=PASS format=parallel-tar-zstd-shards workers=$WORKERS"
    ;;
  verify)
    ensure_zstd
    python3 "$ROOT/.circleci/scripts/sandium-checkpoint-shards.py" verify --root "$ROOT" --workers "$WORKERS" --zstd-test
    ;;
  *)
    fail "usage: $0 {restore|archive|verify}"
    ;;
esac
