#!/usr/bin/env bash
# Pinned payload with explicit branch-scoped candidate activation.
set -euo pipefail
ROOT="${CIRCLE_WORKING_DIRECTORY:?}"
test "${CIRCLE_BRANCH:?}" = experiment/ubo-runtime
ACTIVATE="${SANDIUM_UBO_ACTIVATE_CANDIDATE:-false}"
case "$ACTIVATE" in true|false) ;; *) echo "Invalid activation mode" >&2; exit 2;; esac
SRC="$ROOT/brave-work/src"
OUT="$SRC/out/android_Release_arm64"
CACHE="$ROOT/brave-work/.sandium/ubo-upstream-cache"
ARTIFACTS="$ROOT/ubo-source-artifacts"
# Fresh destination per CI stage. Upstream cache is verified, never blindly reused.
STAGE="$(mktemp -d /tmp/sandium-ubo-stage.XXXXXX)"
mkdir -p "$ARTIFACTS"
git -C "$ROOT" rev-parse HEAD > "$STAGE/integration.txt"
printf '\nCandidate activation requested=%s; actual runtime owner unverified. Private profiles native. Fallback must be reported explicitly.\n' "$ACTIVATE" >> "$STAGE/integration.txt"
# Include exact scripts/adapter/build recipe, not just a mutable repository URL.
git -C "$ROOT" archive HEAD experiments/ubo-runtime .circleci > "$STAGE/sandium-integration-source.tar"
sha256sum "$STAGE/sandium-integration-source.tar" >> "$STAGE/integration.txt"
python3 "$ROOT/experiments/ubo-runtime/bundle/prepare.py" \
  --cache-dir "$CACHE" --fetch --output "$STAGE/prepared.zip" \
  --source-artifacts "$STAGE/corresponding-source" --integration-details "$STAGE/integration.txt"
cp "$STAGE/sandium-integration-source.tar" "$STAGE/corresponding-source/"
cp -a "$STAGE/corresponding-source/." "$ARTIFACTS/"
python3 "$ROOT/experiments/ubo-runtime/loader/apply.py" --src "$SRC" --bundle "$STAGE/prepared.zip"
python3 "$ROOT/experiments/ubo-runtime/shields_bridge/apply.py" --core "$SRC/brave"
python3 "$ROOT/experiments/ubo-runtime/routing/apply.py" --core "$SRC/brave"
python3 "$ROOT/experiments/ubo-runtime/routing/apply_startup.py" --core "$SRC/brave"
python3 "$ROOT/experiments/ubo-runtime/request_policy/apply.py" --src "$SRC"
# Baseline runtime-off gates ran before these overlays, not on candidate postimages.
if [ "$ACTIVATE" = true ]; then
  python3 "$ROOT/experiments/ubo-runtime/activation/apply.py" --core "$SRC/brave" --branch "$CIRCLE_BRANCH" --mode on
else
  python3 "$ROOT/experiments/ubo-runtime/activation/apply.py" --core "$SRC/brave" --mode verify-off
fi
python3 "$ROOT/experiments/ubo-runtime/status/apply.py" --core "$SRC/brave"
export DEPOT_TOOLS_UPDATE=0
export PYTHONPATH="$SRC/brave/script:$SRC/tools/grit/grit/extern:$SRC/brave/vendor/requests:$SRC/build:$SRC/brave/vendor/depot_tools:${PYTHONPATH:-}"
(cd "$SRC" && "$SRC/buildtools/linux64/gn" gen "$OUT")
python3 "$ROOT/experiments/ubo-runtime/verify_compile_inputs.py" --src "$SRC"
printf 'SANDIUM_UBO_PAYLOAD=STAGED; candidate_activation=%s; runtime_owner=UNVERIFIED; private=NATIVE\n' "$ACTIVATE"
