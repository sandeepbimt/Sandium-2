#!/usr/bin/env bash
set -euo pipefail

MODE="${1:?usage: restore-brave-source-checkpoint.sh <base|progress>}"
ROOT="${CIRCLE_WORKING_DIRECTORY:?CIRCLE_WORKING_DIRECTORY is required}"
WORK="$ROOT/brave-work"

fresh_bootstrap() {
  # Clear only this ephemeral runner workspace. Immutable CircleCI caches and
  # the protected canonical reference remain untouched and recoverable.
  rm -rf "$WORK" \
    "$ROOT/brave-source-checkpoint.shards" \
    "$ROOT/brave-source-checkpoint.manifest.json" \
    "$ROOT/brave-workspace-checkpoint.shards" \
    "$ROOT/brave-workspace-checkpoint.manifest.json" \
    "$ROOT/brave-workspace-checkpoint.tar.zst" \
    "$ROOT/brave-reference-ready.tar.zst"
  mkdir -p "$WORK/.sandium"
  touch "$WORK/.sandium/fresh-bootstrap-required"
  echo "SOURCE_PREP_BASE=FRESH_BOOTSTRAP_REQUIRED reason=no-valid-restorable-reference"
}

restore_source_archive() {
  local ready="$1"
  if [ ! -d "$ROOT/brave-source-checkpoint.shards" ] || [ ! -s "$ROOT/brave-source-checkpoint.manifest.json" ]; then
    return 1
  fi
  if [ "$ready" = "true" ]; then
    python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" verify --root "$ROOT" --workers 8 --ready --zstd-test || return 1
    python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" restore --root "$ROOT" --workers 8 --ready || return 1
    mkdir -p "$WORK/.sandium"
    touch "$WORK/.sandium/source-ready-restored" \
      "$WORK/.sandium/source-sync-complete" \
      "$WORK/.sandium/source-runhooks-complete" \
      "$WORK/.sandium/source-configure-complete" \
      "$WORK/.sandium/source-gn-complete"
    echo "SOURCE_PREP_BASE=PINNED_SOURCE_READY all-cumulative-stage-data-restored"
  else
    python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" verify --root "$ROOT" --workers 8 || return 1
    python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" restore --root "$ROOT" --workers 8 || return 1
    mkdir -p "$WORK/.sandium"
    echo "SOURCE_PREP_BASE=VALID_PROGRESS_CHECKPOINT all-cumulative-stage-data-restored"
  fi
  return 0
}

restore_legacy_reference() {
  if { [ -d "$ROOT/brave-workspace-checkpoint.shards" ] && [ -s "$ROOT/brave-workspace-checkpoint.manifest.json" ]; } || \
     [ -s "$ROOT/brave-workspace-checkpoint.tar.zst" ] || [ -s "$ROOT/brave-reference-ready.tar.zst" ]; then
    echo "SOURCE_PREP_BASE=TRY_LEGACY_FULL_WORKSPACE_REFERENCE"
    export BRAVE_STAGE_INDEX=1
    export SANDIUM_ARCHIVE_WORKERS=8
    if bash "$ROOT/.circleci/scripts/archive-brave-workspace.sh" restore; then
      mkdir -p "$WORK/.sandium"
      echo "SOURCE_PREP_BASE=LEGACY_FULL_WORKSPACE_RESTORED"
      return 0
    fi
  fi
  return 1
}

case "$MODE" in
  base)
    if [ -s "$ROOT/brave-source-checkpoint.manifest.json" ]; then
      if MANIFEST_READY="$(python3 -c 'import json,sys; print("true" if json.load(open(sys.argv[1],encoding="utf-8")).get("ready") is True else "false")' "$ROOT/brave-source-checkpoint.manifest.json" 2>/dev/null)"; then
        :
      else
        MANIFEST_READY=invalid
      fi
    else
      MANIFEST_READY=missing
    fi

    if [ "$MANIFEST_READY" = "true" ]; then
      # A ready-marked archive that fails ready validation is corrupt or stale;
      # never downgrade it to an ordinary progress checkpoint.
      if ! restore_source_archive true; then
        if ! restore_legacy_reference; then fresh_bootstrap; fi
      fi
    elif [ "$MANIFEST_READY" = "false" ]; then
      if ! restore_source_archive false; then
        if ! restore_legacy_reference; then fresh_bootstrap; fi
      fi
    else
      if ! restore_legacy_reference; then fresh_bootstrap; fi
    fi
    ;;
  progress)
    if ! restore_source_archive false; then
      echo "SOURCE_PREP_PROGRESS=FAIL prior-stage cumulative checkpoint is missing or invalid" >&2
      exit 1
    fi
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
