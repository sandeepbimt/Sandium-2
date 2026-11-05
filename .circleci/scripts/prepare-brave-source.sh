#!/usr/bin/env bash
set -euo pipefail
ROOT="$CIRCLE_WORKING_DIRECTORY"
NODE_DIR="$ROOT/node-runtime"
if [ ! -x "$NODE_DIR/bin/node" ]; then
  mkdir -p "$NODE_DIR"
  curl -fsSL --retry 3 https://nodejs.org/dist/v24.16.0/node-v24.16.0-linux-x64.tar.xz -o "$ROOT/node-v24.16.0.tar.xz"
  tar -xJf "$ROOT/node-v24.16.0.tar.xz" --strip-components=1 -C "$NODE_DIR"
  rm -f "$ROOT/node-v24.16.0.tar.xz"
fi
export npm_config_prefix="$NODE_DIR"
export PATH="$NODE_DIR/bin:$PATH"
if [ ! -x "$NODE_DIR/bin/pnpm" ] || [ "$("$NODE_DIR/bin/pnpm" --version 2>/dev/null || true)" != "11.11.0" ]; then
  npm install --global pnpm@11.11.0
fi
test "$("$NODE_DIR/bin/pnpm" --version)" = "11.11.0" || {
  echo "BRAVE_NODE_PNPM_GATE=FAIL expected pnpm 11.11.0" >&2
  exit 1
}
printf 'export PATH=%q:$PATH\n' "$NODE_DIR/bin" >> "$BASH_ENV"
printf 'export npm_config_prefix=%q\n' "$NODE_DIR" >> "$BASH_ENV"
echo "BRAVE_NODE_PNPM_CACHE=PASS node=24.16.0 pnpm=11.11.0"
mkdir -p "$ROOT/brave-work"
SRC_DIR="$ROOT/brave-work/src"
CORE_DIR="$SRC_DIR/brave"
OUT="$SRC_DIR/out/android_Release_arm64"
BRAVE_STAGE_INDEX="${BRAVE_STAGE_INDEX:?BRAVE_STAGE_INDEX is required}"
CHROMIUM_URL="https://chromium.googlesource.com/chromium/src.git"
PINS_FILE="$ROOT/brave-work/.sandium/source-pins.env"
REQUEST_ID_FILE="$ROOT/.circleci/source-pin-refresh-id"
REQUEST_ID="${SANDIUM_PINNING_REQUEST_ID:-$(tr -d '\\r\\n' < "$REQUEST_ID_FILE")}"
STORED_PIN_REQUEST_ID="$(sed -n 's/^REFRESH_REQUEST_ID=//p' "$PINS_FILE" 2>/dev/null | head -n 1 || true)"
if [ "$BRAVE_STAGE_INDEX" != "1" ]; then
  test -s "$PINS_FILE" || { echo "BRAVE_PIN_METADATA_GATE=FAIL later phase has no source-pins.env" >&2; exit 1; }
  BRAVE_CORE_TAG="$(sed -n 's/^BRAVE_CORE_TAG=//p' "$PINS_FILE" | head -n 1)"
  test -n "$BRAVE_CORE_TAG" || { echo "BRAVE_PIN_METADATA_GATE=FAIL stored Brave tag is empty" >&2; exit 1; }
  echo "BRAVE_RELEASE_PIN=RESTORED tag=$BRAVE_CORE_TAG request_id=$REQUEST_ID"
elif [ -s "$PINS_FILE" ] && [ "$STORED_PIN_REQUEST_ID" = "$REQUEST_ID" ]; then
  # Keep an in-progress request pinned to its original Brave/Chromium pair.
  # Legacy checkpoints without the request field are migrated after the
  # package's Chromium tag and both actual Git checkouts are verified.
  BRAVE_CORE_TAG="$(sed -n 's/^BRAVE_CORE_TAG=//p' "$PINS_FILE" | head -n 1)"
  test -n "$BRAVE_CORE_TAG" || { echo "BRAVE_PIN_METADATA_GATE=FAIL stored Brave tag is empty" >&2; exit 1; }
  echo "BRAVE_RELEASE_PIN=RESUME tag=$BRAVE_CORE_TAG request_id=$REQUEST_ID"
else
  # This workflow is deliberately pinned to the latest verified upstream
  # Brave Release tag. The exact Chromium revision is taken from this tag's
  # own package.json; no Sandium browser overlays are applied.
  BRAVE_CORE_TAG="v1.99.55"
  BRAVE_RELEASE_CHANNEL="RELEASE"
  echo "BRAVE_RELEASE_PIN=VANILLA_RELEASE_PINNED tag=$BRAVE_CORE_TAG channel=$BRAVE_RELEASE_CHANNEL github_prerelease_flag=true"

fi

test "$BRAVE_CORE_TAG" = "v1.99.55" || {
  echo "BRAVE_RELEASE_PIN_GATE=FAIL expected v1.99.55, got $BRAVE_CORE_TAG" >&2
  exit 1
}

# Separate dependency installation from Brave sync. A successful install is
# reusable only for the exact package, lockfile and npm-config fingerprint.
run_brave_sync() {
  local fingerprint marker install_started sync_started
  fingerprint="$(
    {
      sha256sum package.json pnpm-lock.yaml
      if [ -f .npmrc ]; then sha256sum .npmrc; fi
    } | sha256sum | awk '{print $1}'
  )"
  marker="$ROOT/brave-work/.sandium/pnpm-install-$fingerprint.ok"
  mkdir -p "$ROOT/brave-work/.sandium"

  if [ -s "$marker" ] && [ -s node_modules/.modules.yaml ] && [ -d node_modules/.pnpm ]; then
    echo "BRAVE_PNPM_DEPENDENCIES=REUSE fingerprint=$fingerprint"
  else
    install_started=$SECONDS
    echo "BRAVE_PNPM_INSTALL=START fingerprint=$fingerprint"
    pnpm install --frozen-lockfile --yes
    test -s node_modules/.modules.yaml && test -d node_modules/.pnpm || {
      echo "BRAVE_PNPM_INSTALL_GATE=FAIL node_modules layout is incomplete" >&2
      exit 1
    }
    printf '%s\n' "$fingerprint" > "$marker"
    echo "BRAVE_PNPM_INSTALL=PASS duration_seconds=$((SECONDS - install_started)) fingerprint=$fingerprint"
  fi

  sync_started=$SECONDS
  npm_package_version="$(node -p "require('./package.json').version")" node ./build/commands/scripts/sync.ts "$@"
  echo "BRAVE_UPSTREAM_SYNC_SECONDS=$((SECONDS - sync_started))"
}
if [ "$BRAVE_STAGE_INDEX" = "1" ]; then
  if [ ! -d "$CORE_DIR/.git" ]; then
    CORE_PIN_STARTED=$SECONDS
    git clone --depth 1 --branch "$BRAVE_CORE_TAG" https://github.com/brave/brave-core.git "$CORE_DIR"
    echo "BRAVE_CORE_PIN_PREP_SECONDS=$((SECONDS - CORE_PIN_STARTED)) action=clone"
  else
    LOCAL_CORE_TAG="$(git -C "$CORE_DIR" describe --tags --exact-match 2>/dev/null || true)"
    LOCAL_CORE_HEAD="$(git -C "$CORE_DIR" rev-parse HEAD 2>/dev/null || true)"
    LOCAL_CORE_TAG_SHA="$(git -C "$CORE_DIR" rev-parse "$BRAVE_CORE_TAG^{commit}" 2>/dev/null || true)"
    if [ "$LOCAL_CORE_TAG" = "$BRAVE_CORE_TAG" ] && [ -n "$LOCAL_CORE_TAG_SHA" ] && [ "$LOCAL_CORE_HEAD" = "$LOCAL_CORE_TAG_SHA" ]; then
      echo "BRAVE_CORE_PIN_REUSE=PASS tag=$BRAVE_CORE_TAG sha=$LOCAL_CORE_HEAD; fetch/checkout/clean skipped"
      echo "BRAVE_CORE_PIN_PREP_SECONDS=0 action=verified-local-reuse"
    else
      CORE_PIN_STARTED=$SECONDS
      git -C "$CORE_DIR" fetch --depth=1 origin "refs/tags/$BRAVE_CORE_TAG:refs/tags/$BRAVE_CORE_TAG"
      git -C "$CORE_DIR" checkout --force --detach "$BRAVE_CORE_TAG"
      git -C "$CORE_DIR" clean -ffd
      echo "BRAVE_CORE_PIN_PREP_SECONDS=$((SECONDS - CORE_PIN_STARTED)) action=fetch-checkout-clean"
    fi
  fi
else
  [ -d "$CORE_DIR/.git" ] || { echo "BRAVE_SOURCE_REUSE=FAIL restored Brave Core Git checkout is missing" >&2; exit 1; }
  [ "$(git -C "$CORE_DIR" describe --tags --exact-match 2>/dev/null || true)" = "$BRAVE_CORE_TAG" ] || {
    echo "BRAVE_SOURCE_REUSE=FAIL restored Brave Core tag does not match $BRAVE_CORE_TAG" >&2
    exit 1
  }
fi
cd "$CORE_DIR"
ACTUAL_BRAVE_CORE_SHA="$(git -C "$CORE_DIR" rev-parse HEAD)"
test "$ACTUAL_BRAVE_CORE_SHA" = "d5f73ccfbb8887db2367b182fa86df82c6b705cf" || {
  echo "BRAVE_CORE_SHA_GATE=FAIL expected d5f73ccfbb8887db2367b182fa86df82c6b705cf, got $ACTUAL_BRAVE_CORE_SHA" >&2
  exit 1
}
CHROMIUM_TAG="$(node -e 'console.log(JSON.parse(require("fs").readFileSync("package.json")).config.projects.chrome.tag)')"
if [ "$BRAVE_STAGE_INDEX" = "1" ]; then
  PINNED_BRAVE_TAG="$(sed -n 's/^BRAVE_CORE_TAG=//p' "$PINS_FILE" 2>/dev/null | head -n 1 || true)"
  PINNED_CHROMIUM_TAG="$(sed -n 's/^CHROMIUM_TAG=//p' "$PINS_FILE" 2>/dev/null | head -n 1 || true)"
  if [ ! -s "$PINS_FILE" ] || [ "$PINNED_BRAVE_TAG" != "$BRAVE_CORE_TAG" ] || [ "$PINNED_CHROMIUM_TAG" != "$CHROMIUM_TAG" ]; then
    # Resolve the exact commit behind the Chromium tag required by this Brave
    # release. Record it before sync so all stages and retries retain one pin.
    CHROMIUM_PIN="$(git ls-remote "$CHROMIUM_URL" "refs/tags/$CHROMIUM_TAG" "refs/tags/$CHROMIUM_TAG^{}" | awk -v ref="refs/tags/$CHROMIUM_TAG" '$2 == ref { plain=$1 } $2 == ref"^{}" { peeled=$1 } END { if (peeled != "") print peeled; else if (plain != "") print plain; else exit 1 }')"
    echo "BRAVE_CHROMIUM_REMOTE_LOOKUP=PERFORMED stage=1 tag=$CHROMIUM_TAG"
  else
    CHROMIUM_PIN="$(sed -n 's/^CHROMIUM_SHA=//p' "$PINS_FILE" | head -n 1)"
    echo "BRAVE_CHROMIUM_PIN_METADATA=RESTORED brave=$BRAVE_CORE_TAG chromium=$CHROMIUM_TAG sha=$CHROMIUM_PIN request_id=${STORED_PIN_REQUEST_ID:-legacy}"
  fi
else
  test -s "$PINS_FILE" || {
    echo "BRAVE_SOURCE_REUSE=FAIL restored source-pins.env is missing" >&2
    exit 1
  }
  PINNED_BRAVE_TAG="$(sed -n 's/^BRAVE_CORE_TAG=//p' "$PINS_FILE" | head -n 1)"
  PINNED_CHROMIUM_TAG="$(sed -n 's/^CHROMIUM_TAG=//p' "$PINS_FILE" | head -n 1)"
  CHROMIUM_PIN="$(sed -n 's/^CHROMIUM_SHA=//p' "$PINS_FILE" | head -n 1)"
  test "$PINNED_BRAVE_TAG" = "$BRAVE_CORE_TAG" || {
    echo "BRAVE_SOURCE_PIN_GATE=FAIL stored Brave tag=$PINNED_BRAVE_TAG differs from phase tag=$BRAVE_CORE_TAG" >&2
    exit 1
  }
  test "$PINNED_CHROMIUM_TAG" = "$CHROMIUM_TAG" || {
    echo "BRAVE_SOURCE_PIN_GATE=FAIL stored Chromium tag=$PINNED_CHROMIUM_TAG differs from Brave package tag=$CHROMIUM_TAG" >&2
    exit 1
  }
  echo "BRAVE_CHROMIUM_PIN_METADATA=RESTORED stage=$BRAVE_STAGE_INDEX tag=$CHROMIUM_TAG sha=$CHROMIUM_PIN"
fi
test -n "$CHROMIUM_PIN" && [ "${#CHROMIUM_PIN}" -eq 40 ] || {
  echo "BRAVE_CHROMIUM_PIN_GATE=FAIL expected a full 40-character commit SHA" >&2
  exit 1
}
CURRENT_CHROMIUM_CHECKOUT_SHA="$(git -C "$SRC_DIR" rev-parse HEAD 2>/dev/null || true)"
if [ "$CURRENT_CHROMIUM_CHECKOUT_SHA" = "$CHROMIUM_PIN" ]; then
  echo "BRAVE_CHROMIUM_CHECKOUT=TARGET sha=$CURRENT_CHROMIUM_CHECKOUT_SHA"
else
  echo "BRAVE_CHROMIUM_CHECKOUT=NEEDS_UPDATE current=${CURRENT_CHROMIUM_CHECKOUT_SHA:-missing} target=$CHROMIUM_PIN; metadata alone is not source reuse"
fi
if [ -n "${SANDIUM_PINNING_STAGE_INDEX:-}" ]; then
  echo "SANDIUM_PINNING_STAGE_INDEX=$SANDIUM_PINNING_STAGE_INDEX BRAVE_SOURCE_PHASE_INDEX=$BRAVE_STAGE_INDEX"
fi
echo "BRAVE_CORE_TAG=$BRAVE_CORE_TAG"
echo "CHROMIUM_TAG=$CHROMIUM_TAG"
echo "CHROMIUM_PIN=$CHROMIUM_PIN"
echo "BRAVE_STAGE=${BRAVE_STAGE_INDEX:?BRAVE_STAGE_INDEX is required}"
test "$CHROMIUM_TAG" = "157.0.8103.39" || {
  echo "BRAVE_CHROMIUM_TAG_GATE=FAIL expected 157.0.8103.39, got $CHROMIUM_TAG" >&2
  exit 1
}
test "$CHROMIUM_PIN" = "9a31f0acec1854d44e49a73fbf8017598151a583" || {
  echo "BRAVE_CHROMIUM_SHA_GATE=FAIL expected 9a31f0acec1854d44e49a73fbf8017598151a583, got $CHROMIUM_PIN" >&2
  exit 1
}
test "${#CHROMIUM_PIN}" -eq 40
if [ "$BRAVE_STAGE_INDEX" = "1" ]; then
  mkdir -p "$ROOT/brave-work/.sandium"
  PINS_TMP="$ROOT/brave-work/.sandium/source-pins.env.tmp"
  BRAVE_CORE_SHA="$(git -C "$CORE_DIR" rev-parse HEAD)"
  {
    echo "BRAVE_CORE_TAG=$BRAVE_CORE_TAG"
    echo "BRAVE_CORE_SHA=$BRAVE_CORE_SHA"
    echo "CHROMIUM_TAG=$CHROMIUM_TAG"
    echo "CHROMIUM_SHA=$CHROMIUM_PIN"
    echo "REFRESH_REQUEST_ID=$REQUEST_ID"
  } > "$PINS_TMP"
  mv "$PINS_TMP" "$ROOT/brave-work/.sandium/source-pins.env"
  echo "BRAVE_SOURCE_PINS=RECORDED before sync for resumable checkpointing"
fi
# Probe the actual Chromium endpoint once per refresh request. Only enable
# blob filtering after a temporary fetch proves promisor metadata and lazy
# blob hydration; unsupported endpoints retain the established full-fetch path.
PROBE_MARKER="$ROOT/brave-work/.sandium/partial-clone-probe.env"
if [ ! -s "$PROBE_MARKER" ] || ! grep -qx "TAG=$CHROMIUM_TAG" "$PROBE_MARKER"; then
  bash "$ROOT/.circleci/scripts/probe-chromium-partial-clone.sh" "$ROOT/brave-work"
  if [ -s "$PROBE_MARKER" ]; then
    PROBE_TMP="$PROBE_MARKER.tmp"
    { grep -v '^TAG=' "$PROBE_MARKER" || true; echo "TAG=$CHROMIUM_TAG"; } > "$PROBE_TMP"
    mv "$PROBE_TMP" "$PROBE_MARKER"
  fi
fi
PARTIAL_CLONE_OPT_IN="${SANDIUM_ENABLE_CHROMIUM_PARTIAL_CLONE:-false}"
CHROMIUM_ORIGIN_URL="$(git -C "$SRC" remote get-url origin 2>/dev/null || true)"
if [ -d "$SRC/.git" ] && [ "$CHROMIUM_ORIGIN_URL" = "$CHROMIUM_URL" ]; then
  if [ "$PARTIAL_CLONE_OPT_IN" = "true" ] && grep -qx 'PARTIAL_CLONE_SUPPORTED=true' "$PROBE_MARKER" 2>/dev/null; then
    git -C "$SRC" config extensions.partialClone origin
    git -C "$SRC" config remote.origin.promisor true
    git -C "$SRC" config remote.origin.partialclonefilter blob:none
    test "$(git -C "$SRC" config --get extensions.partialClone)" = origin
    test "$(git -C "$SRC" config --get remote.origin.promisor)" = true
    test "$(git -C "$SRC" config --get remote.origin.partialclonefilter)" = blob:none
    echo "BRAVE_CHROMIUM_PARTIAL_CLONE=ENABLED tag=$CHROMIUM_TAG filter=blob:none; explicit experiment opt-in verified"
  else
    # Disable filtering for a full working-tree checkout. Retain promisor
    # metadata so already-omitted objects remain eligible for lazy hydration.
    git -C "$SRC" config --unset-all remote.origin.partialclonefilter || true
    if [ "$PARTIAL_CLONE_OPT_IN" = "true" ]; then
      echo "BRAVE_CHROMIUM_PARTIAL_CLONE=DISABLED tag=$CHROMIUM_TAG reason=probe-not-supported"
    else
      echo "BRAVE_CHROMIUM_PARTIAL_CLONE=DISABLED tag=$CHROMIUM_TAG reason=full-checkout-default-no-filter"
    fi
  fi
else
  if [ "$PARTIAL_CLONE_OPT_IN" = "true" ]; then
    echo "BRAVE_CHROMIUM_PARTIAL_CLONE=DEFERRED tag=$CHROMIUM_TAG reason=source-checkout-not-created-yet"
  else
    echo "BRAVE_CHROMIUM_PARTIAL_CLONE=DISABLED tag=$CHROMIUM_TAG reason=full-checkout-default-no-filter"
  fi
fi
SOURCE_PREP_PHASE="${SANDIUM_SOURCE_PREP_PHASE:-all}"
pnpm config set store-dir "$HOME/.cache/pnpm-store"
  # Use Brave's native RBE configuration path. At v1.99.55,
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
    grep -Ev '^(rbe_service|use_remoteexec)=' "$ENV_FILE" > "$ENV_TMP" || true
  fi
  printf '%s\n' \
    "rbe_service=$REAPI_ADDRESS" \
    'use_remoteexec=true' \
    >> "$ENV_TMP"
  mv "$ENV_TMP" "$ENV_FILE"
  echo "BRAVE_RBE_ENDPOINT=$REAPI_ADDRESS"
  echo "BRAVE_RBE_INSTANCE=$REAPI_INSTANCE"
  export DEPOT_TOOLS_UPDATE=0

if [ "$BRAVE_STAGE_INDEX" = "1" ]; then
  SRC_DIR="$ROOT/brave-work/src"
  CORE_DIR="$SRC_DIR/brave"
  OUT="$SRC_DIR/out/android_Release_arm64"
  SOURCE_REUSE=false
  SOURCE_ARCHIVE_PIN_MATCH=false


  # Reuse the pinned source tree, but refresh Brave's generated Siso config.
  if [ -s "$ROOT/brave-work/.gclient" ] && [ -e "$SRC_DIR/.git" ] && \
     [ -x "$SRC_DIR/build/install-build-deps.sh" ] && \
     [ "$(git -C "$CORE_DIR" describe --tags --exact-match 2>/dev/null || true)" = "$BRAVE_CORE_TAG" ] && \
     [ "$(git -C "$SRC_DIR" rev-parse HEAD 2>/dev/null || true)" = "$CHROMIUM_PIN" ] && \
     [ -d "$SRC_DIR/third_party" ] && [ -d "$SRC_DIR/build" ]; then
    SOURCE_REUSE=true
    echo "BRAVE_SOURCE_REUSE=PASS; pinned source restored."
    echo "BRAVE_CHECKPOINT_PRESERVATION=PASS restored pinned source checkout retained."
    if [ -s "$ROOT/brave-work/.sandium/source-sync-complete" ]; then
      if [ -s "$ROOT/brave-work/.sandium/source-ready-restored" ]; then SOURCE_ARCHIVE_PIN_MATCH=true; fi
      echo "BRAVE_SOURCE_SYNC=REUSE; previous source sync is complete."
    else
      echo "BRAVE_SOURCE_REUSE=PASS; resume Chromium sync from restored source tree."
      cd "$CORE_DIR"
      if [ "$SOURCE_PREP_PHASE" = "sync" ]; then
        run_brave_sync --target_os=android --target_arch=arm64 --no-history --nohooks
      else
        run_brave_sync --target_os=android --target_arch=arm64 --no-history --sync_chromium=false
      fi
    fi
  elif [ -s "$ROOT/brave-work/.gclient" ] && \
       [ -e "$SRC_DIR/.git" ] && \
       [ -e "$CORE_DIR/.git" ] && \
       [ -x "$SRC_DIR/build/install-build-deps.sh" ] && \
       [ -d "$SRC_DIR/third_party" ] && [ -d "$SRC_DIR/build" ] && \
       [ "$(git -C "$CORE_DIR" describe --tags --exact-match 2>/dev/null || true)" = "$BRAVE_CORE_TAG" ]; then
    # SANDIUM_INCREMENTAL_SOURCE_UPGRADE: use regular sync without init/force
    # when the old Chromium checkout and its dependencies are already present.
    CURRENT_CHROMIUM_SHA="$(git -C "$SRC_DIR" rev-parse HEAD)"
    echo "BRAVE_SOURCE_INCREMENTAL_SYNC=START current=$CURRENT_CHROMIUM_SHA target_tag=$CHROMIUM_TAG target_sha=$CHROMIUM_PIN"
    if [ -d "$OUT" ]; then
      echo "BRAVE_VERSION_UPGRADE_CLEAN_OUT=START path=$OUT"
      rm -rf "$OUT"
      echo "BRAVE_VERSION_UPGRADE_CLEAN_OUT=PASS"
    fi
    cd "$CORE_DIR"
    SOURCE_SYNC_STARTED=$SECONDS
    if [ "$SOURCE_PREP_PHASE" = "sync" ]; then
      run_brave_sync --target_os=android --target_arch=arm64 --no-history --nohooks
    else
      run_brave_sync --target_os=android --target_arch=arm64 --no-history
    fi
    SOURCE_SYNC_SECONDS=$((SECONDS - SOURCE_SYNC_STARTED))
    echo "BRAVE_SOURCE_INCREMENTAL_SYNC=PASS duration_seconds=$SOURCE_SYNC_SECONDS current_before=$CURRENT_CHROMIUM_SHA target=$CHROMIUM_PIN"
  else
    echo "BRAVE_SOURCE_REUSE=MISS; no complete Chromium checkout; using one-time Brave initialization."
    if [ -d "$OUT" ]; then
      echo "BRAVE_VERSION_UPGRADE_CLEAN_OUT=START path=$OUT"
      rm -rf "$OUT"
      echo "BRAVE_VERSION_UPGRADE_CLEAN_OUT=PASS"
    fi
    cd "$CORE_DIR"
    SOURCE_INIT_STARTED=$SECONDS
    if [ "$SOURCE_PREP_PHASE" = "sync" ]; then
      run_brave_sync --init --target_os=android --target_arch=arm64 --no-history --nohooks
    else
      pnpm run init --target_os=android --target_arch=arm64 --no-history
    fi
    SOURCE_INIT_SECONDS=$((SECONDS - SOURCE_INIT_STARTED))
    echo "BRAVE_SOURCE_INITIALIZATION=COMPLETE duration_seconds=$SOURCE_INIT_SECONDS"
  fi

  ACTUAL_CHROMIUM_SHA="$(git -C "$SRC_DIR" rev-parse HEAD)"
  ACTUAL_BRAVE_TAG="$(git -C "$CORE_DIR" describe --tags --exact-match 2>/dev/null || true)"
  test "$ACTUAL_BRAVE_TAG" = "$BRAVE_CORE_TAG" || {
    echo "BRAVE_SOURCE_PIN_GATE=FAIL Brave tag expected=$BRAVE_CORE_TAG actual=${ACTUAL_BRAVE_TAG:-missing}" >&2
    exit 1
  }
  test "$ACTUAL_CHROMIUM_SHA" = "$CHROMIUM_PIN" || {
    echo "BRAVE_SOURCE_PIN_GATE=FAIL Chromium tag=$CHROMIUM_TAG expected_sha=$CHROMIUM_PIN actual=$ACTUAL_CHROMIUM_SHA" >&2
    exit 1
  }
  mkdir -p "$ROOT/brave-work/.sandium"
  # Keep the complete immutable pin receipt. Rewriting only the three
  # version fields here used to drop BRAVE_CORE_SHA and REFRESH_REQUEST_ID,
  # making later stage handoffs ambiguous and non-reproducible.
  BRAVE_CORE_SHA="$(git -C "$CORE_DIR" rev-parse HEAD)"
  PINS_TMP="$PINS_FILE.tmp"
  {
    echo "BRAVE_CORE_TAG=$BRAVE_CORE_TAG"
    echo "BRAVE_CORE_SHA=$BRAVE_CORE_SHA"
    echo "CHROMIUM_TAG=$CHROMIUM_TAG"
    echo "CHROMIUM_SHA=$ACTUAL_CHROMIUM_SHA"
    echo "REFRESH_REQUEST_ID=$REQUEST_ID"
  } > "$PINS_TMP"
  mv "$PINS_TMP" "$PINS_FILE"
  echo "BRAVE_SOURCE_PIN_GATE=PASS Brave=$ACTUAL_BRAVE_TAG Chromium=$CHROMIUM_TAG sha=$ACTUAL_CHROMIUM_SHA request_id=$REQUEST_ID"

fi

if [ "$BRAVE_STAGE_INDEX" != "1" ]; then
  ACTUAL_CHROMIUM_SHA="$(git -C "$SRC_DIR" rev-parse HEAD)"
  ACTUAL_BRAVE_TAG="$(git -C "$CORE_DIR" describe --tags --exact-match 2>/dev/null || true)"
  test "$ACTUAL_BRAVE_TAG" = "$BRAVE_CORE_TAG" || {
    echo "BRAVE_SOURCE_PIN_GATE=FAIL restored Brave tag mismatch" >&2
    exit 1
  }
  EXPECTED_BRAVE_SHA="$(sed -n 's/^BRAVE_CORE_SHA=//p' "$PINS_FILE" | head -n 1)"
  ACTUAL_BRAVE_SHA="$(git -C "$CORE_DIR" rev-parse HEAD)"
  if [ -n "$EXPECTED_BRAVE_SHA" ] && [ "$ACTUAL_BRAVE_SHA" != "$EXPECTED_BRAVE_SHA" ]; then
    echo "BRAVE_SOURCE_PIN_GATE=FAIL restored Brave SHA mismatch expected=$EXPECTED_BRAVE_SHA actual=$ACTUAL_BRAVE_SHA" >&2
    exit 1
  fi
  test "$ACTUAL_CHROMIUM_SHA" = "$CHROMIUM_PIN" || {
    echo "BRAVE_SOURCE_PIN_GATE=FAIL restored Chromium SHA mismatch expected=$CHROMIUM_PIN actual=$ACTUAL_CHROMIUM_SHA" >&2
    exit 1
  }
  test -s "$ROOT/brave-work/.sandium/source-pins.env" || {
    echo "BRAVE_SOURCE_PIN_GATE=FAIL restored source-pins.env is missing" >&2
    exit 1
  }
  grep -Fx "BRAVE_CORE_TAG=$BRAVE_CORE_TAG" "$ROOT/brave-work/.sandium/source-pins.env" >/dev/null
  grep -Fx "CHROMIUM_TAG=$CHROMIUM_TAG" "$ROOT/brave-work/.sandium/source-pins.env" >/dev/null
  grep -Fx "CHROMIUM_SHA=$ACTUAL_CHROMIUM_SHA" "$ROOT/brave-work/.sandium/source-pins.env" >/dev/null
  echo "BRAVE_SOURCE_PIN_GATE=PASS restored Brave=$ACTUAL_BRAVE_TAG Chromium=$CHROMIUM_TAG sha=$ACTUAL_CHROMIUM_SHA"
fi

if [ "$SOURCE_PREP_PHASE" = "sync" ]; then
  ACTUAL_SYNC_SHA="$(git -C "$SRC_DIR" rev-parse HEAD)"
  test "$ACTUAL_SYNC_SHA" = "$CHROMIUM_PIN" || {
    echo "BRAVE_SOURCE_PIN_GATE=FAIL sync returned before pinned Chromium SHA expected=$CHROMIUM_PIN actual=$ACTUAL_SYNC_SHA" >&2
    exit 1
  }
  mkdir -p "$ROOT/brave-work/.sandium"
  touch "$ROOT/brave-work/.sandium/source-sync-complete"
  echo "SANDIUM_SOURCE_PREP_PHASE=sync PASS; Chromium sync completed without runhooks."
  exit 0
fi

if [ "$SOURCE_PREP_PHASE" = "hooks" ]; then
  export PATH="$CORE_DIR/vendor/depot_tools:$SRC_DIR/buildtools/linux64:$PATH"
  export DEPOT_TOOLS_UPDATE=0
  cd "$ROOT/brave-work"
  test -x "$CORE_DIR/vendor/depot_tools/gclient" || {
    echo "BRAVE_GCLIENT_RUNHOOKS_GATE=FAIL pinned Brave gclient missing" >&2
    exit 1
  }
  "$CORE_DIR/vendor/depot_tools/gclient" runhooks
  mkdir -p "$ROOT/brave-work/.sandium"
  touch "$ROOT/brave-work/.sandium/source-runhooks-complete"
  echo "BRAVE_GCLIENT_RUNHOOKS=PASS"
  exit 0
fi

if [ "$SOURCE_PREP_PHASE" = "configure" ] || [ "$BRAVE_STAGE_INDEX" = "1" ]; then
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
old = """    FileUtils.write_text_file(
        (
            f'{Paths.src_dir}/buildtools/reclient_cfgs/python/'
            'python_remote_wrapper'
        ),
        ShellTemplate(python_remote_wrapper_template).substitute(template_vars),
    )"""
new = """    wrapper_path = (
        f'{Paths.src_dir}/buildtools/reclient_cfgs/python/'
        'python_remote_wrapper'
    )
    FileUtils.write_text_file(
        wrapper_path,
        ShellTemplate(python_remote_wrapper_template).substitute(template_vars),
    )
    os.chmod(wrapper_path, 0o755)"""
if old in source and source.count(old) == 1:
    source_file.write_text(source.replace(old, new, 1), encoding="utf-8")
    print("BRAVE_PYTHON_REMOTE_WRAPPER_GENERATOR_GATE=PASS patched v1.99.54 generator")
elif new in source:
    print("BRAVE_PYTHON_REMOTE_WRAPPER_GENERATOR_GATE=PASS already patched")
else:
    raise SystemExit(
        "BRAVE_PYTHON_REMOTE_WRAPPER_GENERATOR_GATE=FAIL expected the v1.99.54 "
        "generate_python_remote_wrapper write block exactly once"
    )
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

  # Host Android packages are installed by compilation jobs, not source pinning.

  # Re-run the pinned Chromium Siso configurator after Brave hooks with
  # Brave's native google.star backend, and persist BuildBuddy credentials.
  HELPER=/tmp/sandium-buildbuddy-credential-helper.py
  # Brave v1.99.54 sets reapi_backend_config_path=google.star in its pinned
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
  # retain the proven BuildBuddy action-cache write flag.
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

fi

if [ "$SOURCE_PREP_PHASE" = "gn" ] || [ "$BRAVE_STAGE_INDEX" = "1" ]; then
  cd "$CORE_DIR"
  if [ -s "$ROOT/brave-work/.sandium/source-gn-complete" ] && [ -s "$OUT/build.ninja" ] && [ -s "$OUT/args.gn" ]; then
    echo "BRAVE_GN_GRAPH_REUSE=PASS; existing GN graph retained."
  else
    echo "BRAVE_GN_GRAPH_REUSE=MISS; source sync skipped if source pin matched; generating GN graph."
  fi
  export SISO_LIMITS=local=8,remote=80
  echo "BRAVE_STAGE1_VALIDATION_MODE=DRY_RUN_NO_COMPILATION"
  # Build unmodified upstream Brave; no app overlays, package overrides or updater changes.
  pnpm run build Release --channel=release --target_os=android --target_arch=arm64 --target_android_output_format=aab --android_aab_to_apk --use_remoteexec=true --gn use_siso:true --gn use_reclient:false --gn is_java_debug:false --gn enable_android_secondary_abi:false --gn is_official_build:true --gn android_channel:stable --gn chrome_public_manifest_package:com.brave.browser --target create_dist --ninja=n
  bash "$ROOT/.circleci/scripts/verify-clang-diagnostics-gn.sh"
fi

if [ "$SOURCE_PREP_PHASE" = "final" ]; then
  echo "SANDIUM_SOURCE_PREP_PHASE=final PASS"
  exit 0
fi

if [ "$BRAVE_STAGE_INDEX" != "1" ]; then
  ACTUAL_CHROMIUM_SHA="$(git -C "$SRC_DIR" rev-parse HEAD)"
  ACTUAL_BRAVE_TAG="$(git -C "$CORE_DIR" describe --tags --exact-match 2>/dev/null || true)"
  test "$ACTUAL_BRAVE_TAG" = "$BRAVE_CORE_TAG" || {
    echo "BRAVE_SOURCE_PIN_GATE=FAIL restored Brave tag mismatch" >&2
    exit 1
  }
  test "$ACTUAL_CHROMIUM_SHA" = "$CHROMIUM_PIN" || {
    echo "BRAVE_SOURCE_PIN_GATE=FAIL restored Chromium SHA mismatch expected=$CHROMIUM_PIN actual=$ACTUAL_CHROMIUM_SHA" >&2
    exit 1
  }
  test -s "$ROOT/brave-work/.sandium/source-pins.env" || {
    echo "BRAVE_SOURCE_PIN_GATE=FAIL restored source-pins.env is missing" >&2
    exit 1
  }
  grep -Fx "BRAVE_CORE_TAG=$BRAVE_CORE_TAG" "$ROOT/brave-work/.sandium/source-pins.env" >/dev/null
  grep -Fx "CHROMIUM_TAG=$CHROMIUM_TAG" "$ROOT/brave-work/.sandium/source-pins.env" >/dev/null
  grep -Fx "CHROMIUM_SHA=$ACTUAL_CHROMIUM_SHA" "$ROOT/brave-work/.sandium/source-pins.env" >/dev/null
  echo "BRAVE_SOURCE_PIN_GATE=PASS restored Brave=$ACTUAL_BRAVE_TAG Chromium=$CHROMIUM_TAG sha=$ACTUAL_CHROMIUM_SHA"
  echo "VANILLA_BRAVE_STAGE_RESTORE=PASS stage=$BRAVE_STAGE_INDEX; no app overlays."
fi

echo "VANILLA_BRAVE_SOURCE_OVERLAYS=NONE"
