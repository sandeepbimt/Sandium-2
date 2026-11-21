"""Verify exact #1396 admission and both effective Full job shapes."""
import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import ci_restore_only as policy
from generate_full_config import generate

FIXTURE = ROOT / 'tests/fixtures/restore-only-1396'


class RestoreOnly(unittest.TestCase):
    def test_default_full_and_other_workflows_unchanged(self):
        old = generate(restore_only=False)
        new = generate(signed_test=False)
        self.assertEqual({'type': 'boolean', 'default': False},
                         new['parameters'].pop('raw_full_restore_only'))
        stage1 = new['jobs']['raws-full-stage-1']['steps']
        disabled = stage1[:-2] + stage1[-2]['unless']['steps']
        self.assertEqual(old['jobs']['raws-full-stage-1']['steps'], disabled)
        new['jobs']['raws-full-stage-1']['steps'] = disabled
        group = new['job-groups']['raws-full-chain']['jobs']
        for job in group[1:]:
            invocation = next(iter(job.values()))
            self.assertEqual('pipeline.git.branch == "raw-sandium/official158" '
                             'and not pipeline.parameters.raw_full_restore_only',
                             invocation['filters'])
            invocation['filters'] = {'branches': {'only': 'raw-sandium/official158'}}
        self.assertEqual(old, new)

    def test_enabled_full_has_exact_read_only_transport_and_no_save_steps(self):
        steps = generate()['jobs']['raws-full-stage-1']['steps'][-1]['when']['steps']
        self.assertEqual([[policy.RECEIPT_CACHE], [policy.BASE_CACHE]],
                         [step['restore_cache']['keys'] for step in steps
                          if 'restore_cache' in step])
        self.assertEqual(1, sum('store_artifacts' in step for step in steps))
        text = json.dumps(steps)
        for bad in ('save_cache', 'restore-layer', 'ci_source.py', 'ci_full.py begin',
                    'ci_full.py capture', 'ci_full.py publish', 'halt-complete'):
            self.assertNotIn(bad, text)
        for before, after in (('select', 'restore-base'), ('restore-finish', 'ci_restore_only.py compile'),
                              ('ci_restore_only.py compile', 'completed')):
            self.assertLess(text.index(before), text.index(after))

    def test_frozen_receipt_matches_real_validator_and_native_cache_keys(self):
        identity = policy.fingerprint()
        self.assertEqual(policy.FINGERPRINT, identity)
        receipt = (FIXTURE / 'receipt.json').read_bytes()
        payload = json.loads(receipt)['payload']
        hash_key = lambda data: base64.b64encode(hashlib.sha256(data).digest()).decode()
        self.assertEqual(policy.RECEIPT_SHA, hashlib.sha256(receipt).hexdigest())
        self.assertEqual(policy.RECEIPT_CACHE, 'raws-final-receipt-v1-' + hash_key(receipt))
        self.assertEqual(policy.BASE_CACHE,
                         'raws-final-base-v1-' + hash_key(payload['plan']['base']['key'].encode()))
        with patch.dict(os.environ, {'RAWS_PIPELINE_NUMBER': '1500',
                                     'RAWS_CHECKPOINT_SCOPE': 'raws-full-v1-' + identity}), \
                patch.object(policy.full.D.time, 'time', return_value=1795800000):
            self.assertEqual(payload, policy.check_receipt(json.loads(receipt)))
            with patch.object(policy.full.D.time, 'time', return_value=1796300000):
                with self.assertRaisesRegex(ValueError, 'Expired'):
                    policy.check_receipt(json.loads(receipt))

    def test_exact_checkpoint_only_and_no_completion_short_circuit(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(policy, 'gate'), \
                patch.object(policy, 'FINAL', Path(directory)), \
                patch.object(policy, 'check_receipt'), \
                patch.object(policy.full.D, 'select') as select:
            with self.assertRaisesRegex(ValueError, 'missing or changed'):
                policy.select()
            select.assert_not_called()
            path = policy.FINAL / 'receipt.json'
            path.write_bytes((FIXTURE / 'receipt.json').read_bytes())
            (policy.FINAL / 'archived-apk-proof.json').write_bytes(
                (FIXTURE / 'archived-apk-proof.json').read_bytes())
            previous = policy.full.D.HEAD
            policy.select()
            select.assert_called_once_with(precheck=True)
            self.assertEqual(previous, policy.full.D.HEAD)
            path.write_bytes(path.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'missing or changed'):
                policy.select()

    def test_missing_or_mismatched_current_restore_proof_fails_before_compile(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(policy, 'gate'), \
                patch.object(policy.full, 'ROOT', Path(directory)), \
                patch.object(policy.full.D, 'STATE', Path(directory) / 'state'), \
                patch.dict(os.environ, {'RAWS_PIPELINE_NUMBER': '1500',
                                        'RAWS_CHECKPOINT_SCOPE': 'raws-full-v1-' + policy.FINGERPRINT}), \
                patch.object(policy.full.D.time, 'time', return_value=1795800000):
            root = policy.full.ROOT
            policy.full.D.STATE.mkdir()
            (policy.full.D.STATE / 'selected.json').write_bytes((FIXTURE / 'receipt.json').read_bytes())
            proof = policy.full.D.STATE / 'restored-proof.json'
            proof.write_text(json.dumps({'receipt': policy.RECEIPT_ID, 'head': 'wrong'}))
            with self.assertRaisesRegex(ValueError, 'Exact completed archive restore proof'):
                policy.restored()
            proof.write_text(json.dumps({'receipt': policy.RECEIPT_ID, 'head': policy.BASE_ID}))
            with self.assertRaisesRegex(ValueError, 'APK differs'):
                policy.restored()
            old_apk = root / 'work/source/src/out/RawSandium/apks/ChromePublic.apk'
            old_apk.parent.mkdir(parents=True)
            old_apk.write_bytes(b'mock bytes never treated as validated without matching digest')
            lock = root / 'upstream.lock.json'
            lock.write_bytes(b'lock')
            source_ready = root / 'work/source/source-ready.json'
            with patch.object(policy, 'file_sha', return_value=policy.OLD_APK):
                source_ready.write_text('{"ready":true,"lock_sha256":"different"}')
                with self.assertRaisesRegex(ValueError, 'source proof; no fallback'):
                    policy.restored()
                source_ready.write_text(json.dumps(dict(
                    ready=True, lock_sha256=hashlib.sha256(lock.read_bytes()).hexdigest())))
                policy.restored()

    def test_timeout_and_failed_apk_are_errors(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(policy, 'gate'), \
                patch.object(policy, 'active_feature', return_value=None), \
                patch.object(policy.full, 'ROOT', Path(directory)):
            folder = policy.full.ROOT / 'handoff/stage1'
            folder.mkdir(parents=True)
            apk = policy.full.ROOT / 'artifacts/RawSandium-baseline-arm64.apk'
            apk.parent.mkdir()
            apk.write_bytes(b'synthetic verified-outcome fixture')
            state_file = folder / 'state.json'
            state = dict(status='slice_expired', stage=1, fingerprint=policy.FINGERPRINT)
            state_file.write_text(json.dumps(state))
            with self.assertRaisesRegex(ValueError, 'timed out; no progress saved'):
                policy.completed()
            state.update(status='done', apk_produced=True, apk_verified=True,
                         apk_zip_verified=True, apk_signature_verified=True,
                         apk_sha256=policy.file_sha(apk))
            state_file.write_text(json.dumps(state))
            policy.completed()
            apk.write_bytes(b'wrong APK')
            with self.assertRaisesRegex(ValueError, 'did not produce a verified APK'):
                policy.completed()


if __name__ == '__main__':
    unittest.main()
