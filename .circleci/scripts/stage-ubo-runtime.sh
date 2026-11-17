#!/usr/bin/env bash
# Full payload compilation only. Activation/cutover remains separately gated.
set -euo pipefail
ROOT="${CIRCLE_WORKING_DIRECTORY:?}"
test "${CIRCLE_BRANCH:?}" = experiment/ubo-runtime
SRC="$ROOT/brave-work/src"
OUT="$SRC/out/android_Release_arm64"
CACHE="$ROOT/brave-work/.sandium/ubo-upstream-cache"
ARTIFACTS="$ROOT/ubo-source-artifacts"
# Fresh destination per CI stage. Upstream cache is verified, never blindly reused.
STAGE="$(mktemp -d /tmp/sandium-ubo-stage.XXXXXX)"
mkdir -p "$ARTIFACTS"
git -C "$ROOT" rev-parse HEAD > "$STAGE/integration.txt"
printf '\nRuntime defaults OFF; Brave filtering retained. Not runtime verification.\n' >> "$STAGE/integration.txt"
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
# Do not use the baseline runtime-off source allowlist after intentional overlays.
# Preserve the activation invariant independently of the staged source identity.
python3 - "$SRC/brave/browser/brave_browser_features.cc" <<'PY'
import pathlib,sys
text=pathlib.Path(sys.argv[1]).read_text()
assert text.count('BASE_FEATURE(kSandiumUboRuntime, base::FEATURE_DISABLED_BY_DEFAULT);')==1
assert 'BASE_FEATURE(kSandiumUboRuntime, base::FEATURE_ENABLED_BY_DEFAULT)' not in text
PY
export DEPOT_TOOLS_UPDATE=0
export PYTHONPATH="$SRC/brave/script:$SRC/tools/grit/grit/extern:$SRC/brave/vendor/requests:$SRC/build:$SRC/brave/vendor/depot_tools:${PYTHONPATH:-}"
(cd "$SRC" && "$SRC/buildtools/linux64/gn" gen "$OUT")
python3 "$ROOT/experiments/ubo-runtime/verify_compile_inputs.py" --src "$SRC"
grep -F 'BASE_FEATURE(kSandiumUboExclusiveRouting, base::FEATURE_DISABLED_BY_DEFAULT);' \
  "$SRC/brave/components/sandium_ubo_routing/routing.cc" >/dev/null
echo 'SANDIUM_UBO_PAYLOAD=STAGED; activation=OFF; native/runtime validation pending'
