#!/usr/bin/env bash
set -euo pipefail
ROOT="$CIRCLE_WORKING_DIRECTORY"
# Sandium filter subscriptions use public list URLs; no Brave Services key is required.
NODE_DIR="$ROOT/node-runtime"
if [ ! -x "$NODE_DIR/bin/node" ]; then
  mkdir -p "$NODE_DIR"
  curl -fsSL --retry 3 https://nodejs.org/dist/v24.16.0/node-v24.16.0-linux-x64.tar.xz -o "$ROOT/node-v24.16.0.tar.xz"
  tar -xJf "$ROOT/node-v24.16.0.tar.xz" --strip-components=1 -C "$NODE_DIR"
  rm -f "$ROOT/node-v24.16.0.tar.xz"
fi
export PATH="$NODE_DIR/bin:$PATH"
npm install --global pnpm@11.11.0
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
      echo "BRAVE_SOURCE_REUSE=PASS; no portable checkpoint marker; refreshing Brave config."
      cd "$CORE_DIR"
      pnpm run sync --target_os=android --target_arch=arm64 --no-history --sync_chromium=false
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

  # Delay host-package installation until sync/configuration succeeds.
  cd "$ROOT/brave-work"
  # Keep apt indexes and downloaded .deb files in CircleCI's workspace cache.
  # The VM is fresh for every workflow, so /var/cache/apt cannot persist by itself.
  mkdir -p "$ROOT/.apt-cache/archives/partial" "$ROOT/.apt-cache/lists/partial"
  printf 'Dir::Cache::archives "%s";\nDir::State::lists "%s";\n' \
    "$ROOT/.apt-cache/archives" "$ROOT/.apt-cache/lists" \
    | sudo tee /etc/apt/apt.conf.d/99sandium-workspace-cache >/dev/null
  ./src/build/install-build-deps.sh --android

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
  MODE="$(sed -n 's/^SANDIUM_BUILD_MODE=//p' "$ROOT/brave-work/.sandium/build-mode.txt" | head -n 1)"
  ORIGIN_GN_ARGS=()
  # Keep Brave Speedreader and Playlist enabled: they are explicit Sandium exclusions.
  # Do not add enable_speedreader:false or disable Playlist here.
  if [ "$MODE" = "full" ]; then
    python3 "$ROOT/.circleci/scripts/apply-sandium-full-overlays.py" --core "$CORE_DIR" --src "$SRC_DIR"
    python3 "$ROOT/.circleci/scripts/apply-sandium-product-suppression.py" --core "$CORE_DIR"
    python3 "$ROOT/.circleci/scripts/apply-sandium-fast-morphe.py" "$SRC_DIR"
    ORIGIN_GN_ARGS+=(
      --gn enable_brave_rewards:false
      --gn enable_brave_news:false
      --gn enable_brave_vpn_v1:false
      --gn enable_brave_vpn_v2:false
      --gn enable_brave_wallet:false
      --gn enable_ai_chat:false
      --gn enable_brave_talk:false
      --gn enable_brave_wayback_machine:false
      --gn enable_tor:false
      --gn enable_web_discovery_native:false
      --gn enable_web_discovery:false
    )
    echo "SANDIUM_ORIGIN_FEATURES=DISABLED_FOR_FULL_MODE"
    echo "SANDIUM_READER_TYPOGRAPHY=INTEGRATED_FOR_FULL_MODE"
  elif [ "$MODE" = "fast" ]; then
    echo "SANDIUM_FULL_OVERLAYS=SKIPPED mode=fast"
  else
    echo "SANDIUM_BUILD_MODE_GATE=FAIL missing or invalid build-mode marker" >&2
    exit 2
  fi
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

  # Brave v1.98.62's Android tabs_impl target has an unconditional dependency
  # on //brave/browser/ai_chat even when enable_ai_chat=false. That target
  # asserts enable_ai_chat, so GN generation fails before compilation. Make
  # the dependency conditional, matching Brave's own feature-gating elsewhere.
  python3 - "$CORE_DIR/browser/android/BUILD.gn" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
source = path.read_text(encoding="utf-8")
import_line = 'import("//brave/components/ai_chat/core/common/buildflags/buildflags.gni")'
old_dep = '    "//brave/browser/ai_chat",' + chr(10)
valid_dep = '    "//brave/components/ai_chat/core/common/buildflags",' + chr(10)
malformed_dep = '    "//brave/components/ai_chat/core/common/buildflags",' + chr(92) + 'n'
new_deps = (
    '  ]\n\n'
    '  if (enable_ai_chat) {\n'
    '    deps += [ "//brave/browser/ai_chat" ]\n'
    '  }\n'
)
if import_line not in source:
    header = 'import("//brave/build/config.gni")\n'
    if source.count(header) != 1:
        raise SystemExit("SANDIUM_AI_CHAT_GN_GATE=FAIL build config import anchor not unique")
    source = source.replace(header, header + import_line + "\n", 1)

target = 'source_set("tabs_impl") {'
start = source.find(target)
if start < 0 or source.find(target, start + 1) >= 0:
    raise SystemExit("SANDIUM_AI_CHAT_GN_GATE=FAIL tabs_impl target anchor not unique")
end = source.find('\n}', start)
block = source[start:end + 2]
if old_dep in block:
    block = block.replace(old_dep, "", 1)
    deps_close = '    "//content/public/browser",\n  ]'
    if block.count(deps_close) != 1:
        raise SystemExit("SANDIUM_AI_CHAT_GN_GATE=FAIL tabs_impl deps close anchor not unique")
    block = block.replace(
        deps_close,
        '    "//content/public/browser",\n  ]\n\n'
        '  if (enable_ai_chat) {\n'
        '    deps += [ "//brave/browser/ai_chat" ]\n'
        '  }',
        1,
    )
elif 'if (enable_ai_chat)' in block and '"//brave/browser/ai_chat"' in block:
    print("SANDIUM_AI_CHAT_GN_GATE=ALREADY_PATCHED")
else:
    raise SystemExit("SANDIUM_AI_CHAT_GN_GATE=FAIL expected unconditional AI Chat dependency")
# Keep this dependency line as a real newline. chr() avoids nested escaping
# through the shell heredoc and makes the generated GN source unambiguous.
valid_dep = '    "//brave/components/ai_chat/core/common/buildflags",' + chr(10)
malformed_dep = '    "//brave/components/ai_chat/core/common/buildflags",' + chr(92) + 'n'
if malformed_dep in block:
    block = block.replace(malformed_dep, valid_dep, 1)
elif valid_dep not in block:
    tabs_public = '    ":tabs_public",' + chr(10)
    if block.count(tabs_public) != 1:
        raise SystemExit("SANDIUM_AI_CHAT_GN_GATE=FAIL tabs_public dependency anchor not unique")
    block = block.replace(tabs_public, tabs_public + valid_dep, 1)
elif block.count(valid_dep) == 1:
    print("SANDIUM_AI_CHAT_GN_GATE=ALREADY_PATCHED dependency line")
else:
    raise SystemExit("SANDIUM_AI_CHAT_GN_GATE=FAIL malformed or duplicate AI Chat buildflags dependency")

# The tabs_impl block must contain exactly one valid dependency line and no
# literal backslash-n token; this catches the previous GN parser failure.
if malformed_dep in block or block.count(valid_dep) != 1:
    raise SystemExit("SANDIUM_AI_CHAT_GN_GATE=FAIL dependency line is malformed or duplicated")
updated = source[:start] + block + source[end + 2:]
path.write_text(updated, encoding="utf-8")
verified = path.read_text(encoding="utf-8")
verified_start = verified.find(target)
verified_end = verified.find(chr(10) + "}", verified_start)
verified_block = verified[verified_start:verified_end + 2]
if malformed_dep in verified_block or verified_block.count(valid_dep) != 1:
    raise SystemExit("SANDIUM_AI_CHAT_GN_GATE=FAIL post-write dependency-line verification failed")
if 'if (enable_ai_chat) {\n    deps += [ "//brave/browser/ai_chat" ]\n  }' not in verified_block:
    raise SystemExit("SANDIUM_AI_CHAT_GN_GATE=FAIL conditional dependency verification failed")
print("SANDIUM_AI_CHAT_GN_GATE=PASS; valid GN newline and conditional Android dependency")

# The matching tabs_impl source includes and calls AI Chat helpers directly.
# Compile those pieces only when the generated ENABLE_AI_CHAT buildflag is on.
cc = path.parent / "brave_tab_features.cc"
cc_source = cc.read_text(encoding="utf-8")
include_anchor = '#include "brave/browser/ai_chat/ai_chat_utils.h"\n'
guarded_includes = (
    '#include "brave/components/ai_chat/core/common/buildflags/buildflags.h"\n'
    '\n'
    '#if BUILDFLAG(ENABLE_AI_CHAT)\n'
    '#include "brave/browser/ai_chat/ai_chat_utils.h"\n'
    '#include "brave/browser/ai_chat/tab_data_web_contents_observer.h"\n'
    '#include "brave/browser/ai_chat/web_mcp_injection/web_mcp_injector.h"\n'
    '#endif  // BUILDFLAG(ENABLE_AI_CHAT)\n'
)
old_includes = (
    '#include "brave/browser/ai_chat/ai_chat_utils.h"\n'
    '#include "brave/browser/ai_chat/tab_data_web_contents_observer.h"\n'
    '#include "brave/browser/ai_chat/web_mcp_injection/web_mcp_injector.h"\n'
)
if guarded_includes in cc_source:
    print("SANDIUM_AI_CHAT_CPP_GATE=ALREADY_PATCHED includes")
elif old_includes in cc_source:
    cc_source = cc_source.replace(old_includes, guarded_includes, 1)
else:
    raise SystemExit("SANDIUM_AI_CHAT_CPP_GATE=FAIL AI Chat include block anchor mismatch")

old_calls = (
    '  if (ai_chat::IsAllowedForContext(profile)) {\n'
    '    tab_data_observer_ = std::make_unique<ai_chat::TabDataWebContentsObserver>(\n'
    '        TabAndroid::FromWebContents(web_contents)->GetAndroidId(),\n'
    '        web_contents);\n'
    '    // Injects Brave-provided WebMCP tools into matching pages; see\n'
    '    // WebMcpInjector. Null when WebMCP is disabled or has no rules.\n'
    '    web_mcp_injector_ = ai_chat::WebMcpInjector::MaybeCreate(web_contents);\n'
    '  }\n'
)
new_calls = '#if BUILDFLAG(ENABLE_AI_CHAT)\n' + old_calls + '#endif  // BUILDFLAG(ENABLE_AI_CHAT)\n'
if new_calls in cc_source:
    print("SANDIUM_AI_CHAT_CPP_GATE=ALREADY_PATCHED calls")
elif old_calls in cc_source:
    cc_source = cc_source.replace(old_calls, new_calls, 1)
else:
    raise SystemExit("SANDIUM_AI_CHAT_CPP_GATE=FAIL AI Chat call block anchor mismatch")
cc.write_text(cc_source, encoding="utf-8")
verified = cc.read_text(encoding="utf-8")
if guarded_includes not in verified or new_calls not in verified:
    raise SystemExit("SANDIUM_AI_CHAT_CPP_GATE=FAIL post-write verification failed")
print("SANDIUM_AI_CHAT_CPP_GATE=PASS; Android AI Chat C++ references follow ENABLE_AI_CHAT")
PY

  # Brave's Android mobile-subscription renderer unconditionally links the AI
  # Chat common component for Leo purchase callbacks. With enable_ai_chat=false,
  # that pulls features.cc/pref_names.cc into the APK build and trips Brave's
  # intentional static_assert. Keep the renderer target, but compile the Leo
  # bridge and its common/mojom dependencies only when AI Chat is enabled.
  python3 - "$CORE_DIR/components/brave_mobile_subscription/renderer/android/BUILD.gn" "$CORE_DIR/components/brave_mobile_subscription/renderer/android/subscription_render_frame_observer.h" "$CORE_DIR/components/brave_mobile_subscription/renderer/android/subscription_render_frame_observer.cc" <<'PY'
from pathlib import Path
import sys

build_path, header_path, cc_path = map(Path, sys.argv[1:])
for path in (build_path, header_path, cc_path):
    if not path.is_file():
        raise SystemExit("SANDIUM_AI_CHAT_SUBSCRIPTION_GATE=FAIL pinned source missing: " + str(path))

build = build_path.read_text(encoding="utf-8")
buildflags_import = 'import("//brave/components/ai_chat/core/common/buildflags/buildflags.gni")'
if buildflags_import not in build:
    vpn_import = 'import("//brave/components/brave_vpn/common/buildflags/buildflags.gni")\n'
    if build.count(vpn_import) != 1:
        raise SystemExit("SANDIUM_AI_CHAT_SUBSCRIPTION_GATE=FAIL buildflags import anchor mismatch")
    build = build.replace(vpn_import, buildflags_import + "\n" + vpn_import, 1)

def patch_deps(source, target, label):
    start = source.find(target)
    if start < 0 or source.find(target, start + 1) >= 0:
        raise SystemExit("SANDIUM_AI_CHAT_SUBSCRIPTION_GATE=FAIL " + label + " target anchor missing or duplicated")
    end = source.find("\n}", start)
    if end < 0:
        raise SystemExit("SANDIUM_AI_CHAT_SUBSCRIPTION_GATE=FAIL " + label + " target terminator missing")
    block = source[start:end + 2]
    common = '    "//brave/components/ai_chat/core/common",\n'
    mojom = '    "//brave/components/ai_chat/core/common/mojom",\n'
    flags = '    "//brave/components/ai_chat/core/common/buildflags",\n'
    condition_start = block.find('  if (enable_ai_chat) {')
    if condition_start >= 0:
        unconditional = block[:condition_start]
        conditional_block = block[condition_start:]
        if common not in conditional_block or mojom not in conditional_block:
            raise SystemExit("SANDIUM_AI_CHAT_SUBSCRIPTION_GATE=FAIL " + label + " existing AI Chat condition is incomplete")
        unconditional = unconditional.replace(common, "").replace(mojom, "")
        block = unconditional + conditional_block
    else:
        block = block.replace(common, "").replace(mojom, "")
        conditional = (
            '\n\n  if (enable_ai_chat) {\n'
            '    deps += [\n'
            '      "//brave/components/ai_chat/core/common",\n'
            '      "//brave/components/ai_chat/core/common/mojom",\n'
            '    ]\n'
            '  }'
        )
        block = block[:-2] + conditional + '\n}'
    if flags not in block:
        base = '    "//base",\n'
        origin = '    "//brave/components/brave_origin:features",\n'
        if block.count(base) == 1:
            block = block.replace(base, base + flags, 1)
        elif block.count(origin) == 1:
            block = block.replace(origin, flags + origin, 1)
        else:
            raise SystemExit("SANDIUM_AI_CHAT_SUBSCRIPTION_GATE=FAIL " + label + " buildflags dependency anchor mismatch")
    return source[:start] + block + source[end + 2:]

build = patch_deps(build, 'source_set("android") {', "Android renderer")
build = patch_deps(build, 'source_set("browser_tests") {', "browser tests")
build_path.write_text(build, encoding="utf-8")

header = header_path.read_text(encoding="utf-8")
buildflags_header = '#include "brave/components/ai_chat/core/common/buildflags/buildflags.h"\n'
ai_includes = (
    '#include "brave/components/ai_chat/core/common/mojom/ai_chat.mojom.h"\n'
    '#include "brave/components/ai_chat/core/common/mojom/common.mojom.h"\n'
)
guarded_ai_includes = (
    buildflags_header
    + '\n#if BUILDFLAG(ENABLE_AI_CHAT)\n'
    + ai_includes
    + '#endif  // BUILDFLAG(ENABLE_AI_CHAT)\n'
)
if guarded_ai_includes not in header:
    if header.count(ai_includes) != 1:
        raise SystemExit("SANDIUM_AI_CHAT_SUBSCRIPTION_GATE=FAIL header include anchor mismatch")
    header = header.replace(ai_includes, guarded_ai_includes, 1)
member = '  mojo::Remote<ai_chat::mojom::IAPSubscription> ai_chat_subscription_;\n'
guarded_member = '#if BUILDFLAG(ENABLE_AI_CHAT)\n' + member + '#endif  // BUILDFLAG(ENABLE_AI_CHAT)\n'
if guarded_member not in header:
    if header.count(member) != 1:
        raise SystemExit("SANDIUM_AI_CHAT_SUBSCRIPTION_GATE=FAIL header member anchor mismatch")
    header = header.replace(member, guarded_member, 1)
header_path.write_text(header, encoding="utf-8")

cc = cc_path.read_text(encoding="utf-8")
features_include = '#include "brave/components/ai_chat/core/common/features.h"\n'
guarded_features = (
    buildflags_header
    + '\n#if BUILDFLAG(ENABLE_AI_CHAT)\n'
    + features_include
    + '#endif  // BUILDFLAG(ENABLE_AI_CHAT)\n'
)
if guarded_features not in cc:
    if cc.count(features_include) != 1:
        raise SystemExit("SANDIUM_AI_CHAT_SUBSCRIPTION_GATE=FAIL C++ features include anchor mismatch")
    cc = cc.replace(features_include, guarded_features, 1)

old_ensure = (
    '  if (ai_chat::features::IsAIChatEnabled() && product_ == Product::kLeo) {\n'
    '    if (!ai_chat_subscription_.is_bound()) {\n'
    '      render_frame()->GetBrowserInterfaceBroker().GetInterface(\n'
    '          ai_chat_subscription_.BindNewPipeAndPassReceiver());\n'
    '    }\n'
    '    bound |= ai_chat_subscription_.is_bound();\n'
    '  }\n'
)
guarded_ensure = '#if BUILDFLAG(ENABLE_AI_CHAT)\n' + old_ensure + '#endif  // BUILDFLAG(ENABLE_AI_CHAT)\n'
if guarded_ensure not in cc:
    if cc.count(old_ensure) != 1:
        raise SystemExit("SANDIUM_AI_CHAT_SUBSCRIPTION_GATE=FAIL EnsureConnected AI Chat block anchor mismatch")
    cc = cc.replace(old_ensure, guarded_ensure, 1)

old_leo_branch = (
    '  } else if (product_ == Product::kLeo) {\n'
    '    if (ai_chat_subscription_.is_bound()) {\n'
    '      // Inject only linkResult object on the\n'
    '      // https://account.brave.com/order-link/?product=leo page\n'
    '      // and get purchase token id only on\n'
    '      // https://account.brave.com?intent=link-order&product=leo page\n'
    '      if (page_ == Page::kResultLandingPage) {\n'
    '        AddJavaScriptObjectToFrame(context);\n'
    '      } else if (page_ == Page::kInitialLandingPage) {\n'
    '        ai_chat_subscription_->GetPurchaseTokenOrderId(base::BindOnce(\n'
    '            &SubscriptionRenderFrameObserver::OnGetPurchaseTokenOrderId,\n'
    '            weak_factory_.GetWeakPtr()));\n'
    '      }\n'
    '    }\n'
)
guarded_leo_branch = '#if BUILDFLAG(ENABLE_AI_CHAT)\n' + old_leo_branch + '#endif  // BUILDFLAG(ENABLE_AI_CHAT)\n'
if guarded_leo_branch not in cc:
    if cc.count(old_leo_branch) != 1:
        raise SystemExit("SANDIUM_AI_CHAT_SUBSCRIPTION_GATE=FAIL Leo branch anchor mismatch")
    cc = cc.replace(old_leo_branch, guarded_leo_branch, 1)

old_status = (
    '  if (product_ == Product::kLeo && ai_chat_subscription_.is_bound()) {\n'
    '    ai_chat_subscription_->SetLinkStatus(\n'
    '        status_dict.FindInt("status").value_or(0));\n'
    '  } else if (product_ == Product::kOrigin && origin_subscription_.is_bound()) {\n'
)
new_status = (
    '#if BUILDFLAG(ENABLE_AI_CHAT)\n'
    '  if (product_ == Product::kLeo && ai_chat_subscription_.is_bound()) {\n'
    '    ai_chat_subscription_->SetLinkStatus(\n'
    '        status_dict.FindInt("status").value_or(0));\n'
    '  } else\n'
    '#endif  // BUILDFLAG(ENABLE_AI_CHAT)\n'
    '  if (product_ == Product::kOrigin && origin_subscription_.is_bound()) {\n'
)
if new_status not in cc:
    if cc.count(old_status) != 1:
        raise SystemExit("SANDIUM_AI_CHAT_SUBSCRIPTION_GATE=FAIL SetLinkStatus branch anchor mismatch")
    cc = cc.replace(old_status, new_status, 1)

cc_path.write_text(cc, encoding="utf-8")

verified_build = build_path.read_text(encoding="utf-8")
verified_header = header_path.read_text(encoding="utf-8")
verified_cc = cc_path.read_text(encoding="utf-8")
for target in ('source_set("android") {', 'source_set("browser_tests") {'):
    start = verified_build.find(target)
    end = verified_build.find("\n}", start)
    block = verified_build[start:end + 2]
    if block.count('"//brave/components/ai_chat/core/common/buildflags"') != 1:
        raise SystemExit("SANDIUM_AI_CHAT_SUBSCRIPTION_GATE=FAIL missing buildflags dependency: " + target)
    if block.count('if (enable_ai_chat)') != 1 or block.count('"//brave/components/ai_chat/core/common/mojom"') != 1:
        raise SystemExit("SANDIUM_AI_CHAT_SUBSCRIPTION_GATE=FAIL common/mojom dependency is not conditional: " + target)
if ai_includes in verified_header.replace(guarded_ai_includes, "") or member in verified_header.replace(guarded_member, ""):
    raise SystemExit("SANDIUM_AI_CHAT_SUBSCRIPTION_GATE=FAIL unguarded AI Chat header/member remains")
if features_include in verified_cc.replace(guarded_features, ""):
    raise SystemExit("SANDIUM_AI_CHAT_SUBSCRIPTION_GATE=FAIL unguarded AI Chat features include remains")
if verified_cc.count('#if BUILDFLAG(ENABLE_AI_CHAT)') != 4:
    raise SystemExit("SANDIUM_AI_CHAT_SUBSCRIPTION_GATE=FAIL expected four guarded C++ blocks")
print("SANDIUM_AI_CHAT_SUBSCRIPTION_GATE=PASS; Leo bridge and common target dependencies follow ENABLE_AI_CHAT")
PY

  # Brave v1.98.62's Android preferences target unconditionally depends on
  # Brave News, even when enable_brave_news=false. The common target is omitted
  # in that configuration, so GN reports an unresolved dependency. Gate the
  # dependency and the JNI bridge's News implementation together; retain the
  # JNI surface as harmless no-op stubs while News is disabled.
  python3 - "$CORE_DIR/browser/android/preferences/BUILD.gn" "$CORE_DIR/browser/android/preferences/brave_pref_service_bridge.cc" <<'PY'
from pathlib import Path
import sys

build_path = Path(sys.argv[1])
cc_path = Path(sys.argv[2])
if not build_path.is_file() or not cc_path.is_file():
    raise SystemExit("SANDIUM_BRAVE_NEWS_ANDROID_GATE=FAIL pinned preferences source missing")

build = build_path.read_text(encoding="utf-8")
news_import = 'import("//brave/components/brave_news/common/buildflags/buildflags.gni")'
wallet_import = 'import("//brave/components/brave_wallet/common/buildflags/buildflags.gni")'
if news_import not in build:
    if build.count(wallet_import) != 1:
        raise SystemExit("SANDIUM_BRAVE_NEWS_ANDROID_GATE=FAIL preferences GN import anchor mismatch")
    build = build.replace(wallet_import, wallet_import + "\n" + news_import, 1)

target = 'source_set("preferences") {'
start = build.find(target)
if start < 0 or build.find(target, start + 1) >= 0:
    raise SystemExit("SANDIUM_BRAVE_NEWS_ANDROID_GATE=FAIL preferences target anchor not unique")
end = build.find("\n}", start)
if end < 0:
    raise SystemExit("SANDIUM_BRAVE_NEWS_ANDROID_GATE=FAIL preferences target block unterminated")
block = build[start:end + 2]
common_dep = '    "//brave/components/brave_news/common",\n'
flags_dep = '    "//brave/components/brave_news/common/buildflags",\n'
conditional_dep = '  if (enable_brave_news) {\n    deps += [ "//brave/components/brave_news/common" ]\n  }'
if common_dep in block:
    block = block.replace(common_dep, "", 1)
if flags_dep not in block:
    deps_end = '    "//brave/components/brave_rewards/core",\n'
    if block.count(deps_end) != 1:
        raise SystemExit("SANDIUM_BRAVE_NEWS_ANDROID_GATE=FAIL preferences deps insertion anchor mismatch")
    block = block.replace(deps_end, deps_end + flags_dep, 1)
if conditional_dep not in block:
    if 'if (enable_brave_news)' in block:
        raise SystemExit("SANDIUM_BRAVE_NEWS_ANDROID_GATE=FAIL unexpected existing News dependency condition")
    if not block.endswith("\n}"):
        raise SystemExit("SANDIUM_BRAVE_NEWS_ANDROID_GATE=FAIL preferences target closing brace anchor mismatch")
    block = block[:-2] + "\n\n" + conditional_dep + "\n}"
build = build[:start] + block + build[end + 2:]
build_path.write_text(build, encoding="utf-8")

cc = cc_path.read_text(encoding="utf-8")
buildflags_include = '#include "brave/components/brave_news/common/buildflags/buildflags.h"\n'
news_include = '#include "brave/components/brave_news/common/pref_names.h"\n'
guarded_news_include = buildflags_include + '#if BUILDFLAG(ENABLE_BRAVE_NEWS)\n' + news_include + '#endif  // BUILDFLAG(ENABLE_BRAVE_NEWS)\n'
if guarded_news_include not in cc:
    if cc.count(news_include) != 1:
        raise SystemExit("SANDIUM_BRAVE_NEWS_ANDROID_GATE=FAIL C++ News include anchor mismatch")
    cc = cc.replace(news_include, guarded_news_include, 1)

real_methods = (
    'void JNI_BravePrefServiceBridge_SetNewsOptIn(JNIEnv* env, jboolean value) {\n'
    '  GetOriginalProfile()->GetPrefs()->SetBoolean(\n'
    '      brave_news::prefs::kBraveNewsOptedIn, value);\n'
    '}\n\n'
    'jboolean JNI_BravePrefServiceBridge_GetNewsOptIn(JNIEnv* env) {\n'
    '  return GetOriginalProfile()->GetPrefs()->GetBoolean(\n'
    '      brave_news::prefs::kBraveNewsOptedIn);\n'
    '}\n\n'
    'void JNI_BravePrefServiceBridge_SetShowNews(JNIEnv* env, jboolean value) {\n'
    '  GetOriginalProfile()->GetPrefs()->SetBoolean(\n'
    '      brave_news::prefs::kNewTabPageShowToday, value);\n'
    '}\n\n'
    'jboolean JNI_BravePrefServiceBridge_GetShowNews(JNIEnv* env) {\n'
    '  return GetOriginalProfile()->GetPrefs()->GetBoolean(\n'
    '      brave_news::prefs::kNewTabPageShowToday);\n'
    '}'
)
stub_methods = (
    'void JNI_BravePrefServiceBridge_SetNewsOptIn(JNIEnv* env, jboolean value) {\n'
    '  (void)env;\n  (void)value;\n'
    '}\n\n'
    'jboolean JNI_BravePrefServiceBridge_GetNewsOptIn(JNIEnv* env) {\n'
    '  (void)env;\n  return false;\n'
    '}\n\n'
    'void JNI_BravePrefServiceBridge_SetShowNews(JNIEnv* env, jboolean value) {\n'
    '  (void)env;\n  (void)value;\n'
    '}\n\n'
    'jboolean JNI_BravePrefServiceBridge_GetShowNews(JNIEnv* env) {\n'
    '  (void)env;\n  return false;\n'
    '}'
)
guarded_methods = '#if BUILDFLAG(ENABLE_BRAVE_NEWS)\n' + real_methods + '\n#else  // BUILDFLAG(ENABLE_BRAVE_NEWS)\n' + stub_methods + '\n#endif  // BUILDFLAG(ENABLE_BRAVE_NEWS)'
if guarded_methods not in cc:
    if cc.count(real_methods) != 1:
        raise SystemExit("SANDIUM_BRAVE_NEWS_ANDROID_GATE=FAIL C++ News JNI method block anchor mismatch")
    cc = cc.replace(real_methods, guarded_methods, 1)

cc_path.write_text(cc, encoding="utf-8")
verified_build = build_path.read_text(encoding="utf-8")
verified_cc = cc_path.read_text(encoding="utf-8")
if common_dep in verified_build or conditional_dep not in verified_build or flags_dep not in verified_build:
    raise SystemExit("SANDIUM_BRAVE_NEWS_ANDROID_GATE=FAIL post-write GN dependency verification")
if news_include in verified_cc.replace(guarded_news_include, ""):
    raise SystemExit("SANDIUM_BRAVE_NEWS_ANDROID_GATE=FAIL unguarded News include remains")
if guarded_methods not in verified_cc or guarded_news_include not in verified_cc:
    raise SystemExit("SANDIUM_BRAVE_NEWS_ANDROID_GATE=FAIL post-write JNI verification")
print("SANDIUM_BRAVE_NEWS_ANDROID_GATE=PASS conditional GN dependency; JNI stubs retained when disabled")
PY

  # The Brave Chromium overlay is compiled into Chromium's Android feature-list
  # target. Its AI Chat and News headers contain static_asserts requiring their
  # respective buildflags, so guard both headers and the AI Chat feature-list
  # macro when Sandium intentionally disables those products.
  python3 - "$CORE_DIR/chromium_src/chrome/browser/flags/android/chrome_feature_list.cc" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
if not path.is_file():
    raise SystemExit("SANDIUM_CHROMIUM_FEATURE_LIST_GATE=FAIL overlay missing: " + str(path))
source = path.read_text(encoding="utf-8")

def replace_once(text, old, new, label):
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            "SANDIUM_CHROMIUM_FEATURE_LIST_GATE=FAIL %s anchor count=%d" % (label, count)
        )
    return text.replace(old, new, 1)

source = replace_once(
    source,
    '#include "brave/components/ai_chat/core/common/features.h"\n',
    '#include "brave/components/ai_chat/core/common/buildflags/buildflags.h"\n'
    '#if BUILDFLAG(ENABLE_AI_CHAT)\n'
    '#include "brave/components/ai_chat/core/common/features.h"\n'
    '#endif  // BUILDFLAG(ENABLE_AI_CHAT)\n',
    "AI Chat include",
)
source = replace_once(
    source,
    '#include "brave/components/brave_news/common/features.h"\n',
    '#include "brave/components/brave_news/common/buildflags/buildflags.h"\n'
    '#if BUILDFLAG(ENABLE_BRAVE_NEWS)\n'
    '#include "brave/components/brave_news/common/features.h"\n'
    '#endif  // BUILDFLAG(ENABLE_BRAVE_NEWS)\n',
    "Brave News include",
)

old_macro = (
    '// CHROMIUM_SRC_INTERNAL_USE\n'
    '#define BRAVE_AI_CHAT_FLAGS                                        \\\n'
    '  &ai_chat::features::kAIChat, &ai_chat::features::kAIChatHistory, \\\n'
    '      &ai_chat::features::kBraveSyncAIChat,\n'
)
new_macro = (
    '// CHROMIUM_SRC_INTERNAL_USE\n'
    '#if BUILDFLAG(ENABLE_AI_CHAT)\n'
    '#define BRAVE_AI_CHAT_FLAGS                                        \\\n'
    '  &ai_chat::features::kAIChat, &ai_chat::features::kAIChatHistory, \\\n'
    '      &ai_chat::features::kBraveSyncAIChat,\n'
    '#else  // BUILDFLAG(ENABLE_AI_CHAT)\n'
    '#define BRAVE_AI_CHAT_FLAGS\n'
    '#endif  // BUILDFLAG(ENABLE_AI_CHAT)\n'
)
source = replace_once(source, old_macro, new_macro, "AI Chat feature macro")

checks = {
    "AI Chat buildflags include": source.count('#include "brave/components/ai_chat/core/common/buildflags/buildflags.h"') == 1,
    "AI Chat guarded feature header": '#if BUILDFLAG(ENABLE_AI_CHAT)\n#include "brave/components/ai_chat/core/common/features.h"\n#endif  // BUILDFLAG(ENABLE_AI_CHAT)' in source,
    "News buildflags include": source.count('#include "brave/components/brave_news/common/buildflags/buildflags.h"') == 1,
    "News guarded feature header": '#if BUILDFLAG(ENABLE_BRAVE_NEWS)\n#include "brave/components/brave_news/common/features.h"\n#endif  // BUILDFLAG(ENABLE_BRAVE_NEWS)' in source,
    "AI Chat macro guarded": new_macro in source,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("SANDIUM_CHROMIUM_FEATURE_LIST_GATE=FAIL verification: " + ", ".join(failed))
path.write_text(source, encoding="utf-8")
print("SANDIUM_CHROMIUM_FEATURE_LIST_GATE=PASS; AI Chat and Brave News feature headers respect disabled buildflags")
PY

  # When Brave Wallet is disabled, the only source for this generated enum
  # srcjar disappears. Chromium's java_cpp_enum action requires >=1 input path,
  # so keep the target and its consumers consistently conditional on Wallet.
  python3 - "$CORE_DIR/android/BUILD.gn" "$CORE_DIR/browser/notifications/BUILD.gn" "$CORE_DIR/build/android/config.gni" <<'PY'
from pathlib import Path
import sys

android_path, notifications_path, config_path = map(Path, sys.argv[1:])
for path in (android_path, notifications_path, config_path):
    if not path.is_file():
        raise SystemExit("SANDIUM_BRAVE_WALLET_ENUM_GATE=FAIL pinned GN source missing: " + str(path))

def replace_once_or_already(path, old, new, label):
    source = path.read_text(encoding="utf-8")
    if new in source:
        print("SANDIUM_BRAVE_WALLET_ENUM_GATE=ALREADY_PATCHED " + label)
        return source
    if source.count(old) != 1:
        raise SystemExit("SANDIUM_BRAVE_WALLET_ENUM_GATE=FAIL " + label + " anchor missing or non-unique")
    updated = source.replace(old, new, 1)
    path.write_text(updated, encoding="utf-8")
    return updated

old_enum = '''java_cpp_enum("brave_android_java_enums_srcjar") {
  sources = []

  if (enable_brave_wallet) {
    sources += [ "//brave/components/decentralized_dns/core/constants.h" ]
  }
}'''
new_enum = '''# SANDIUM_WALLET_DNS_ENUM_COMPILE_CONTRACT_BEGIN
java_cpp_enum("brave_android_java_enums_srcjar") {
  # Compile-time enum bindings used by shared BraveActivity Java sources.
  # This does not enable Wallet or decentralized DNS runtime features.
  sources = [ "//brave/components/decentralized_dns/core/constants.h" ]
}
# SANDIUM_WALLET_DNS_ENUM_COMPILE_CONTRACT_END'''
android = replace_once_or_already(android_path, old_enum, new_enum, "Android enum target")
if 'java_cpp_enum("brave_android_java_enums_srcjar")' in android and new_enum not in android:
    raise SystemExit("SANDIUM_BRAVE_WALLET_ENUM_GATE=FAIL enum target is not wallet-conditional")

old_notifications = '''    deps += [
      "//brave/android:brave_android_java_enums_srcjar",
      "//chrome/browser:browser_process",
      "//chrome/browser:browser_public_dependencies",
    ]'''
new_notifications = old_notifications
notifications = replace_once_or_already(
    notifications_path, old_notifications, new_notifications, "Android notifications dependency"
)
if notifications.count('"//brave/android:brave_android_java_enums_srcjar"') != 1:
    raise SystemExit("SANDIUM_BRAVE_WALLET_ENUM_GATE=FAIL notifications enum dependency missing or duplicated")

old_config = '''brave_chrome_java_srcjar_deps = [
  "//brave/android:brave_android_java_enums_srcjar",
  "//brave/android:brave_config_java",
  "//brave/android:brave_policy_constants_java_srcjar",
  "//brave/components/brave_account/android:brave_account_constants_srcjar",
  "//brave/components/web_discovery/browser/android:java_pref_names_srcjar",
]'''
new_config = '''brave_chrome_java_srcjar_deps = [
  "//brave/android:brave_android_java_enums_srcjar",
  "//brave/components/brave_wallet/common:mojom",
  "//brave/android:brave_config_java",
  "//brave/android:brave_policy_constants_java_srcjar",
  "//brave/components/brave_account/android:brave_account_constants_srcjar",
  "//brave/components/web_discovery/browser/android:java_pref_names_srcjar",
]'''
config = replace_once_or_already(config_path, old_config, new_config, "Chrome Java srcjar dependency")
if old_config in config or new_config not in config:
    raise SystemExit("SANDIUM_BRAVE_WALLET_ENUM_GATE=FAIL Chrome Java srcjar compile dependencies are incomplete")

# All known consumers of this target must be conditional; no unconditional
# reference may remain in these pinned Brave GN files.
if notifications.count('"//brave/android:brave_android_java_enums_srcjar"') != 1:
    raise SystemExit("SANDIUM_BRAVE_WALLET_ENUM_GATE=FAIL notifications target reference count")
if config.count('"//brave/android:brave_android_java_enums_srcjar"') != 1:
    raise SystemExit("SANDIUM_BRAVE_WALLET_ENUM_GATE=FAIL Chrome Java srcjar reference count")
print("SANDIUM_BRAVE_WALLET_ENUM_GATE=PASS; compile-only enum and Mojo bindings retained while Wallet runtime remains disabled")
PY

  # AI Chat is intentionally disabled in Sandium. Guard the complete Android
  # tab-feature ownership path as well as Chromium feature registration:
  # forward declarations, unique_ptr members, implementation includes/code,
  # and the GN dependency must all follow ENABLE_AI_CHAT.
  python3 - "$CORE_DIR/browser/android/brave_tab_features.h" "$CORE_DIR/browser/android/brave_tab_features.cc" "$CORE_DIR/browser/android/BUILD.gn" <<'PY'
from pathlib import Path
import sys

header_path, cc_path, build_path = map(Path, sys.argv[1:])
for path in (header_path, cc_path, build_path):
    if not path.is_file():
        raise SystemExit("SANDIUM_AI_CHAT_ANDROID_GATE=FAIL missing pinned Brave source: " + str(path))

header = header_path.read_text(encoding="utf-8")
cc = cc_path.read_text(encoding="utf-8")
build = build_path.read_text(encoding="utf-8")

def replace_once(text, old, new, label):
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit("SANDIUM_AI_CHAT_ANDROID_GATE=FAIL %s anchor count=%d" % (label, count))
    return text.replace(old, new, 1)

header = replace_once(
    header,
    '#include <memory>\n',
    '#include <memory>\n\n'
    '#include "brave/components/ai_chat/core/common/buildflags/buildflags.h"\n',
    "header buildflags include",
)
old_decl = (
    'namespace ai_chat {\n'
    'class TabDataWebContentsObserver;\n'
    'class WebMcpInjector;\n'
    '}  // namespace ai_chat'
)
new_decl = (
    '#if BUILDFLAG(ENABLE_AI_CHAT)\n'
    + old_decl + '\n'
    '#endif  // BUILDFLAG(ENABLE_AI_CHAT)'
)
header = replace_once(header, old_decl, new_decl, "AI Chat forward declarations")

old_members = (
    '  std::unique_ptr<ai_chat::TabDataWebContentsObserver> tab_data_observer_;\n'
    '  std::unique_ptr<ai_chat::WebMcpInjector> web_mcp_injector_;\n'
)
new_members = (
    '#if BUILDFLAG(ENABLE_AI_CHAT)\n'
    + old_members
    + '#endif  // BUILDFLAG(ENABLE_AI_CHAT)\n'
)
header = replace_once(header, old_members, new_members, "AI Chat unique_ptr members")

cc = replace_once(
    cc,
    '#include "base/feature_list.h"\n',
    '#include "base/feature_list.h"\n'
    '#include "brave/components/ai_chat/core/common/buildflags/buildflags.h"\n',
    "implementation buildflags include",
)
ai_includes = (
    '#include "brave/browser/ai_chat/ai_chat_utils.h"\n'
    '#include "brave/browser/ai_chat/tab_data_web_contents_observer.h"\n'
    '#include "brave/browser/ai_chat/web_mcp_injection/web_mcp_injector.h"\n'
)
guarded_ai_includes = (
    '#if BUILDFLAG(ENABLE_AI_CHAT)\n'
    + ai_includes
    + '#endif  // BUILDFLAG(ENABLE_AI_CHAT)\n'
)
cc = replace_once(cc, ai_includes, guarded_ai_includes, "AI Chat implementation includes")

old_ai_block = (
    '  if (ai_chat::IsAllowedForContext(profile)) {\n'
    '    tab_data_observer_ = std::make_unique<ai_chat::TabDataWebContentsObserver>(\n'
    '        TabAndroid::FromWebContents(web_contents)->GetAndroidId(),\n'
    '        web_contents);\n'
    '    // Injects Brave-provided WebMCP tools into matching pages; see\n'
    '    // WebMcpInjector. Null when WebMCP is disabled or has no rules.\n'
    '    web_mcp_injector_ = ai_chat::WebMcpInjector::MaybeCreate(web_contents);\n'
    '  }\n'
)
guarded_ai_block = (
    '#if BUILDFLAG(ENABLE_AI_CHAT)\n'
    + old_ai_block
    + '#endif  // BUILDFLAG(ENABLE_AI_CHAT)\n'
)
cc = replace_once(cc, old_ai_block, guarded_ai_block, "AI Chat tab initialization")

build = replace_once(
    build,
    'import("//brave/components/brave_ads/buildflags/buildflags.gni")\n',
    'import("//brave/components/brave_ads/buildflags/buildflags.gni")\n'
    'import("//brave/components/ai_chat/core/common/buildflags/buildflags.gni")\n',
    "Android GN buildflags import",
)
old_public = '  public_deps = [ "//chrome/browser/android:tabs_public" ]'
new_public = (
    '  public_deps = [\n'
    '    "//brave/components/ai_chat/core/common/buildflags",\n'
    '    "//chrome/browser/android:tabs_public",\n'
    '  ]'
)
build = replace_once(build, old_public, new_public, "tabs_public buildflags dependency")
old_dep = '    "//brave/browser/ai_chat",\n'
if build.count(old_dep) == 1:
    build = build.replace(old_dep, '', 1)
elif build.count(old_dep) != 0:
    raise SystemExit("SANDIUM_AI_CHAT_ANDROID_GATE=FAIL unexpected AI Chat GN dependency count")
conditional_dep = (
    '  if (enable_ai_chat) {\n'
    '    deps += [ "//brave/browser/ai_chat" ]\n'
    '  }\n'
)
if conditional_dep not in build:
    marker = 'source_set("tabs_impl") {\n'
    if build.count(marker) != 1:
        raise SystemExit("SANDIUM_AI_CHAT_ANDROID_GATE=FAIL tabs_impl target anchor mismatch")
    # Add the conditional after the deps list, immediately before target close.
    old_tail = (
        '    "//content/public/browser",\n'
        '  ]\n'
        '}\n'
    )
    new_tail = (
        '    "//content/public/browser",\n'
        '  ]\n'
        + conditional_dep
        + '}\n'
    )
    build = replace_once(build, old_tail, new_tail, "tabs_impl conditional dependency")
    
header_path.write_text(header, encoding="utf-8")
cc_path.write_text(cc, encoding="utf-8")
build_path.write_text(build, encoding="utf-8")

# Post-write assertions make partial/incorrect guards fail before GN generation.
assert '#if BUILDFLAG(ENABLE_AI_CHAT)\nnamespace ai_chat {' in header
assert '#if BUILDFLAG(ENABLE_AI_CHAT)\n  std::unique_ptr<ai_chat::TabDataWebContentsObserver>' in header
assert guarded_ai_includes in cc and guarded_ai_block in cc
assert 'import("//brave/components/ai_chat/core/common/buildflags/buildflags.gni")' in build
assert '"//brave/components/ai_chat/core/common/buildflags"' in build
assert conditional_dep in build
assert build.count('"//brave/browser/ai_chat"') == 1
print("SANDIUM_AI_CHAT_ANDROID_GATE=PASS; disabled AI Chat no longer leaks incomplete types or unconditional GN deps")
PY

  # Retain generated API bindings only; the Wallet feature and native implementation remain disabled.
  python3 "$ROOT/.circleci/scripts/apply-sandium-wallet-java-compile-contract.py" --core "$CORE_DIR" --src "$SRC_DIR"
  GN_BIN="$SRC_DIR/buildtools/linux64/gn"
  GN_FILES=(
    "$CORE_DIR/browser/android/BUILD.gn"
    "$CORE_DIR/android/BUILD.gn"
    "$CORE_DIR/browser/notifications/BUILD.gn"
    "$CORE_DIR/build/android/config.gni"
    "$CORE_DIR/components/brave_mobile_subscription/renderer/android/BUILD.gn"
    "$CORE_DIR/components/brave_wallet/common/BUILD.gn"
    "$SRC_DIR/chrome/android/BUILD.gn"
  )
  test -x "$GN_BIN" || { echo "SANDIUM_AI_CHAT_GN_FORMAT_GATE=FAIL GN formatter missing: $GN_BIN" >&2; exit 1; }
  for GN_FILE in "${GN_FILES[@]}"; do
    test -f "$GN_FILE" || { echo "SANDIUM_AI_CHAT_GN_FORMAT_GATE=FAIL GN file missing: $GN_FILE" >&2; exit 1; }
    "$GN_BIN" format --in-place "$GN_FILE" || {
      echo "SANDIUM_AI_CHAT_GN_FORMAT_GATE=FAIL GN formatter could not parse: $GN_FILE" >&2
      exit 1
    }
    "$GN_BIN" format --dry-run "$GN_FILE" || {
      echo "SANDIUM_AI_CHAT_GN_FORMAT_GATE=FAIL GN post-format verification failed: $GN_FILE" >&2
      exit 1
    }
  done
  echo "SANDIUM_AI_CHAT_GN_FORMAT_GATE=PASS files=5 formatted=true dry_run=true"

  pnpm run build Release --target_os=android --target_arch=arm64 --target_android_output_format=apk --use_remoteexec=true --gn use_siso:true --gn use_reclient:false "${ORIGIN_GN_ARGS[@]}" --gn is_java_debug:false --gn enable_android_secondary_abi:false --gn is_official_build:false --gn enable_updater:false --gn enable_update_notifications:false --gn android_channel:default --gn chrome_public_manifest_package:com.brave.browser_default --gn brave_channel:development --target brave --ninja=n
  bash "$ROOT/.circleci/scripts/verify-clang-diagnostics-gn.sh"
fi

# Sandium native Shields/uBlock-compatible filter backport.
# This runs after source restore/preparation in every stage. It never changes pins.
SRC_DIR="$ROOT/brave-work/src"
CORE_DIR="$SRC_DIR/brave"
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

echo "SANDIUM_ADBLOCK_PIN_GATE=PASS brave=$ACTUAL_BRAVE_TAG brave_sha=$ACTUAL_BRAVE_SHA chromium=$ACTUAL_CHROMIUM_TAG chromium_sha=$ACTUAL_CHROMIUM_SHA"
python3 "$ROOT/.circleci/scripts/apply-sandium-filter-subscriptions.py" --core "$CORE_DIR"
