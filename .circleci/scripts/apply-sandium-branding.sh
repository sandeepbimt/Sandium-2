#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "${CIRCLE_WORKING_DIRECTORY:?CIRCLE_WORKING_DIRECTORY is required}" && pwd)"
SRC_DIR="$ROOT/brave-work/src"
CORE_DIR="$SRC_DIR/brave"

python3 "$ROOT/.circleci/scripts/apply-sandium-branding-refresh.py" \
  --core "$CORE_DIR" \
  --src "$SRC_DIR" \
  --repo-root "$ROOT"

python3 "$ROOT/.circleci/scripts/test-sandium-branding-refresh.py" \
  --core "$CORE_DIR" \
  --src "$SRC_DIR"
