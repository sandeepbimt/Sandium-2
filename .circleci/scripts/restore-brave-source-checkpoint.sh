#!/usr/bin/env bash
set -euo pipefail

MODE="${1:?usage: restore-brave-source-checkpoint.sh <base|base-required|progress>}"
ROOT="${CIRCLE_WORKING_DIRECTORY:?CIRCLE_WORKING_DIRECTORY is required}"
WORK="$ROOT/brave-work"

fresh_bootstrap() {
  # Clear only this ephemeral runner workspace. Immutable CircleCI caches and
  # the protected canonical reference remain untouched and recoverable.
  rm -rf "$WORK" \
    "$ROOT/brave-source-checkpoint.shards" \
    "$ROOT/brave-source-checkpoint.manifest.json" \
    "$ROOT/brave-workspace-checkpoint.shards" \
    "$ROOT/brave-workspace-checkpoint.manifest.json" \
    "$ROOT/brave-workspace-checkpoint.tar.zst" \
    "$ROOT/brave-reference-ready.tar.zst"
  mkdir -p "$WORK/.sandium"
  touch "$WORK/.sandium/fresh-bootstrap-required"
  echo "SOURCE_PREP_BASE=FRESH_BOOTSTRAP_REQUIRED reason=no-valid-restorable-reference"
}

restore_source_archive() {
  local ready="$1"
  if [ ! -d "$ROOT/brave-source-checkpoint.shards" ] || [ ! -s "$ROOT/brave-source-checkpoint.manifest.json" ]; then
    return 1
  fi
  if [ "$ready" = "true" ]; then
    # restore performs manifest, SHA-256, pin, and workspace checks before
    # extracting; extraction itself validates zstd without a second full pass.
    python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" restore --root "$ROOT" --workers 8 --ready || return 1
    mkdir -p "$WORK/.sandium"
    touch "$WORK/.sandium/source-ready-restored" \
      "$WORK/.sandium/source-sync-complete" \
      "$WORK/.sandium/source-runhooks-complete" \
      "$WORK/.sandium/source-configure-complete" \
      "$WORK/.sandium/source-gn-complete"
    echo "SOURCE_PREP_BASE=PINNED_SOURCE_READY all-cumulative-stage-data-restored"
  else
    # restore performs the SHA-256 and workspace checks once before extraction;
    # tar/zstd extraction validates the compressed stream in the same pass.
    python3 "$ROOT/.circleci/scripts/sandium-source-shards.py" restore --root "$ROOT" --workers 8 || return 1
    mkdir -p "$WORK/.sandium"
    echo "SOURCE_PREP_BASE=VALID_PROGRESS_CHECKPOINT all-cumulative-stage-data-restored"
  fi
  return 0
}


write_restore_receipt() {
  local mode="$1"
  python3 - "$ROOT" "$mode" <<'PY'
import json, sys
from pathlib import Path

root = Path(sys.argv[1])
mode = sys.argv[2]
manifest_path = root / "brave-source-checkpoint.manifest.json"
request_path = root / ".circleci" / "source-pin-refresh-id"
payload = json.loads(manifest_path.read_text(encoding="utf-8"))
source = payload.get("source", {})
shards = payload.get("shards", [])
expected_request = request_path.read_text(encoding="utf-8").strip()
request_id = str(source.get("refresh_request_id", "")).strip()
archive_bytes = int(payload.get("archive_bytes", -1))
source_bytes = int(payload.get("source_bytes", -1))
stage = int(payload.get("stage", -1))
ready = payload.get("ready")
shard_bytes = sum(int(item.get("size_bytes", -1)) for item in shards)

if not request_id:
    raise SystemExit("SOURCE_RESTORE_GATE=FAIL manifest refresh_request_id is missing")
if archive_bytes < 0 or shard_bytes != archive_bytes:
    raise SystemExit("SOURCE_RESTORE_GATE=FAIL manifest archive_bytes does not equal shard size sum")
if mode == "base-required":
    import re
    # CircleCI prefix cache lookup can return a valid prior-release checkpoint
    # when no archive exists for the new refresh request. Treat that archive as
    # an upgrade parent, never as the requested target-version checkpoint.
    if stage not in (1, 2, 3, 4, 5):
        raise SystemExit("SOURCE_RESTORE_GATE=FAIL progress checkpoint stage must be 1..5; got stage=%s" % stage)
    if ready is not True and ready is not False:
        raise SystemExit("SOURCE_RESTORE_GATE=FAIL manifest ready flag is invalid")
    if len(shards) != 8:
        raise SystemExit("SOURCE_RESTORE_GATE=FAIL expected 8 verified shards; got %d" % len(shards))
    if source_bytes < 50_000_000_000 or archive_bytes < 30_000_000_000:
        raise SystemExit("SOURCE_RESTORE_GATE=FAIL checkpoint is smaller than the known 50GB source / 30GB archive baseline")
    brave_tag = str(payload.get("source", {}).get("brave_core_tag", ""))
    brave_sha = str(payload.get("source", {}).get("brave_core_sha", ""))
    chromium_tag = str(payload.get("source", {}).get("chromium_tag", ""))
    chromium_sha = str(payload.get("source", {}).get("chromium_sha", ""))
    actual_chromium_sha = str(payload.get("source", {}).get("actual_chromium_sha", ""))
    pin_request_id = str(payload.get("source", {}).get("pin_refresh_request_id", ""))
    if not re.fullmatch(r"v[0-9]+[.][0-9]+[.][0-9]+", brave_tag):
        raise SystemExit("SOURCE_RESTORE_GATE=FAIL parent Brave tag is not a stable release")
    if not re.fullmatch(r"[0-9a-f]{40}", brave_sha):
        raise SystemExit("SOURCE_RESTORE_GATE=FAIL parent Brave Core SHA is invalid")
    if not re.fullmatch(r"[0-9]+[.][0-9]+[.][0-9]+[.][0-9]+", chromium_tag):
        raise SystemExit("SOURCE_RESTORE_GATE=FAIL parent Chromium tag is invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", chromium_sha) or not re.fullmatch(r"[0-9a-f]{40}", actual_chromium_sha):
        raise SystemExit("SOURCE_RESTORE_GATE=FAIL parent Chromium SHA metadata is invalid")
    if pin_request_id and pin_request_id != request_id:
        raise SystemExit("SOURCE_RESTORE_GATE=FAIL parent pin and progress request IDs disagree")
    if ready is True and actual_chromium_sha != chromium_sha:
        raise SystemExit("SOURCE_RESTORE_GATE=FAIL ready parent Chromium HEAD differs from its pinned SHA")
    request_matches = request_id == expected_request
    if request_matches:
        print("SOURCE_RESTORE_GATE=PASS prior_stage=%d ready=%s shards=8 source_bytes=%d archive_bytes=%d request_match=true request=%s" %
              (stage, str(ready).lower(), source_bytes, archive_bytes, request_id))
    else:
        print("SOURCE_PREP_BASE=UPGRADE_PARENT prior_stage=%d ready=%s parent_brave=%s parent_chromium=%s parent_request=%s target_request=%s; verified old source will be incrementally upgraded, not treated as target-ready" %
              (stage, str(ready).lower(), brave_tag, chromium_tag, request_id, expected_request))
else:
    print("SOURCE_RESTORE_GATE=PASS mode=%s parent_stage=%s shards=%d source_bytes=%d archive_bytes=%d request=%s" %
          (mode, stage, len(shards), source_bytes, archive_bytes, request_id))

status = root / "pinning-status"
status.mkdir(parents=True, exist_ok=True)
lines = [
    "RESTORE_RESULT=PASS",
    "RESTORE_MODE=" + mode,
    "MANIFEST_STAGE=" + str(stage),
    "MANIFEST_READY=" + str(ready).lower(),
    "SHARD_COUNT=" + str(len(shards)),
    "SOURCE_BYTES=" + str(source_bytes),
    "ARCHIVE_BYTES=" + str(archive_bytes),
    "RESTORED_REFRESH_REQUEST_ID=" + request_id,
    "REQUESTED_REFRESH_REQUEST_ID=" + expected_request,
]
for index, item in enumerate(sorted(shards, key=lambda x: x["name"]), 1):
    lines.extend([
        "SHARD_%d_NAME=%s" % (index, item["name"]),
        "SHARD_%d_BYTES=%s" % (index, item["size_bytes"]),
        "SHARD_%d_SHA256=%s" % (index, item["sha256"]),
    ])
receipt = status / "source-restore-receipt.env"
tmp = receipt.with_suffix(".env.tmp")
tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
tmp.replace(receipt)
print("SOURCE_RESTORE_RECEIPT=WRITTEN path=%s" % receipt)
PY
}

restore_legacy_reference() {
  if { [ -d "$ROOT/brave-workspace-checkpoint.shards" ] && [ -s "$ROOT/brave-workspace-checkpoint.manifest.json" ]; } || \
     [ -s "$ROOT/brave-workspace-checkpoint.tar.zst" ] || [ -s "$ROOT/brave-reference-ready.tar.zst" ]; then
    echo "SOURCE_PREP_BASE=TRY_LEGACY_FULL_WORKSPACE_REFERENCE"
    export BRAVE_STAGE_INDEX=1
    export SANDIUM_ARCHIVE_WORKERS=8
    if bash "$ROOT/.circleci/scripts/archive-brave-workspace.sh" restore; then
      mkdir -p "$WORK/.sandium"
      echo "SOURCE_PREP_BASE=LEGACY_FULL_WORKSPACE_RESTORED"
      return 0
    fi
  fi
  return 1
}

case "$MODE" in
  base)
    if [ -s "$ROOT/brave-source-checkpoint.manifest.json" ]; then
      if MANIFEST_READY="$(python3 -c 'import json,sys; print("true" if json.load(open(sys.argv[1],encoding="utf-8")).get("ready") is True else "false")' "$ROOT/brave-source-checkpoint.manifest.json" 2>/dev/null)"; then
        :
      else
        MANIFEST_READY=invalid
      fi
    else
      MANIFEST_READY=missing
    fi

    if [ "$MANIFEST_READY" = "true" ]; then
      # A ready-marked archive that fails ready validation is corrupt or stale;
      # never downgrade it to an ordinary progress checkpoint.
      if ! restore_source_archive true; then
        if ! restore_legacy_reference; then fresh_bootstrap; fi
      fi
    elif [ "$MANIFEST_READY" = "false" ]; then
      if ! restore_source_archive false; then
        if ! restore_legacy_reference; then fresh_bootstrap; fi
      fi
    else
      if ! restore_legacy_reference; then fresh_bootstrap; fi
    fi
    ;;
  base-required)
    # A previously established Stage 5 checkpoint is now mandatory. Never
    # silently replace a cache miss/corrupt archive with an expensive fresh sync.
    if [ ! -s "$ROOT/brave-source-checkpoint.manifest.json" ] || [ ! -d "$ROOT/brave-source-checkpoint.shards" ]; then
      echo "SOURCE_RESTORE_GATE=FAIL expected prior Stage 5 checkpoint was not restored from CircleCI cache" >&2
      exit 1
    fi
    MANIFEST_READY="$(python3 -c 'import json,sys; print("true" if json.load(open(sys.argv[1],encoding="utf-8")).get("ready") is True else "false")' "$ROOT/brave-source-checkpoint.manifest.json")"
    EXPECTED_REQUEST="$(tr -d '\\r\\n' < "$ROOT/.circleci/source-pin-refresh-id")"
    RESTORED_REQUEST="$(python3 -c 'import json,sys; print(str(json.load(open(sys.argv[1],encoding="utf-8")).get("source",{}).get("refresh_request_id","")).strip())' "$ROOT/brave-source-checkpoint.manifest.json")"
    if [ "$RESTORED_REQUEST" = "$EXPECTED_REQUEST" ]; then
      # Same request: preserve ready-vs-progress semantics exactly.
      if ! restore_source_archive "$MANIFEST_READY"; then
        echo "SOURCE_RESTORE_GATE=FAIL matching-request checkpoint failed SHA/workspace/decompression verification" >&2
        exit 1
      fi
    else
      # Different request: restore the prior archive only as an upgrade parent.
      # Deliberately do NOT mark source-ready-restored or any completed phase;
      # Stage 1 must re-pin Brave/Chromium and run the incremental upgrade.
      echo "SOURCE_PREP_BASE=UPGRADE_PARENT_REQUEST_MISMATCH restored=$RESTORED_REQUEST requested=$EXPECTED_REQUEST"
      if ! restore_source_archive false; then
        echo "SOURCE_RESTORE_GATE=FAIL prior upgrade-parent checkpoint failed SHA/workspace/decompression verification" >&2
        exit 1
      fi
    fi
    write_restore_receipt base-required
    if [ "$RESTORED_REQUEST" != "$EXPECTED_REQUEST" ]; then
      echo "SOURCE_RESTORE_GATE=PASS checkpoint_role=verified-upgrade-parent restored_request=$RESTORED_REQUEST target_request=$EXPECTED_REQUEST"
    else
      echo "SOURCE_RESTORE_GATE=PASS checkpoint_role=matching-request restored_request=$RESTORED_REQUEST"
    fi
    ;;
  progress)
    if ! restore_source_archive false; then
      echo "SOURCE_PREP_PROGRESS=FAIL prior-stage cumulative checkpoint is missing or invalid" >&2
      exit 1
    fi
    echo "SOURCE_PREP_PROGRESS=RESTORED"
    write_restore_receipt progress
    ;;
  *)
    echo "SOURCE_PREP_RESTORE=FAIL invalid mode=$MODE" >&2
    exit 2
    ;;
esac

mkdir -p "$WORK/.sandium"
touch "$WORK/.sandium/workspace-checkpoint-restored"
echo "SOURCE_PREP_RESTORE=PASS mode=$MODE"
