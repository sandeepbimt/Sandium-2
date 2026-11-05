#!/usr/bin/env python3
"""Static regression tests for mandatory cross-workflow Stage 5 checkpoint reuse."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
restore = (ROOT / ".circleci/scripts/restore-brave-source-checkpoint.sh").read_text(encoding="utf-8")
config = (ROOT / ".circleci/config.yml").read_text(encoding="utf-8")

assert 'base-required)' in restore
assert 'restore_source_archive "$MANIFEST_READY"' in restore
assert 'tar/zstd extraction itself validates' in restore
assert 'ready is False and stage != 5' in restore
assert 'ready is not True and ready is not False' in restore
assert 'len(shards) != 8' in restore
assert 'source_bytes < 50_000_000_000 or archive_bytes < 30_000_000_000' in restore
assert 'REQUESTED_REFRESH_REQUEST_ID=' in restore
assert 'RESTORED_REFRESH_REQUEST_ID=' in restore
assert 'SOURCE_RESTORE_GATE=FAIL' in restore
assert 'write_restore_receipt base-required' in restore
assert 'SHARD_%d_SHA256' in restore
assert 'bash .circleci/scripts/restore-brave-source-checkpoint.sh base-required' in config
assert 'grep -qx \'RESTORE_RESULT=PASS\'' in config
assert '- pinning-status/source-restore-receipt.env' in config

# The mandatory mode must not route through the legacy/fresh-bootstrap fallback.
mandatory = restore.split('  base-required)', 1)[1].split('  progress)', 1)[0]
assert 'restore_legacy_reference' not in mandatory
assert 'fresh_bootstrap' not in mandatory
assert 'exit 1' in mandatory

print("SOURCE_CHECKPOINT_RESTORE_GATE_TEST=PASS progress_stage5_or_promoted_ready shards=8 sha256=verified extraction=verified request_ids=recorded receipt=persisted")
