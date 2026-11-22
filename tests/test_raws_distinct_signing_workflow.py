"""Fail-closed workflow contract; tests do not access CircleCI or signing keys."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
OPT = '<< pipeline.parameters.run_raw_signed_test >>'
CODEC_OPT = '<< pipeline.parameters.run_raw_combined_codec_trial >>'
CODEC_WORKFLOW = 'RawS combined signed codec trial'
PROBE_OPT = '<< pipeline.parameters.run_raw_signing_probe >>'
BRANCH = 'raw-sandium/official158'
COMPILE = 'raws-test-identity-compile'
SIGN = 'raws-test-identity-sign'
WORKFLOW = 'RawS distinct signed test'
CHAIN = 'raws-signed-test-chain'
PROBE = 'raws-test-signing-context-probe'
PROBE_WORKFLOW = 'RawS signing context probe'
KEYS = ('RAWS_TEST_KEYSTORE_B64', 'RAWS_KEYSTORE_PASSWORD', 'RAWS_KEY_PASSWORD')
SDK_PIN = '5d9ac77fb6ff43d9da518a337b4fcf8f9097113df531d99ccefe80ef7ce8250b'


class RawSDistinctSigningWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.config = yaml.safe_load((ROOT / '.circleci/config.yml').read_text())
        self.compile = self.config['jobs'][COMPILE]
        self.sign = self.config['jobs'][SIGN]

    def test_exact_opt_in_does_not_schedule_normal_or_conflicting_workflows(self):
        self.assertEqual(self.config['parameters']['run_raw_signed_test'],
                         {'type': 'boolean', 'default': False})
        self.assertEqual(self.config['parameters']['run_raw_signing_probe'],
                         {'type': 'boolean', 'default': False})
        wf = self.config['workflows'][WORKFLOW]
        self.assertEqual(wf['jobs'], [{CHAIN: {'serial-group': '<< pipeline.project.slug >>/raws-full'}}])
        self.assertEqual(wf['when']['and'], [
            OPT, {'equal': [BRANCH, '<< pipeline.git.branch >>']},
            *({'not': f'<< pipeline.parameters.{key} >>'}
              for key in self.config['parameters'] if key != 'run_raw_signed_test'),
        ])
        for name, other in self.config['workflows'].items():
            if name not in (WORKFLOW, PROBE_WORKFLOW, CODEC_WORKFLOW):
                self.assertIn({'not': OPT}, other['when']['and'])
                self.assertIn({'not': PROBE_OPT}, other['when']['and'])
                self.assertIn({'not': CODEC_OPT}, other['when']['and'])

    def test_codec_workflow_reuses_exact_shared_signed_chain_and_is_exclusive(self):
        self.assertEqual(self.config['parameters']['run_raw_combined_codec_trial'],
                         {'type': 'boolean', 'default': False})
        workflow = self.config['workflows'][CODEC_WORKFLOW]
        self.assertEqual(workflow['jobs'], self.config['workflows'][WORKFLOW]['jobs'])
        self.assertEqual(workflow['when']['and'], [
            CODEC_OPT, {'equal': [BRANCH, '<< pipeline.git.branch >>']},
            *({'not': f'<< pipeline.parameters.{key} >>'}
              for key in self.config['parameters'] if key != 'run_raw_combined_codec_trial'),
        ])
        for job in (self.compile, self.sign):
            selected = [step['run']['command'] for step in job['steps']
                        if isinstance(step, dict) and 'run' in step and
                        'RAWS_CODEC_TRIAL' in step['run']['command']]
            self.assertEqual(len(selected), 3 if job is self.compile else 1)
            self.assertTrue(all('RAWS_CODEC_TRIAL='+CODEC_OPT in s for s in selected))
        self.assertNotIn('RAWS_CODEC_TRIAL', str(self.config['jobs']['raws-full-stage-1']))

    def test_context_is_on_signer_only_and_compile_gets_no_secrets(self):
        chain = self.config['job-groups'][CHAIN]['jobs']
        filt = {'branches': {'only': BRANCH}}
        self.assertEqual(chain, [
            {COMPILE: {'filters': filt}},
            {SIGN: {'requires': [COMPILE], 'filters': filt, 'context': 'RawS-Test-Signing'}},
        ])
        self.assertEqual(str(self.config).count('RawS-Test-Signing'), 2)
        self.assertNotIn('RAWS_DISTINCT_TEST_IDENTITY', self.compile['environment'])
        self.assertEqual(self.compile['environment']['RAWS_ALLOW_FRESH_SEED'], 'false')
        for key in KEYS:
            self.assertNotIn(key, self.compile['environment'])
            self.assertIn('${' + key + '+x}', self.compile['steps'][1]['run']['command'])
        self.assertNotIn('context', self.compile)
        self.assertNotIn('environment', self.sign)

    def test_identity_mode_applies_only_to_authenticated_policy_steps(self):
        commands = [step.get('run', {}).get('command', '') for step in self.compile['steps']
                    if isinstance(step, dict)]
        selected = [cmd for cmd in commands if 'RAWS_DISTINCT_TEST_IDENTITY' in cmd]
        self.assertEqual(3, len(selected))
        for phase in ('select', 'compile', 'completed'):
            self.assertIn('RAWS_CODEC_TRIAL='+CODEC_OPT+' RAWS_DISTINCT_TEST_IDENTITY=true RAWS_ALLOW_FRESH_SEED=false '
                          'python3 -u tools/ci_restore_only.py ' + phase, selected)
        preflight = next(cmd for cmd in commands if 'unittest discover' in cmd)
        self.assertNotIn('RAWS_DISTINCT_TEST_IDENTITY', preflight)

    def test_exact_restore_private_inputs_no_compile_cache_save_or_artifact(self):
        steps = self.compile['steps']
        ordinary = self.config['jobs']['raws-full-stage-1']['steps']
        restore_only = next(s['when']['steps'] for s in ordinary if 'when' in s)
        for mode in (steps, restore_only):
            self.assertTrue(any('ci_restore_only.py completed' in s.get('run', {}).get('command', '')
                                for s in mode if isinstance(s, dict)))
        restored = lambda seq: [s['restore_cache'] for s in seq
                                if isinstance(s, dict) and 'restore_cache' in s]
        self.assertEqual(restored(steps), restored(restore_only))
        self.assertEqual(steps[-1], {'persist_to_workspace': {
            'root': '.raws-signing-input', 'paths': ['candidate.apk', 'receipt.json']}})
        for forbidden in ('store_artifacts', 'save_cache', 'attach_workspace', 'fresh source'):
            self.assertNotIn(forbidden, str(steps))

    def test_signer_installs_hash_pinned_sdk_before_private_attach(self):
        steps = self.sign['steps']
        sdk = steps[2]['run']['command']
        self.assertIn('expected=' + SDK_PIN, sdk)
        self.assertIn('-eq 63737259', sdk)
        self.assertIn('prefix=android-16 revision=36.0.0', sdk)
        self.assertIn('https://dl.google.com/android/repository/build-tools_r36_linux.zip', sdk)
        self.assertLess(sdk.index('sha256sum --check --status'), sdk.index('unzip -q'))
        self.assertEqual(steps[3], {'attach_workspace': {'at': '.raws-signing-input'}})
        self.assertEqual(steps[-1], {'store_artifacts': {
            'path': 'artifacts/raws-signed', 'destination': 'raws-signed'}})
        self.assertNotIn('restore_cache', str(steps))
        self.assertNotIn('persist_to_workspace', str(steps))

    def test_failed_verifier_in_private_stage_cannot_publish_partial_candidate(self):
        command = self.sign['steps'][4]['run']['command'].replace(CODEC_OPT, 'false')
        for result in (0, 1):
            with self.subTest(code=result), tempfile.TemporaryDirectory() as tmp:
                cwd = Path(tmp)
                (cwd / 'tools').mkdir()
                (cwd / 'tools/ci_sign_raws_test.py').write_text(
                    'from pathlib import Path\nimport sys\n'
                    'dst = Path(sys.argv[sys.argv.index("--output-dir") + 1])\n'
                    'dst.mkdir()\n(dst / "signed.apk").touch()\n'
                    f'raise SystemExit({result})\n')
                finished = subprocess.run(['bash', '-c', command], cwd=cwd, check=False)
                self.assertEqual(finished.returncode, result)
                self.assertEqual((cwd / 'artifacts/raws-signed/signed.apk').is_file(), result == 0)
                self.assertEqual((cwd / '.raws-signing-verified/signed.apk').is_file(), result != 0)

    def test_probe_only_accepts_canary_with_no_credentials_even_empty(self):
        job = self.config['jobs'][PROBE]
        steps = job['steps']
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[1]['run']['command'], self.sign['steps'][2]['run']['command'])
        forbidden = ('checkout', 'save_cache', 'restore_cache', 'attach_workspace',
                     'persist_to_workspace', 'store_artifacts', 'ci_compile', 'ci_sign_raws_test')
        for step in forbidden:
            self.assertNotIn(step, str(steps))
        workflow = self.config['workflows'][PROBE_WORKFLOW]
        self.assertEqual(workflow['jobs'], [{PROBE: {'filters': {'branches': {'only': BRANCH}},
                                                    'context': 'RawS-Test-Signing'}}])
        self.assertEqual(workflow['when']['and'], [
            PROBE_OPT, {'equal': [BRANCH, '<< pipeline.git.branch >>']},
            *({'not': f'<< pipeline.parameters.{key} >>'}
              for key in self.config['parameters'] if key != 'run_raw_signing_probe'),
        ])
        cmd = ['bash', '-c', steps[0]['run']['command']]
        env = {k: v for k, v in os.environ.items() if k not in KEYS}
        env.update(CIRCLE_BRANCH=BRANCH, RAWS_SIGNING_CONTEXT_CANARY='raws-test-signing-probe-v1')
        self.assertEqual(subprocess.run(cmd, env=env, check=False).returncode, 0)
        for k in KEYS:
            self.assertNotEqual(subprocess.run(cmd, env={**env, k: ''}, check=False).returncode, 0)
        self.assertNotEqual(subprocess.run(cmd, env={**env, 'CIRCLE_BRANCH': 'other'}, check=False).returncode, 0)
        self.assertNotEqual(subprocess.run(cmd, env={**env, 'RAWS_SIGNING_CONTEXT_CANARY': ''},
                                           check=False).returncode, 0)
