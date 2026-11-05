#!/usr/bin/env bash
# Fetch the exact Brave-required Chromium commit into the restored checkout
# with blob filtering, then let Brave sync only the remaining DEPS projects.
set -euo pipefail
SRC_DIR="${1:?usage: fetch-pinned-chromium.sh <src-dir> <tag> <sha> [url]}"
TAG="${2:?Chromium tag is required}"
EXPECTED_SHA="${3:?Chromium commit SHA is required}"
URL="${4:-https://chromium.googlesource.com/chromium/src.git}"
[[ "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "CHROMIUM_FILTERED_FETCH=FAIL invalid SHA" >&2; exit 2; }
[ -d "$SRC_DIR/.git" ] || { echo "CHROMIUM_FILTERED_FETCH=FAIL restored Chromium Git checkout missing" >&2; exit 1; }
ACTUAL_URL="$(git -C "$SRC_DIR" remote get-url origin 2>/dev/null || true)"
[ "$ACTUAL_URL" = "$URL" ] || { echo "CHROMIUM_FILTERED_FETCH=FAIL unexpected origin=$ACTUAL_URL" >&2; exit 1; }
START=$SECONDS
BEFORE="$(git -C "$SRC_DIR" count-objects -v | awk '$1 == "size-pack:" {print $2}')"
CURRENT="$(git -C "$SRC_DIR" rev-parse HEAD 2>/dev/null || true)"
echo "CHROMIUM_FILTERED_FETCH=START tag=$TAG target=$EXPECTED_SHA current=${CURRENT:-missing}"
# The separate disposable probe has already proved this endpoint supports
# blob:none and lazy hydration. Configure the real restored repo as promisor
# before fetching so missing blobs can be fetched on demand.
git -C "$SRC_DIR" config extensions.partialClone origin
git -C "$SRC_DIR" config remote.origin.promisor true
git -C "$SRC_DIR" config remote.origin.partialclonefilter blob:none
GIT_TERMINAL_PROMPT=0 git -C "$SRC_DIR" -c protocol.version=2 \
  fetch --filter=blob:none --no-tags --depth=1 origin \
  "+refs/tags/$TAG:refs/tags/$TAG"
RESOLVED="$(git -C "$SRC_DIR" rev-parse "$TAG^{commit}")"
[ "$RESOLVED" = "$EXPECTED_SHA" ] || {
  echo "CHROMIUM_FILTERED_FETCH=FAIL tag=$TAG resolved=$RESOLVED expected=$EXPECTED_SHA" >&2
  exit 1
}
git -C "$SRC_DIR" cat-file -e "$EXPECTED_SHA^{commit}"
if [ "$CURRENT" != "$EXPECTED_SHA" ]; then
  git -C "$SRC_DIR" checkout --force --detach "$EXPECTED_SHA"
fi
ACTUAL="$(git -C "$SRC_DIR" rev-parse HEAD)"
[ "$ACTUAL" = "$EXPECTED_SHA" ] || {
  echo "CHROMIUM_FILTERED_FETCH=FAIL checkout=$ACTUAL expected=$EXPECTED_SHA" >&2
  exit 1
}
PROMISOR="$(git -C "$SRC_DIR" config --get remote.origin.promisor)"
FILTER="$(git -C "$SRC_DIR" config --get remote.origin.partialclonefilter)"
[ "$PROMISOR" = true ] && [ "$FILTER" = blob:none ] || {
  echo "CHROMIUM_FILTERED_FETCH=FAIL promisor metadata was not retained" >&2
  exit 1
}
AFTER="$(git -C "$SRC_DIR" count-objects -v | awk '$1 == "size-pack:" {print $2}')"
echo "CHROMIUM_FILTERED_FETCH=PASS tag=$TAG sha=$ACTUAL filter=blob:none promisor=true pack_kib_before=${BEFORE:-0} pack_kib_after=${AFTER:-0} duration_seconds=$((SECONDS-START))"
echo "CHROMIUM_FILTERED_FETCH=GCLIENT_HANDOFF; run filtered Chromium gclient sync at the exact pin, then Brave DEPS sync"
