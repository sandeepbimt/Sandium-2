#!/usr/bin/env bash
# Probe the real Chromium Git endpoint before opting the existing checkout into
# blob filtering. Unsupported servers leave the normal gclient path untouched.
set -euo pipefail
ROOT="${CIRCLE_WORKING_DIRECTORY:?CIRCLE_WORKING_DIRECTORY is required}"
WORK="${1:-$ROOT/brave-work}"
SRC="$WORK/src"
PINS="$WORK/.sandium/source-pins.env"
EVIDENCE="$WORK/.sandium/partial-clone-probe.env"
URL="https://chromium.googlesource.com/chromium/src.git"
TAG="$(sed -n 's/^CHROMIUM_TAG=//p' "$PINS" | head -n 1)"
SHA="$(sed -n 's/^CHROMIUM_SHA=//p' "$PINS" | head -n 1)"
mkdir -p "$(dirname "$EVIDENCE")"
test -n "$TAG" && [[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "CHROMIUM_PARTIAL_CLONE_PROBE=SKIP reason=missing-or-invalid-pin"
  exit 0
}
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
REPO="$TMP/probe.git"
git init --bare -q "$REPO"
git -C "$REPO" remote add origin "$URL"
echo "CHROMIUM_PARTIAL_CLONE_PROBE=START tag=$TAG sha=$SHA"
set +e
GIT_TERMINAL_PROMPT=0 git -C "$REPO" -c protocol.version=2 fetch --filter=blob:none --depth=1 --no-tags origin "refs/tags/$TAG:refs/tags/$TAG" >"$TMP/fetch.out" 2>"$TMP/fetch.err"
FETCH_RC=$?
set -e
if [ "$FETCH_RC" -ne 0 ]; then
  printf 'PARTIAL_CLONE_SUPPORTED=false\nPROBE_RESULT=FETCH_FAILED\nFETCH_EXIT=%s\n' "$FETCH_RC" > "$EVIDENCE"
  echo "CHROMIUM_PARTIAL_CLONE_PROBE=UNSUPPORTED_OR_UNAVAILABLE exit=$FETCH_RC"
  tail -n 20 "$TMP/fetch.err" || true
  exit 0
fi
PROMISOR="$(git -C "$REPO" config --get remote.origin.promisor || true)"
FILTER="$(git -C "$REPO" config --get remote.origin.partialclonefilter || true)"
EXTENSION="$(git -C "$REPO" config --get extensions.partialClone || true)"
COMMIT="$(git -C "$REPO" rev-parse "$TAG^{commit}")"
# Enumerate trees without hydrating blobs, then explicitly hydrate one real
# blob to prove that the server supports lazy object backfill as well.
BLOB="$(git -C "$REPO" ls-tree -r "$COMMIT" | awk '$2 == "blob" {print $3; exit}')"
test -n "$BLOB" || { echo "CHROMIUM_PARTIAL_CLONE_PROBE=FAIL no blob found" >&2; exit 1; }
BEFORE="$(git -C "$REPO" count-objects -v | awk '$1 == "size-pack:" {print $2}')"
git -C "$REPO" cat-file -e "$BLOB"
AFTER="$(git -C "$REPO" count-objects -v | awk '$1 == "size-pack:" {print $2}')"
if [ "$PROMISOR" != true ] || [ "$FILTER" != blob:none ] || [ "$EXTENSION" != origin ]; then
  printf 'PARTIAL_CLONE_SUPPORTED=false\nPROBE_RESULT=FILTER_NOT_RETAINED\nPROMISOR=%s\nFILTER=%s\nEXTENSION=%s\n' "$PROMISOR" "$FILTER" "$EXTENSION" > "$EVIDENCE"
  echo "CHROMIUM_PARTIAL_CLONE_PROBE=UNSUPPORTED filter_metadata_not_retained"
  exit 0
fi
if [ ! -d "$SRC/.git" ] || [ "$(git -C "$SRC" remote get-url origin 2>/dev/null || true)" != "$URL" ]; then
  printf 'PARTIAL_CLONE_SUPPORTED=true\nPROBE_RESULT=SERVER_CAPABILITY_CONFIRMED\nTAG=%s\nCOMMIT=%s\nSAMPLE_BLOB=%s\nPACK_KIB_BEFORE=%s\nPACK_KIB_AFTER=%s\n' "$TAG" "$COMMIT" "$BLOB" "$BEFORE" "$AFTER" > "$EVIDENCE"
  echo "CHROMIUM_PARTIAL_CLONE_PROBE=PASS server_supports_blob_none; existing checkout not modified"
  exit 0
fi
git -C "$SRC" config extensions.partialClone origin
git -C "$SRC" config remote.origin.promisor true
git -C "$SRC" config remote.origin.partialclonefilter blob:none
printf 'PARTIAL_CLONE_SUPPORTED=true\nPROBE_RESULT=SERVER_CAPABILITY_CONFIRMED_AND_CONFIGURED\nTAG=%s\nCOMMIT=%s\nSAMPLE_BLOB=%s\nPACK_KIB_BEFORE=%s\nPACK_KIB_AFTER=%s\n' "$TAG" "$COMMIT" "$BLOB" "$BEFORE" "$AFTER" > "$EVIDENCE"
echo "CHROMIUM_PARTIAL_CLONE_PROBE=PASS; existing origin configured for blob:none; gclient fetches may use lazy blob backfill"
