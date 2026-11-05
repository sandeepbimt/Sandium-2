#!/usr/bin/env python3
"""Static regression tests for verified cumulative source checkpoint reuse."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
restore = (ROOT / ".circleci/scripts/restore-brave-source-checkpoint.sh").read_text(encoding="utf-8")
config = (ROOT / ".circleci/config.yml").read_text(encoding="utf-8")

assert 'base-required)' in restore
assert 'restore_source_archive "$MANIFEST_READY"' in restore
assert 'extraction itself validates zstd' in restore
assert 'stage not in (1, 2, 3, 4, 5)' in restore
assert 'request_matches = request_id == expected_request' in restore
assert 'SOURCE_PREP_BASE=UPGRADE_PARENT' in restore
assert 'SOURCE_PREP_BASE=UPGRADE_PARENT_REQUEST_MISMATCH' in restore
assert 'restore_source_archive false' in restore
assert 'parent pin and progress request IDs disagree' in restore
assert 'ready parent Chromium HEAD differs from its pinned SHA' in restore
assert 'request_match=true' in restore
assert 'highest numbered stage' in restore
assert 'upgrade parent, never as the requested target-version checkpoint' in restore
assert 'Deliberately do NOT mark source-ready-restored or any completed phase' in restore
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
assert 'SANDIUM_PINNING_WORKFLOW=STOP' in config
assert 'exit 75' in config
assert 'source-sync-no-progress' in config
assert 'Stop after non-resumable Chromium fetch made no durable progress' in config

# The mandatory mode must not route through the legacy/fresh-bootstrap fallback.
mandatory = restore.split('  base-required)', 1)[1].split('  progress)', 1)[0]
assert 'restore_legacy_reference' not in mandatory
assert 'fresh_bootstrap' not in mandatory
assert 'exit 1' in mandatory

# The compiled checkpoint is independently useful when a source-only archive
# has not yet been promoted for a new Brave/Chromium pin. Stage 1 may bootstrap;
# later stages must verify the exact pin receipt in their restored handoff.
verifier = (ROOT / ".circleci/scripts/verify-pinned-source-reference.sh").read_text(encoding="utf-8")
assert 'PINNED_SOURCE_REFERENCE=BOOTSTRAP_REQUIRED stage=1' in verifier
assert 'PINNED_SOURCE_REFERENCE=RESTORED_AND_VERIFIED_FROM_COMPILED_HANDOFF' in verifier
assert 'PIN_REFERENCE_OUTDATED=FAIL partial independent source-ready archive restored' in verifier
assert 'actual_chromium_sha' in verifier
assert 'REFRESH_REQUEST_ID' in verifier
assert 'EXPECTED_BRAVE_CORE_SHA' in verifier
assert 'EXPECTED_CHROMIUM_SHA' in verifier
assert 'EXPECTED_BRAVE_CORE_TAG=v1.99.55' in config
assert 'EXPECTED_CHROMIUM_TAG=157.0.8103.39' in config
assert 'verify-pinned-source-reference.sh "<< parameters.stage_index >>"' in config

print("SOURCE_CHECKPOINT_RESTORE_GATE_TEST=PASS cumulative_stage1_to_5_or_promoted_ready shards=8 sha256=verified extraction=verified request_ids=recorded receipt=persisted")
