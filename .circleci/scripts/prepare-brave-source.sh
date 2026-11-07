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
old_dep = '    "//brave/browser/ai_chat",\n'
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
updated = source[:start] + block + source[end + 2:]
path.write_text(updated, encoding="utf-8")
verified = path.read_text(encoding="utf-8")
if 'if (enable_ai_chat) {\n    deps += [ "//brave/browser/ai_chat" ]\n  }' not in verified:
    raise SystemExit("SANDIUM_AI_CHAT_GN_GATE=FAIL post-write verification failed")
print("SANDIUM_AI_CHAT_GN_GATE=PASS; Android tabs_impl dependency follows enable_ai_chat")

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
if old_includes in cc_source:
    cc_source = cc_source.replace(old_includes, guarded_includes, 1)
elif guarded_includes not in cc_source:
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
if old_calls in cc_source:
    cc_source = cc_source.replace(old_calls, new_calls, 1)
elif new_calls not in cc_source:
    raise SystemExit("SANDIUM_AI_CHAT_CPP_GATE=FAIL AI Chat call block anchor mismatch")
cc.write_text(cc_source, encoding="utf-8")
verified = cc.read_text(encoding="utf-8")
if guarded_includes not in verified or new_calls not in verified:
    raise SystemExit("SANDIUM_AI_CHAT_CPP_GATE=FAIL post-write verification failed")
print("SANDIUM_AI_CHAT_CPP_GATE=PASS; Android AI Chat C++ references follow ENABLE_AI_CHAT")
PY

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
