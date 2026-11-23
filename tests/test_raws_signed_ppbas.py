"""Same-machine PPBAS admission; do not execute APT, hooks, or remote builds."""
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import ci_compile
import ci_restore_only as policy
from generate_full_config import generate


class RawSSignedPPBASTests(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        self.state = self.root / '.checkpoint-state'
        self.state.mkdir()
        self.receipt = self.state / 'signed-ppbas.json'
        source = self.root / 'work/source'
        source.mkdir(parents=True)
        (source / 'source-ready.json').write_text('{}')
        (self.root / 'upstream.lock.json').write_text('{"upstream":1}')
        self.epoch = self.state / 'job-start.json'
        self.epoch.write_text('{"epoch":1000}')
        self.c = SimpleNamespace(
            read=lambda p: json.loads(p.read_text()),
            save=lambda p, data: p.write_text(json.dumps(data)))
        self.feature = SimpleNamespace(identity='b'*64, has_ui=True, verify=Mock())
        self.env = {
            'CIRCLE_JOB': 'raws-test-identity-compile', 'CIRCLE_SHA1': 'a'*40,
            'CIRCLE_WORKFLOW_ID': '31dbef20-0996-4e61-9a05-3aa42aa67275',
            'CIRCLE_BUILD_NUM': '4123', 'RAWS_DISTINCT_TEST_IDENTITY': 'true',
            'RAWS_UNSIGNED_TEST_APK': 'true', 'RAWS_CODEC_TRIAL': 'false',
        }
        for patcher in (
            patch.object(policy.full, 'ROOT', self.root),
            patch.object(policy.full.D, 'STATE', self.state),
            patch.object(policy.full.D, 'c', self.c),
            patch.dict(os.environ, self.env, clear=True),
            patch('raws_codec_trial.git', return_value=self.env['CIRCLE_SHA1']),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_exact_same_vm_job_head_lock_recipe_epoch_and_mode(self):
        with self.assertRaisesRegex(ValueError, 'missing|Missing'):
            policy.require_prepared(self.feature)
        expected = policy.prepared_contract(self.feature)
        self.c.save(self.receipt, expected)
        policy.require_prepared(self.feature)
        for key in ('boot', 'workflow', 'job', 'head', 'source_ready', 'lock',
                    'checkpoint_receipt', 'checkpoint_fingerprint', 'recipe', 'start_epoch',
                    'codec', 'dependencies_and_hooks_complete'):
            with self.subTest(key=key):
                self.c.save(self.receipt, expected | {key: 'stale'})
                with self.assertRaisesRegex(ValueError, 'same-job'):
                    policy.require_prepared(self.feature)
        self.receipt.unlink()
        other = self.root / 'unsafe'
        self.c.save(other, expected)
        self.receipt.symlink_to(other)
        with self.assertRaisesRegex(ValueError, 'same-job'):
            policy.require_prepared(self.feature)

    def test_receipt_follows_successful_dependencies_and_hooks_only(self):
        with (patch.object(policy, 'gate'), patch.object(policy, 'active_feature',
              return_value=self.feature), patch.object(policy, 'materialize_feature',
              return_value=self.feature), patch.object(ci_compile, 'verified_source_env',
              return_value=({}, {'PATH': '/fixture'})), patch.object(ci_compile,
              'install_host_and_hooks', side_effect=TimeoutError('installer failed')) as setup):
            with self.assertRaisesRegex(TimeoutError, 'installer failed'):
                policy.prepare_signed()
            self.assertFalse(self.receipt.exists())
            setup.side_effect = None
            policy.prepare_signed()
            policy.require_prepared(self.feature)
            with self.assertRaisesRegex(ValueError, 'existing'):
                policy.prepare_signed()
            self.assertEqual(setup.call_count, 2)

    def test_build_must_read_proof_and_never_rematerializes(self):
        with (patch.object(policy, 'restored') as restored,
              patch.object(policy, 'active_feature', return_value=self.feature),
              patch.object(policy, 'materialize_feature') as materialize,
              patch.object(ci_compile, 'main', return_value=0) as compile_main):
            with self.assertRaisesRegex(ValueError, 'same-job'):
                policy.compile_prepared()
            compile_main.assert_not_called()
            self.c.save(self.receipt, policy.prepared_contract(self.feature))
            self.assertEqual(policy.compile_prepared(), 0)
            compile_main.assert_called_once_with(1, feature=self.feature,
                distinct_test=True, codec_trial=False, prepared=True)
            self.assertEqual(restored.call_count, 2)
            materialize.assert_not_called()

    def test_generator_and_checked_in_config_match(self):
        checked_in = yaml.safe_load((ROOT / '.circleci/config.yml').read_text())
        self.assertEqual(checked_in, generate())


if __name__ == '__main__':
    unittest.main()
