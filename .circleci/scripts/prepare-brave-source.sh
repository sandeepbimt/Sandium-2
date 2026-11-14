#!/usr/bin/env bash
set -euo pipefail
ROOT="$CIRCLE_WORKING_DIRECTORY"

# Configure the persistent APT workspace cache before any dependency installation.
# Reuse restored .deb files and reduce repeated index/network overhead during PPBAS.
APT_CACHE_DIR="$ROOT/.apt-cache"
mkdir -p "$APT_CACHE_DIR/archives/partial" "$APT_CACHE_DIR/lists/partial"

# APT drops download privileges to _apt even when install-build-deps.sh is
# launched through sudo. CircleCI cache restores can leave these directories
# owned by circleci/root with restrictive permissions, which makes APT fall
# back to unsandboxed root downloads and can fail the dependency step.
sudo chmod 0755 "$ROOT" "$APT_CACHE_DIR"
sudo install -d -o _apt -g root -m 0755 \
  "$APT_CACHE_DIR/archives" \
  "$APT_CACHE_DIR/archives/partial" \
  "$APT_CACHE_DIR/lists" \
  "$APT_CACHE_DIR/lists/partial"
sudo chown -R _apt:root "$APT_CACHE_DIR/archives" "$APT_CACHE_DIR/lists"
sudo find "$APT_CACHE_DIR/archives" "$APT_CACHE_DIR/lists" -type d -exec chmod 0755 {} +
sudo find "$APT_CACHE_DIR/archives" "$APT_CACHE_DIR/lists" -type f -exec chmod 0644 {} +
echo "PPBAS_APT_PERMISSIONS=PASS owner=_apt mode=0755"

sudo tee /etc/apt/apt.conf.d/99sandium-workspace-cache >/dev/null <<APTCONF
Dir::Cache::archives "$APT_CACHE_DIR/archives";
Dir::State::lists "$APT_CACHE_DIR/lists";
Acquire::Retries "5";
Acquire::Languages "none";
Acquire::Queue-Mode "host";
Acquire::http::Pipeline-Depth "10";
Acquire::https::Pipeline-Depth "10";
Acquire::http::Timeout "60";
Acquire::https::Timeout "60";
APTCONF
# Sandium filter subscriptions use public list URLs; no Brave Services key is required.
NODE_DIR="$ROOT/node-runtime"
if [ ! -x "$NODE_DIR/bin/node" ]; then
  mkdir -p "$NODE_DIR"
  curl -fsSL --retry 3 https://nodejs.org/dist/v24.16.0/node-v24.16.0-linux-x64.tar.xz -o "$ROOT/node-v24.16.0.tar.xz"
  tar -xJf "$ROOT/node-v24.16.0.tar.xz" --strip-components=1 -C "$NODE_DIR"
  rm -f "$ROOT/node-v24.16.0.tar.xz"
fi
export PATH="$NODE_DIR/bin:$PATH"
if ! command -v pnpm >/dev/null 2>&1 || [ "$(pnpm --version 2>/dev/null || true)" != "11.11.0" ]; then
  npm install --global pnpm@11.11.0
else
  echo "PPBAS_PNPM_REUSE=PASS version=$(pnpm --version)"
fi
echo "export PATH=\"$NODE_DIR/bin:\$PATH\"" >> "$BASH_ENV"
mkdir -p "$ROOT/brave-work"
if [ ! -d "$ROOT/brave-work/src/brave/.git" ]; then
  git clone --depth 1 --branch v1.98.62 https://github.com/brave/brave-core.git "$ROOT/brave-work/src/brave"
fi
cd "$ROOT/brave-work/src/brave"
CHROMIUM_TAG="$(node -e 'console.log(JSON.parse(require("fs").readFileSync("package.json")).config.projects.chrome.tag)')"
echo "BRAVE_CORE_TAG=v1.98.62"
echo "CHROMIUM_TAG=$CHROMIUM_TAG"
echo "BRAVE_STAGE=${BRAVE_STAGE_INDEX:?BRAVE_STAGE_INDEX is required}"
test -n "$CHROMIUM_TAG"
# Fresh machines do not inherit installed OS packages from source checkpoints.
# Later stages install only host prerequisites, never stage-1 source preparation.
if [ "$BRAVE_STAGE_INDEX" != "1" ]; then
  bash "$ROOT/.circleci/scripts/install-flow-host-deps.sh"
fi
if [ "${BRAVE_STAGE_INDEX:?BRAVE_STAGE_INDEX is required}" = "1" ]; then
  pnpm config set store-dir "$HOME/.cache/pnpm-store"
  SRC_DIR="$ROOT/brave-work/src"
  CORE_DIR="$SRC_DIR/brave"
  OUT="$SRC_DIR/out/android_Release_arm64"
  SOURCE_REUSE=false
  CHROMIUM_PIN="d331de35ca8ab1358c7a17e4bd41627d55eaef51"

  # Use Brave's native RBE configuration path. At v1.98.62,
  # pnpm sync reads rbe_service from brave/.env and writes the
  # reapi_* custom_vars into .gclient before running Chromium hooks.
  REAPI_ADDRESS="$(printenv SANDIUM_REAPI_ADDRESS 2>/dev/null || true)"
  REAPI_INSTANCE="default"
  [ -n "$REAPI_ADDRESS" ] || REAPI_ADDRESS="remote.buildbuddy.io:443"
  case "$REAPI_ADDRESS" in
    *:443) ;;
    *) echo "BRAVE_RBE_CONFIG_GATE=FAIL unexpected REAPI address (expected host:443): $REAPI_ADDRESS" >&2; exit 1 ;;
  esac
  ENV_FILE="$CORE_DIR/.env"
  ENV_TMP="$(mktemp "$CORE_DIR/.env.tmp.XXXXXX")"
  if [ -f "$ENV_FILE" ]; then
    grep -Ev '^(rbe_service|use_remoteexec|brave_services_key)=' "$ENV_FILE" > "$ENV_TMP" || true
  fi
  printf '%s\n' \
    "rbe_service=$REAPI_ADDRESS" \
    'use_remoteexec=true' \
    >> "$ENV_TMP"
  mv "$ENV_TMP" "$ENV_FILE"
  echo "BRAVE_RBE_ENDPOINT=$REAPI_ADDRESS"
  echo "BRAVE_RBE_INSTANCE=$REAPI_INSTANCE"
  export DEPOT_TOOLS_UPDATE=0

  # Reuse the pinned source tree, but refresh Brave's generated Siso config.
  if [ -s "$ROOT/brave-work/.gclient" ] && [ -e "$SRC_DIR/.git" ] && \
     [ -x "$SRC_DIR/build/install-build-deps.sh" ] && \
     [ "$(git -C "$CORE_DIR" describe --tags --exact-match 2>/dev/null || true)" = "v1.98.62" ] && \
     [ "$(git -C "$SRC_DIR" rev-parse HEAD 2>/dev/null || true)" = "$CHROMIUM_PIN" ] && \
     [ -d "$SRC_DIR/third_party" ] && [ -d "$SRC_DIR/build" ]; then
    SOURCE_REUSE=true
    echo "BRAVE_SOURCE_REUSE=PASS; pinned source restored."
    if [ -s "$ROOT/brave-work/.sandium/workspace-checkpoint-restored" ]; then
      # The archive already contains the matching .gclient, generated GN/Siso
      # configuration, Ninja metadata and Siso filesystem journal. Re-running
      # pnpm sync here can rewrite that state and invalidate the checkpoint.
      echo "BRAVE_CHECKPOINT_PRESERVATION=PASS; skipping pnpm sync on restored workspace."
    else
      # A restored 26 GiB source tree can be complete even when the stage-handoff
      # marker is absent. If its gclient dependency manifest, pinned GN graph and
      # generated Siso files are present and already point at this BuildBuddy
      # endpoint, do not run pnpm sync: that re-applies patches, performs gclient
      # sync and reruns all 143 hooks on every fresh workflow.
      GCLIENT_FILE="$ROOT/brave-work/.gclient"
      GCLIENT_ENTRIES="$ROOT/brave-work/.gclient_entries"
      SISO_DIR="$SRC_DIR/build/config/siso"
      if [ -s "$GCLIENT_FILE" ] && [ -s "$GCLIENT_ENTRIES" ] && \
         [ -s "$OUT/build.ninja" ] && [ -s "$OUT/args.gn" ] && \
         [ -s "$SISO_DIR/.sisoenv" ] && [ -s "$SISO_DIR/.sisorc" ] && \
         grep -Fq "$REAPI_ADDRESS" "$GCLIENT_FILE" && \
         grep -Fq 'reapi_backend_config_path' "$GCLIENT_FILE" && \
         grep -Fq 'reapi_instance' "$GCLIENT_FILE" && \
         grep -Fq "SISO_REAPI_ADDRESS=$REAPI_ADDRESS" "$SISO_DIR/.sisoenv"; then
        echo "BRAVE_GCLIENT_DEPENDENCY_REUSE=PASS; pinned deps and generated Siso hooks restored."
        echo "BRAVE_GCLIENT_HOOKS=SKIPPED; reconciling source patches only."
        cd "$CORE_DIR"
        pnpm run apply_patches
      else
        echo "BRAVE_GCLIENT_DEPENDENCY_REUSE=MISS; required dependency or RBE config state is absent."
        echo "BRAVE_SOURCE_REUSE=PASS; refreshing Brave config with normal pinned sync."
        cd "$CORE_DIR"
        pnpm run sync --target_os=android --target_arch=arm64 --no-history --sync_chromium=false
      fi
    fi
  else
    echo "BRAVE_SOURCE_REUSE=MISS; source checkout incomplete or pin mismatch; full init required."
    cd "$CORE_DIR"
    pnpm run init --target_os=android --target_arch=arm64 --no-history
  fi

  # Apply Sandium launcher artwork and app display name to the pinned sources.
  bash "$ROOT/.circleci/scripts/apply-sandium-branding.sh"

  # Match the proven SSfull REAPI fix: compiler crash diagnostics must stay
  # inside this GN output directory. The upstream rebase_path("//out/...", ...)
  # produces ../clang-crashreports in compile commands; BuildBuddy rejects
  # that parent-relative output path during REAPI command validation.
  CLANG_COMPILER_GNI="$SRC_DIR/build/config/compiler/compiler.gni"
  test -s "$CLANG_COMPILER_GNI" || {
    echo "CLANG_DIAGNOSTIC_PATH_GATE=FAIL missing $CLANG_COMPILER_GNI" >&2
    exit 1
  }
  python3 - "$CLANG_COMPILER_GNI" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
old = 'clang_diagnostic_dir = rebase_path("//out/clang-crashreports", root_build_dir)'
new = 'clang_diagnostic_dir = "clang-crashreports"'
old_count = text.count(old)
new_count = text.count(new)

if old_count == 1 and new_count == 0:
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print("CLANG_DIAGNOSTIC_PATH_NORMALIZATION=PATCHED")
elif old_count == 0 and new_count == 1:
    print("CLANG_DIAGNOSTIC_PATH_NORMALIZATION=ALREADY_PATCHED")
else:
    raise SystemExit(
        "CLANG_DIAGNOSTIC_PATH_GATE=FAIL expected exactly one upstream "
        "rebase_path assignment or exactly one normalized assignment "
        "(old=%d new=%d)" % (old_count, new_count)
    )

verified = path.read_text(encoding="utf-8")
if verified.count(new) != 1 or old in verified:
    raise SystemExit("CLANG_DIAGNOSTIC_PATH_GATE=FAIL post-write verification failed")
print("CLANG_DIAGNOSTIC_PATH_GATE=PASS path=clang-crashreports")
PY

  # Make the permission fix durable: Brave's runhooks generator rewrites this
  # wrapper, so patch the generator to preserve executable mode on regeneration.
  BRAVE_CUSTOM_CONFIG="$CORE_DIR/third_party/reclient_configs/brave_custom/brave_custom.py"
  test -s "$BRAVE_CUSTOM_CONFIG" || {
    echo "BRAVE_PYTHON_REMOTE_WRAPPER_GATE=FAIL Brave wrapper generator missing" >&2
    exit 1
  }
  python3 - "$BRAVE_CUSTOM_CONFIG" <<'PY'
from pathlib import Path
import sys

source_file = Path(sys.argv[1])
source = source_file.read_text(encoding="utf-8")
marker = (
    "    FileUtils.write_text_file(\n"
    "        (f'{Paths.src_dir}/buildtools/reclient_cfgs/python/'\n"
    "         'python_remote_wrapper'),\n"
    "        ShellTemplate(python_remote_wrapper_template).substitute(\n"
    "            template_vars))\n"
)
needle = "    os.chmod(wrapper_path, 0o755)"
if needle in source:
    print("BRAVE_PYTHON_REMOTE_WRAPPER_GENERATOR_GATE=PASS already patched")
else:
    replacement = (
        "    wrapper_path = (\n"
        "        f'{Paths.src_dir}/buildtools/reclient_cfgs/python/'\n"
        "        'python_remote_wrapper'\n"
        "    )\n"
        "    FileUtils.write_text_file(\n"
        "        wrapper_path,\n"
        "        ShellTemplate(python_remote_wrapper_template).substitute(\n"
        "            template_vars))\n"
        "    os.chmod(wrapper_path, 0o755)\n"
    )
    if source.count(marker) != 1:
        raise SystemExit(
            "BRAVE_PYTHON_REMOTE_WRAPPER_GENERATOR_GATE=FAIL expected one known Brave generator block"
        )
    source_file.write_text(source.replace(marker, replacement, 1), encoding="utf-8")
    print("BRAVE_PYTHON_REMOTE_WRAPPER_GENERATOR_GATE=PASS patched")
PY

  # Brave writes its remote Python wrapper as plain text. Siso executes this
  # path directly on BuildBuddy workers, so persist the executable bit before
  # the Stage 1 workspace checkpoint is created.
  PYTHON_REMOTE_WRAPPER="$SRC_DIR/buildtools/reclient_cfgs/python/python_remote_wrapper"
  test -s "$PYTHON_REMOTE_WRAPPER" || {
    echo "BRAVE_PYTHON_REMOTE_WRAPPER_GATE=FAIL generated wrapper missing: $PYTHON_REMOTE_WRAPPER" >&2
    exit 1
  }
  chmod 755 "$PYTHON_REMOTE_WRAPPER"
  test -x "$PYTHON_REMOTE_WRAPPER" || {
    echo "BRAVE_PYTHON_REMOTE_WRAPPER_GATE=FAIL wrapper is not executable after chmod" >&2
    exit 1
  }
  stat -c 'BRAVE_PYTHON_REMOTE_WRAPPER_MODE=%a path=%n' "$PYTHON_REMOTE_WRAPPER"
  echo "BRAVE_PYTHON_REMOTE_WRAPPER_GATE=PASS"

  # BuildBuddy validates REAPI Command.working_directory by walking the
  # action's Merkle input tree. Siso's empty directory marker alone is not
  # enough for this BuildBuddy path; anchor the tree with the real GN args file.
  # Keep canonicalization enabled so remote action paths remain cache-stable
  # as out/x, and explicitly include ./args.gn in every remote rule.
  BRAVE_SISO_CONFIG="$SRC_DIR/build/config/siso/brave_siso_config.star"
  test -s "$BRAVE_SISO_CONFIG" || {
    echo "BRAVE_SISO_BUILDBUDDY_WORKDIR_GATE=FAIL Brave Siso config missing: $BRAVE_SISO_CONFIG" >&2
    exit 1
  }
  python3 - "$BRAVE_SISO_CONFIG" <<'PY'
from pathlib import Path
import sys

config = Path(sys.argv[1])
source = config.read_text(encoding="utf-8")
marker = '    __remove_labels_from_platforms(step_config)\n'

new_block = (
    marker
    + '\n'
    + '    # Materialize the Ninja working directory in every remote action input tree.\n'
    + '    # BuildBuddy requires Command.working_directory to exist in the REAPI Merkle tree.\n'
    + '    for rule in step_config["rules"]:\n'
    + '        if rule.get("remote", False):\n'
    + '            rule["canonicalize_dir"] = True\n'
    + '            inputs = rule.get("inputs", [])\n'
    + '            if "./args.gn" not in inputs:\n'
    + '                inputs.append("./args.gn")\n'
    + '            rule["inputs"] = inputs\n'
)

old_block = (
    marker
    + '\n'
    + '    # BuildBuddy needs the actual output-directory working path in the REAPI input tree.\n'
    + '    # Avoid Siso rewriting out/<config> to the synthetic out/x directory.\n'
    + '    for rule in step_config["rules"]:\n'
    + '        if rule.get("remote", False):\n'
    + '            rule["canonicalize_dir"] = False\n'
)

if new_block != source and '            rule["canonicalize_dir"] = True' in source and '"./args.gn"' in source:
    print("BRAVE_SISO_BUILDBUDDY_WORKDIR_GATE=PASS already configured")
elif old_block in source:
    config.write_text(source.replace(old_block, new_block, 1), encoding="utf-8")
    print("BRAVE_SISO_BUILDBUDDY_WORKDIR_GATE=PASS replaced ineffective canonicalize_dir=false workaround")
elif source.count(marker) == 1:
    config.write_text(source.replace(marker, new_block, 1), encoding="utf-8")
    print("BRAVE_SISO_BUILDBUDDY_WORKDIR_GATE=PASS added explicit ./args.gn input anchor")
else:
    raise SystemExit(
        "BRAVE_SISO_BUILDBUDDY_WORKDIR_GATE=FAIL expected one known insertion point or old workaround"
    )
PY
  grep -n -A8 -B2 'canonicalize_dir' "$BRAVE_SISO_CONFIG"
  grep -n -F '"./args.gn"' "$BRAVE_SISO_CONFIG"

  bash "$ROOT/.circleci/scripts/install-flow-host-deps.sh"

  # Re-run the pinned Chromium Siso configurator after Brave hooks with
  # Brave's native google.star backend, and persist BuildBuddy credentials.
  HELPER=/tmp/sandium-buildbuddy-credential-helper.py
  # Brave v1.98.62 sets reapi_backend_config_path=google.star in its pinned
  # build/commands/lib/config.ts. This is Chromium's pinned Siso backend file:
  # it selects the same siso-chromium worker image Chromium itself validates.
  # Do not replace it with a generic distro image or an OSFamily-only backend.
  BACKEND="$SRC_DIR/build/config/siso/backend_config/google.star"
  test -x "$HELPER" || { echo "BRAVE_RBE_CONFIG_GATE=FAIL credential helper missing: $HELPER" >&2; exit 1; }
  test -s "$BACKEND" || { echo "BRAVE_RBE_CONFIG_GATE=FAIL pinned Chromium google.star missing: $BACKEND" >&2; exit 1; }
  EXPECTED_CONTAINER_IMAGE="$(python3 - "$BACKEND" <<'PY'
import ast
import sys
from pathlib import Path

source = Path(sys.argv[1]).read_text(encoding="utf-8")
images = []
for line in source.splitlines():
    left, separator, right = line.partition("=")
    if separator and left.strip() == "container_image":
        images.append(ast.literal_eval(right.strip()))
if len(images) != 1 or not isinstance(images[0], str) or not images[0].startswith("docker://"):
    raise SystemExit(
        "expected exactly one literal docker container_image in pinned google.star; found %r"
        % images
    )
print(images[0])
PY
)"
  test -n "$EXPECTED_CONTAINER_IMAGE" || {
    echo "BRAVE_RBE_CONFIG_GATE=FAIL pinned google.star does not declare a Docker container image" >&2
    cat "$BACKEND" >&2
    exit 1
  }
  python3 "$SRC_DIR/build/config/siso/configure_siso.py" \
    --reapi_instance "$REAPI_INSTANCE" \
    --reapi_address "$REAPI_ADDRESS" \
    --reapi_backend_config_path "$BACKEND" \
    --credential-helper "$HELPER"
  SISO_BACKEND="$SRC_DIR/build/config/siso/backend_config/backend.star"
  test -s "$SISO_BACKEND" || { echo "BRAVE_RBE_CONFIG_GATE=FAIL generated Siso backend config missing" >&2; exit 1; }
  grep -Fq "$EXPECTED_CONTAINER_IMAGE" "$SISO_BACKEND" || {
    echo "BRAVE_RBE_CONFIG_GATE=FAIL generated Siso backend does not use pinned Chromium image: $EXPECTED_CONTAINER_IMAGE" >&2
    cat "$SISO_BACKEND" >&2
    exit 1
  }
  echo "BRAVE_RBE_CONTAINER_IMAGE=$EXPECTED_CONTAINER_IMAGE"
  # Brave's runhooks generated the native .sisorc immediately before this step.
  # Preserve native flags, enable the pinned Chromium remote-link rules, and
  # retain Sandium's BuildBuddy action-cache write flag.
python3 - "$SRC_DIR/build/config/siso/.sisorc" <<'PY'
from pathlib import Path
import os
import shlex
import stat
import sys
import tempfile

sisorc = Path(sys.argv[1])
if not sisorc.is_file() or sisorc.stat().st_size == 0:
    raise SystemExit("BRAVE_SISO_CONFIG_GATE=FAIL Brave-generated .sisorc is missing or empty")

original = sisorc.read_text(encoding="utf-8")
lines = original.splitlines()
ninja_indexes = [
    index for index, line in enumerate(lines)
    if line.strip() and not line.lstrip().startswith("#")
    and shlex.split(line)[0] == "ninja"
]
if len(ninja_indexes) != 1:
    raise SystemExit(
        "BRAVE_SISO_CONFIG_GATE=FAIL expected exactly one Brave-generated ninja command in .sisorc"
    )

ninja_index = ninja_indexes[0]
tokens = shlex.split(lines[ninja_index])
required = [
    ("-reapi_keep_exec_stream",),
    ("-fs_min_flush_timeout", "300s"),
    ("-reapi_byte_stream_read_threshold", "1024"),
]
for sequence in required:
    found = any(
        tokens[position:position + len(sequence)] == list(sequence)
        for position in range(len(tokens) - len(sequence) + 1)
    )
    if not found:
        raise SystemExit(
            "BRAVE_SISO_CONFIG_GATE=FAIL missing Brave native Siso flag sequence: "
            + " ".join(sequence)
        )

config_positions = [i for i, token in enumerate(tokens) if token == "-config"]
if len(config_positions) != 1 or config_positions[0] + 1 >= len(tokens):
    raise SystemExit("BRAVE_SISO_CONFIG_GATE=FAIL expected exactly one -config value")
config_index = config_positions[0] + 1
config_values = tokens[config_index].split(",")
if "googlechrome" not in config_values:
    raise SystemExit("BRAVE_SISO_CONFIG_GATE=FAIL Brave googlechrome config must be retained")
if "remote-link" not in config_values:
    config_values.append("remote-link")
    tokens[config_index] = ",".join(config_values)
    lines[ninja_index] = shlex.join(tokens)

if "-re_cache_enable_write=true" not in tokens:
    lines[ninja_index] = lines[ninja_index].rstrip() + " -re_cache_enable_write=true"

updated = "\n".join(lines) + "\n"
if updated != original:
    mode = stat.S_IMODE(sisorc.stat().st_mode)
    fd, temporary = tempfile.mkstemp(prefix=".sisorc.sandium.", dir=str(sisorc.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(updated)
        os.chmod(temporary, mode)
        os.replace(temporary, sisorc)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

print("BRAVE_SISO_NATIVE_FLAGS=PASS")
print("BRAVE_SISO_REMOTE_LINK=ENABLED")
print("BRAVE_SISO_CACHE_WRITE=PASS")
print(sisorc.read_text(encoding="utf-8"), end="")
PY

  SISO_ENV="$SRC_DIR/build/config/siso/.sisoenv"
  SISO_RC="$SRC_DIR/build/config/siso/.sisorc"
  SISO_BACKEND="$SRC_DIR/build/config/siso/backend_config/backend.star"
  test -s "$SISO_ENV" || { echo "BRAVE_RBE_CONFIG_GATE=FAIL missing $SISO_ENV" >&2; exit 1; }
  test -s "$SISO_RC" || { echo "BRAVE_RBE_CONFIG_GATE=FAIL missing $SISO_RC" >&2; exit 1; }
  test -s "$SISO_BACKEND" || { echo "BRAVE_RBE_CONFIG_GATE=FAIL missing $SISO_BACKEND" >&2; exit 1; }
  grep -Fx "SISO_REAPI_ADDRESS=$REAPI_ADDRESS" "$SISO_ENV" || { echo "BRAVE_RBE_CONFIG_GATE=FAIL wrong Siso REAPI address" >&2; cat "$SISO_ENV" >&2; exit 1; }
  grep -Fx "SISO_REAPI_INSTANCE=$REAPI_INSTANCE" "$SISO_ENV" || { echo "BRAVE_RBE_CONFIG_GATE=FAIL wrong Siso REAPI instance" >&2; cat "$SISO_ENV" >&2; exit 1; }
  grep -Fx "SISO_CREDENTIAL_HELPER=$HELPER" "$SISO_ENV" || { echo "BRAVE_RBE_CONFIG_GATE=FAIL credential helper not persisted in .sisoenv" >&2; cat "$SISO_ENV" >&2; exit 1; }
  grep -Fq -- '-re_cache_enable_write=true' "$SISO_RC" || { echo "BRAVE_RBE_CONFIG_GATE=FAIL Siso action-cache writes not enabled" >&2; cat "$SISO_RC" >&2; exit 1; }
  printf 'export SISO_REAPI_ADDRESS=%q\n' "$REAPI_ADDRESS" >> "$BASH_ENV"
  printf 'export SISO_REAPI_INSTANCE=%q\n' "$REAPI_INSTANCE" >> "$BASH_ENV"
  echo 'export SISO_LIMITS=local=8,remote=80' >> "$BASH_ENV"
  echo "BRAVE_RBE_CONFIG_GATE=PASS"
  grep -E '^(SISO_REAPI_ADDRESS|SISO_REAPI_INSTANCE|SISO_CREDENTIAL_HELPER)=' "$SISO_ENV"
  cat "$SISO_RC"

  cd "$CORE_DIR"
  if [ -s "$OUT/build.ninja" ] && [ -s "$OUT/args.gn" ]; then
    echo "BRAVE_GN_GRAPH_REUSE=PASS; existing GN graph retained."
  else
    echo "BRAVE_GN_GRAPH_REUSE=MISS; source sync skipped if source pin matched; generating GN graph."
  fi
  export SISO_LIMITS=local=8,remote=80
  echo "BRAVE_STAGE1_VALIDATION_MODE=DRY_RUN_NO_COMPILATION"
  # One fixed product recipe from 0a85, independent of branch or checkpoint maintenance.
  MINIMAL_VANILLA_BUILD=false
  ORIGIN_GN_ARGS=()
  python3 "$ROOT/.circleci/scripts/sandium-removal-recipe.py" --core "$CORE_DIR" --src "$SRC_DIR" --out "$OUT" --phase reset
  SANDIUM_REMOVAL_RESET_DONE=true
  python3 "$ROOT/.circleci/scripts/verify-sandium-vanilla-brave.py" --core "$CORE_DIR" --src "$SRC_DIR" --out "$OUT" --phase retire-reader
  python3 "$ROOT/.circleci/scripts/apply-sandium-full-overlays.py" --core "$CORE_DIR" --src "$SRC_DIR"
  python3 "$ROOT/.circleci/scripts/apply-sandium-fast-morphe.py" "$SRC_DIR"
  ORIGIN_GN_ARGS+=(
    --gn enable_brave_talk:false
    --gn enable_brave_wayback_machine:false
    --gn enable_speedreader:false
    --gn enable_tor:false
    --gn enable_web_discovery_native:false
    --gn enable_web_discovery:false
  )
  echo "SANDIUM_PRODUCT_RECIPE=0a85-plus-welcome-pref-composition-fix"
  if [ "$MINIMAL_VANILLA_BUILD" = true ]; then
    echo "BRAVE_NEWS_GN_SCOPE_GATE=SKIPPED; use unmodified upstream Brave News GN."
  else
  # GN files have isolated scopes. Brave v1.98.62 declares enable_brave_news
  # in this buildflags file, but the Android browser-test dependency file may
  # reference it without importing that declaration. Import only when needed;
  # never mask the error by inventing a local value or changing the feature flag.
  python3 - "$CORE_DIR/android/android_browser_tests.gni" "$CORE_DIR/components/brave_news/common/buildflags/buildflags.gni" <<'PY'
from pathlib import Path
import sys

target = Path(sys.argv[1])
declaration = Path(sys.argv[2])
if not target.is_file() or not declaration.is_file():
    raise SystemExit("BRAVE_NEWS_GN_SCOPE_GATE=FAIL pinned GN source/declaration file missing")
source = target.read_text(encoding="utf-8")
flags = declaration.read_text(encoding="utf-8")
if "enable_brave_news" not in flags or "declare_args()" not in flags:
    raise SystemExit("BRAVE_NEWS_GN_SCOPE_GATE=FAIL pinned Brave News GN declaration not found")
import_line = 'import("//brave/components/brave_news/common/buildflags/buildflags.gni")'
if "enable_brave_news" not in source:
    print("BRAVE_NEWS_GN_SCOPE_GATE=PASS no Brave News reference in Android test GN file")
elif import_line in source:
    print("BRAVE_NEWS_GN_SCOPE_GATE=PASS Brave News buildflags already imported")
else:
    lines = source.splitlines(keepends=True)
    # Insert after the license header and before the first executable GN statement.
    insert_at = 0
    while insert_at < len(lines) and (not lines[insert_at].strip() or lines[insert_at].lstrip().startswith("#")):
        insert_at += 1
    lines.insert(insert_at, import_line + "\n")
    updated = "".join(lines)
    if updated.count(import_line) != 1:
        raise SystemExit("BRAVE_NEWS_GN_SCOPE_GATE=FAIL import insertion verification failed")
    target.write_text(updated, encoding="utf-8")
    print("BRAVE_NEWS_GN_SCOPE_GATE=PATCHED scoped buildflags import")

verified = target.read_text(encoding="utf-8")
if "enable_brave_news" in verified and import_line not in verified:
    raise SystemExit("BRAVE_NEWS_GN_SCOPE_GATE=FAIL referenced variable remains out of scope")
print("BRAVE_NEWS_GN_SCOPE_GATE=PASS")
PY
  fi

  if [ "$MINIMAL_VANILLA_BUILD" = true ]; then
    python3 "$ROOT/.circleci/scripts/verify-sandium-vanilla-brave.py" --core "$CORE_DIR" --src "$SRC_DIR" --out "$OUT" --phase prepare
  fi

  # Reuse the pinned Vanilla Welcome GN/Ninja graph when all critical args match.
  # Any missing/stale graph or changed build-critical arg falls back to normal GN generation.
  REUSE_GN_GRAPH=false
  if [ "$SOURCE_REUSE" = true ] && [ "$MINIMAL_VANILLA_BUILD" = true ] && \
     [ -s "$OUT/build.ninja" ] && [ -s "$OUT/args.gn" ] && \
     grep -Fqx 'target_cpu = "arm64"' "$OUT/args.gn" && \
     grep -Fqx 'is_debug = false' "$OUT/args.gn" && \
     grep -Fqx 'is_java_debug = false' "$OUT/args.gn" && \
     grep -Fqx 'use_remoteexec = true' "$OUT/args.gn" && \
     grep -Fqx 'use_siso = true' "$OUT/args.gn" && \
     grep -Fqx 'use_reclient = false' "$OUT/args.gn" && \
     grep -Fqx 'enable_android_secondary_abi = false' "$OUT/args.gn" && \
     grep -Fqx 'is_official_build = false' "$OUT/args.gn" && \
     grep -Fqx 'enable_updater = false' "$OUT/args.gn" && \
     grep -Fqx 'enable_update_notifications = false' "$OUT/args.gn" && \
     grep -Fqx 'android_channel = "default"' "$OUT/args.gn" && \
     grep -Fqx 'brave_channel = "development"' "$OUT/args.gn" && \
     grep -Fqx 'chrome_public_manifest_package = "com.brave.browser_default"' "$OUT/args.gn"; then
    REUSE_GN_GRAPH=true
  fi
  if [ "$REUSE_GN_GRAPH" = true ]; then
    echo "PPBAS_GN_GRAPH_REUSE=PASS; pinned ARM64 Release graph and Siso/REAPI args already match."
  else
    echo "PPBAS_GN_GRAPH_REUSE=MISS; running pinned Brave GN generation."
    pnpm run build Release --target_os=android --target_arch=arm64 --target_android_output_format=apk --use_remoteexec=true --gn use_siso:true --gn use_reclient:false "${ORIGIN_GN_ARGS[@]}" --gn is_java_debug:false --gn enable_android_secondary_abi:false --gn is_official_build:false --gn enable_updater:false --gn enable_update_notifications:false --gn android_channel:default --gn chrome_public_manifest_package:com.brave.browser_default --gn brave_channel:development --target brave --ninja=n
  fi
  bash "$ROOT/.circleci/scripts/verify-clang-diagnostics-gn.sh"
  if [ "$MINIMAL_VANILLA_BUILD" = true ]; then
    python3 "$ROOT/.circleci/scripts/verify-sandium-vanilla-brave.py" --core "$CORE_DIR" --src "$SRC_DIR" --out "$OUT" --phase verify
  fi
fi

# Sandium native Shields/uBlock-compatible filter backport.
# This runs after source restore/preparation in every stage. It never changes pins.
SRC_DIR="$ROOT/brave-work/src"
CORE_DIR="$SRC_DIR/brave"
# Unconditional in every continuation stage; stage 1 also retires before GN.
if [ "${SANDIUM_REMOVAL_RESET_DONE:-false}" != true ]; then
  python3 "$ROOT/.circleci/scripts/sandium-removal-recipe.py" --core "$CORE_DIR" --src "$SRC_DIR" --out "$SRC_DIR/out/android_Release_arm64" --phase reset
fi
python3 "$ROOT/.circleci/scripts/verify-sandium-vanilla-brave.py" --core "$CORE_DIR" --src "$SRC_DIR" --out "$SRC_DIR/out/android_Release_arm64" --phase retire-reader
EXPECTED_BRAVE_CORE_SHA="44a84b1f89d9a35287289d6a3d493e362f5a5123"
EXPECTED_CHROMIUM_TAG="156.0.8078.74"
EXPECTED_CHROMIUM_SHA="d331de35ca8ab1358c7a17e4bd41627d55eaef51"

ACTUAL_BRAVE_TAG="$(git -C "$CORE_DIR" describe --tags --exact-match 2>/dev/null || true)"
ACTUAL_BRAVE_SHA="$(git -C "$CORE_DIR" rev-parse HEAD 2>/dev/null || true)"
ACTUAL_CHROMIUM_SHA="$(git -C "$SRC_DIR" rev-parse HEAD 2>/dev/null || true)"
ACTUAL_CHROMIUM_TAG="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["config"]["projects"]["chrome"]["tag"])' "$CORE_DIR/package.json")"

[ "$ACTUAL_BRAVE_TAG" = "v1.98.62" ] || {
  echo "SANDIUM_ADBLOCK_PIN_GATE=FAIL expected Brave v1.98.62, found $ACTUAL_BRAVE_TAG" >&2
  exit 1
}
[ "$ACTUAL_BRAVE_SHA" = "$EXPECTED_BRAVE_CORE_SHA" ] || {
  echo "SANDIUM_ADBLOCK_PIN_GATE=FAIL Brave Core SHA mismatch expected=$EXPECTED_BRAVE_CORE_SHA actual=$ACTUAL_BRAVE_SHA" >&2
  exit 1
}
[ "$ACTUAL_CHROMIUM_TAG" = "$EXPECTED_CHROMIUM_TAG" ] || {
  echo "SANDIUM_ADBLOCK_PIN_GATE=FAIL Chromium tag mismatch expected=$EXPECTED_CHROMIUM_TAG actual=$ACTUAL_CHROMIUM_TAG" >&2
  exit 1
}
[ "$ACTUAL_CHROMIUM_SHA" = "$EXPECTED_CHROMIUM_SHA" ] || {
  echo "SANDIUM_ADBLOCK_PIN_GATE=FAIL Chromium SHA mismatch expected=$EXPECTED_CHROMIUM_SHA actual=$ACTUAL_CHROMIUM_SHA" >&2
  exit 1
}

echo "SANDIUM_SOURCE_PIN_GATE=PASS brave=$ACTUAL_BRAVE_TAG brave_sha=$ACTUAL_BRAVE_SHA chromium=$ACTUAL_CHROMIUM_TAG chromium_sha=$ACTUAL_CHROMIUM_SHA"
python3 "$ROOT/.circleci/scripts/apply-sandium-filter-subscriptions.py" --core "$CORE_DIR"
