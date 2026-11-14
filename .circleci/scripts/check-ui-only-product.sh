#!/usr/bin/env bash
# Keep the CI product gate independent of the executor's Python packages.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEPS="$(mktemp -d)"
trap 'rm -rf "$DEPS"' EXIT
python3 -m pip install --disable-pip-version-check --no-input --no-deps \
  --only-binary=:all: --target "$DEPS" 'PyYAML==6.0.2'
PYTHONPATH="$DEPS${PYTHONPATH:+:$PYTHONPATH}" python3 "$ROOT/tests/test_ui_only_product.py"
