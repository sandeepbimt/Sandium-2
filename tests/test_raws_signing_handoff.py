import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import ci_sign_raws_test as ci


class SigningHandoffTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.commit = 'c' * 40
        self.workflow = '00000000-0000-4000-8000-000000000001'
        self.run = (self.commit, self.workflow)
        manifest = self.root / 'raws-adblock/production-restore-recipe.json'
        manifest.parent.mkdir()
        manifest.write_text('{}\n')
        self.apk = self.root / 'original.apk'
        self.apk.write_bytes(b'candidate bytes')
        self.state = dict.fromkeys(ci.EVIDENCE, True)
        self.state.update(
            stage=1, status='done', apk_package=ci.APPLICATION_ID,
            apk_abis=['arm64-v8a'], feature_recipe_sha256=ci.sha256(manifest),
            apk_sha256=ci.sha256(self.apk), raws_engine_smoke={'cases': list(range(13))},
        )

    def stage(self):
        with patch.object(ci, 'run_identity', return_value=self.run):
            ci.stage_private_input(self.root, self.state, self.apk)
        return self.root / ci.HANDOFF

    def test_handoff_is_private_and_bound_to_exact_checkout(self):
        source = self.stage()
        with patch.object(ci, 'run_identity', return_value=self.run):
            apk, proof = ci.input_receipt(self.root, source)
        self.assertEqual(ci.sha256(apk), self.state['apk_sha256'])
        self.assertEqual(proof['commit'], self.commit)
        self.assertFalse(self.apk.exists())
        self.assertFalse((self.root / 'artifacts').exists())

    def test_missing_graph_never_creates_handoff(self):
        self.state['raws_ui_apk_graph_verified'] = False
        with self.assertRaisesRegex(ValueError, 'Unverified'):
            self.stage()
        self.assertFalse((self.root / ci.HANDOFF).exists())

    def test_modified_input_or_workflow_does_not_pass(self):
        source = self.stage()
        other = '00000000-0000-4000-8000-000000000002'
        with patch.object(ci, 'run_identity', return_value=(self.commit, other)):
            with self.assertRaisesRegex(ValueError, 'exact candidate'):
                ci.input_receipt(self.root, source)
        (source / 'candidate.apk').write_bytes(b'other bytes')
        with patch.object(ci, 'run_identity', return_value=self.run):
            with self.assertRaisesRegex(ValueError, 'exact candidate'):
                ci.input_receipt(self.root, source)

    def test_recipe_from_different_checkout_does_not_pass(self):
        source = self.stage()
        (self.root / 'raws-adblock/production-restore-recipe.json').write_text('{"other":1}')
        with patch.object(ci, 'run_identity', return_value=self.run):
            with self.assertRaisesRegex(ValueError, 'feature recipe'):
                ci.input_receipt(self.root, source)

    def test_signing_failure_never_creates_artifact(self):
        source = self.stage()
        target = self.root / 'artifacts/raws-signed'
        with patch.object(ci, 'run_identity', return_value=self.run), \
                patch.dict(ci.os.environ, {'RAWS_TEST_SIGNER_PIN_SHA256': 'a' * 64,
                                          'RAWS_TEST_KEYSTORE_B64': 'YQ=='}, clear=True), \
                patch.object(ci, 'sign_release_locally', side_effect=ValueError('synthetic')):
            with self.assertRaisesRegex(ValueError, 'synthetic'):
                ci.sign(self.root, source, self.root / 'sdk', target)
        self.assertFalse(target.exists())

    def test_public_output_contains_only_verified_apk_and_receipt(self):
        source = self.stage()
        target = self.root / 'artifacts/raws-signed'

        def signed(apk, output, sdk, key, alias, pin, *, expected_input_sha256):
            self.assertEqual(0o600, key.stat().st_mode & 0o777)
            self.assertEqual(alias, 'raws-test')
            self.assertEqual(expected_input_sha256, ci.sha256(apk))
            self.assertFalse(target.exists())
            output.write_bytes(b'verified signature')
            return {'apk_project_identity_verified': True,
                    'apk_sha256': hashlib.sha256(b'verified signature').hexdigest()}

        with patch.object(ci, 'run_identity', return_value=self.run), \
                patch.dict(ci.os.environ, {'RAWS_TEST_SIGNER_PIN_SHA256': 'a' * 64,
                                          'RAWS_TEST_KEYSTORE_B64': 'YQ=='}, clear=True), \
                patch.object(ci, 'sign_release_locally', side_effect=signed):
            ci.sign(self.root, source, self.root / 'sdk', target)
        self.assertEqual({p.name for p in target.iterdir()},
                         {ci.APK_NAME, 'signing-receipt.json'})
        self.assertTrue(json.loads((target / 'signing-receipt.json').read_text())['distribution_ready'])
