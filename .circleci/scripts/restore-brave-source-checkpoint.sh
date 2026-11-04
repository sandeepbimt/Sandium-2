#!/usr/bin/env bash
set -euo pipefail

MODE="${1:?usage: restore-brave-source-checkpoint.sh <base|progress>}"
ROOT="${CIRCLE_WORKING_DIRECTORY:?CIRCLE_WORKING_DIRECTORY is required}"
WORK="$ROOT/brave-work"
case "$MODE" in
  base)
    if [ -d "$ROOT/brave-source-checkpoint.shards" ] && [ -s "$ROOT/brave-source-checkpoint.manifest.json" ]; then
      echo "SOURCE_PREP_BASE=PINNED_SOURCE_READY"
      python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" verify --root "$ROOT" --workers 8 --ready --zstd-test
      python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" restore --root "$ROOT" --workers 8 --ready
      mkdir -p "$WORK/.sandium"
      touch "$WORK/.sandium/source-ready-restored"
    elif [ -d "$ROOT/brave-workspace-checkpoint.shards" ] && [ -s "$ROOT/brave-workspace-checkpoint.manifest.json" ]; then
      echo "SOURCE_PREP_BASE=FULL_WORKSPACE_REFERENCE"
      export BRAVE_STAGE_INDEX=1
      export SANDIUM_ARCHIVE_WORKERS=8
      bash "$ROOT/.circleci/scripts/archive-brave-workspace.sh" restore
    elif [ -s "$ROOT/brave-workspace-checkpoint.tar.zst" ] || [ -s "$ROOT/brave-reference-ready.tar.zst" ]; then
      echo "SOURCE_PREP_BASE=LEGACY_FULL_WORKSPACE_REFERENCE"
      export BRAVE_STAGE_INDEX=1
      export SANDIUM_ARCHIVE_WORKERS=8
      bash "$ROOT/.circleci/scripts/archive-brave-workspace.sh" restore
    else
      echo "SOURCE_PREP_BASE=FAIL neither pinned source archive nor protected canonical reference was restored" >&2
      exit 1
    fi
    ;;
  progress)
    [ -d "$ROOT/brave-source-checkpoint.shards" ] && [ -s "$ROOT/brave-source-checkpoint.manifest.json" ] || {
      echo "SOURCE_PREP_PROGRESS=FAIL prior stage source checkpoint missing" >&2
      exit 1
    }
    python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" verify --root "$ROOT" --workers 8
    python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" restore --root "$ROOT" --workers 8
    echo "SOURCE_PREP_PROGRESS=RESTORED"
    ;;
  *)
    echo "SOURCE_PREP_RESTORE=FAIL invalid mode=$MODE" >&2
    exit 2
    ;;
esac

mkdir -p "$WORK/.sandium"
touch "$WORK/.sandium/workspace-checkpoint-restored"
echo "SOURCE_PREP_RESTORE=PASS mode=$MODE"
