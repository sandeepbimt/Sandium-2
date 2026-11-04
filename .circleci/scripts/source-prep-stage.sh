#!/usr/bin/env bash
set -euo pipefail

STAGE="${1:?usage: source-prep-stage.sh <1..5>}"
case "$STAGE" in 1|2|3|4|5) ;; *) echo "SOURCE_PREP_STAGE=FAIL invalid stage=$STAGE" >&2; exit 2 ;; esac

ROOT="${CIRCLE_WORKING_DIRECTORY:?CIRCLE_WORKING_DIRECTORY is required}"
WORK="$ROOT/brave-work"
SRC="$WORK/src"
CORE="$SRC/brave"
export BRAVE_STAGE_INDEX="$STAGE"

case "$STAGE" in
  1)
    export SANDIUM_SOURCE_PREP_PHASE=sync
    echo "SANDIUM_SOURCE_PREP_STAGE=1 action=sync-chromium-nohooks"
    bash "$ROOT/.circleci/scripts/prepare-brave-source.sh"
    PHASE="chromium-synchronized"
    ;;
  2)
    export SANDIUM_SOURCE_PREP_PHASE=hooks
    echo "SANDIUM_SOURCE_PREP_STAGE=2 action=runhooks"
    bash "$ROOT/.circleci/scripts/prepare-brave-source.sh"
    PHASE="runhooks-complete"
    ;;
  3)
    export SANDIUM_SOURCE_PREP_PHASE=configure
    echo "SANDIUM_SOURCE_PREP_STAGE=3 action=host-deps-and-siso-environment"
    bash "$ROOT/.circleci/scripts/prepare-brave-source.sh"
    PHASE="build-environment-configured"
    ;;
  4)
    export SANDIUM_SOURCE_PREP_PHASE=gn
    echo "SANDIUM_SOURCE_PREP_STAGE=4 action=generate-gn-graph-no-compilation"
    bash "$ROOT/.circleci/scripts/prepare-brave-source.sh"
    PHASE="gn-graph-ready"
    ;;
  5)
    export SANDIUM_SOURCE_PREP_PHASE=final
    echo "SANDIUM_SOURCE_PREP_STAGE=5 action=final-source-pin-validation"
    bash "$ROOT/.circleci/scripts/prepare-brave-source.sh"
    PHASE="source-ready"
    ;;
esac

PINS="$WORK/.sandium/source-pins.env"
test -s "$PINS" || { echo "SOURCE_PREP_GATE=FAIL source-pins.env missing" >&2; exit 1; }
mkdir -p "$WORK/.sandium"
{
  echo "STAGE=$STAGE"
  echo "PHASE=$PHASE"
  echo "WORKFLOW_ID=${CIRCLE_WORKFLOW_ID:-local}"
  cat "$PINS"
  echo "SAVED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$WORK/.sandium/source-prep-progress.txt"

if [ "$STAGE" = "5" ]; then
  OUT="$SRC/out/android_Release_arm64"
  test -s "$WORK/.gclient"
  test -s "$WORK/.gclient_entries"
  test -s "$OUT/build.ninja"
  test -s "$OUT/args.gn"
  test -s "$OUT/args_generated.gni"
  test -s "$SRC/build/config/siso/.sisoenv"
  test -s "$SRC/build/config/siso/.sisorc"
  test -s "$SRC/build/config/siso/backend_config/backend.star"
  test -s "$SRC/build/config/siso/brave_siso_config.star"
  test -x "$SRC/buildtools/reclient_cfgs/python/python_remote_wrapper"
  grep -Fq 'use_remoteexec = true' "$OUT/args_generated.gni"
  grep -Fq 'use_siso = true' "$OUT/args_generated.gni"
  grep -Fq 'use_reclient = false' "$OUT/args_generated.gni"
  echo "SANDIUM_SOURCE_READY_VALIDATION=PASS"
  python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" archive \
    --root "$ROOT" --workers 8 --stage "$STAGE" --ready
  python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" verify \
    --root "$ROOT" --workers 8 --ready --zstd-test
  echo "SANDIUM_SOURCE_READY=PASS archive=source-only shards=8"
else
  python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" archive \
    --root "$ROOT" --workers 8 --stage "$STAGE"
  python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" verify \
    --root "$ROOT" --workers 8
  echo "SANDIUM_SOURCE_PROGRESS=PASS stage=$STAGE phase=$PHASE"
fi
