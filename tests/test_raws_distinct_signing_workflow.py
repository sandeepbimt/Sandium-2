"""Fail-closed workflow contract; tests do not access CircleCI or signing keys."""
from pathlib import Path
import itertools
import os
import re
import subprocess
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
OPT = '<< pipeline.parameters.run_raw_full >>'
CODEC_OPT = '<< pipeline.parameters.raws_h264_aac >>'
PROBE_OPT = '<< pipeline.parameters.run_raw_signing_probe >>'
BRANCH = 'raw-sandium/official158'
COMPILE = 'raws-test-identity-compile'
SIGN = 'raws-test-identity-sign'
WORKFLOW = 'RawS full'
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

    def evaluate(self, node, values, branch=BRANCH):
        if isinstance(node, str):
            if node == '<< pipeline.git.branch >>':
                return branch
            match = re.fullmatch(r'<< pipeline.parameters.([a-z0-9_]+) >>', node)
            return values[match.group(1)] if match else node
        if isinstance(node, dict):
            op, operands = next(iter(node.items()))
            if op == 'not':
                return not self.evaluate(operands, values, branch)
            results = [self.evaluate(x, values, branch) for x in operands]
            if op == 'and':
                return all(results)
            if op == 'or':
                return any(results)
            if op == 'equal':
                return len(set(results)) == 1
            self.fail('Unsupported exact workflow operator: ' + op)
        return node

    def test_regular_routing_for_ordinary_and_private_codecs(self):
        params = self.config['parameters']
        defaults = {key: entry['default'] for key, entry in params.items()}
        for name in ('run_raw_full', 'raws_h264_aac', 'run_raw_signing_probe'):
            self.assertEqual(params[name], {'type': 'boolean', 'default': False})
        self.assertFalse(set(params) & {'run_raw_signed_test', 'run_raw_combined_codec_trial',
                                       'raw_full_restore_only'})
        workflows = self.config['workflows']
        self.assertNotIn('RawS combined signed codec trial', workflows)
        self.assertNotIn('RawS distinct signed test', workflows)
        self.assertEqual(workflows[WORKFLOW]['jobs'],
                         [{CHAIN: {'serial-group': '<< pipeline.project.slug >>/raws-full'}}])
        routed = lambda values, branch=BRANCH: {
            name for name, flow in workflows.items() if self.evaluate(flow['when'], values, branch)}
        self.assertEqual(routed(defaults), set())
        # If any regular-build flag is supplied, no alternate distribution, maintenance
        # or archive workflow can be selected (including for malformed combinations).
        for bits in itertools.product((False, True), repeat=len(params)):
            values = dict(zip(params, bits))
            if values['run_raw_full'] or values['raws_h264_aac']:
                self.assertEqual(routed(values), {WORKFLOW})
                self.assertEqual(routed(values, 'unapproved'), set())

    def test_request_guard_fails_before_any_restore_for_bad_combinations(self):
        defaults = {key: entry['default'] for key, entry in self.config['parameters'].items()}
        guard = self.compile['steps'][1]['run']['command']
        self.assertIn('Request run_raw_full=true', guard)
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
        env = {'PATH': os.environ['PATH'], 'CIRCLE_BRANCH': BRANCH, 'CIRCLE_SHA1': head}
        def invoke(values):
            command = re.sub(r'<< pipeline.parameters.([a-z0-9_]+) >>',
                     lambda m: str(values[m.group(1)]).lower(), guard)
            return subprocess.run(['bash', '-c', command], cwd=ROOT, env=env,
                                  text=True, capture_output=True)
        for codec in (False, True):
            self.assertEqual(invoke(dict(defaults, run_raw_full=True, raws_h264_aac=codec)).returncode, 0)
        orphan = invoke(dict(defaults, raws_h264_aac=True))
        self.assertEqual(orphan.returncode, 2)
        self.assertIn('Request run_raw_full=true', orphan.stdout)
        for flag in sorted(set(defaults) - {'run_raw_full', 'raws_h264_aac'}):
            result = invoke(dict(defaults, run_raw_full=True, **{flag: True}))
            self.assertEqual(result.returncode, 2)
            self.assertIn('cannot combine with ' + flag, result.stdout)
        self.assertNotIn('restore_cache', str(self.compile['steps'][:2]))

    def test_private_codec_is_setting_of_same_compile_and_signer(self):
        for job in (self.compile, self.sign):
            selected = [step['run']['command'] for step in job['steps']
                        if isinstance(step, dict) and 'run' in step and
                        'RAWS_CODEC_TRIAL=' in step['run']['command']]
            self.assertEqual(len(selected), 3 if job is self.compile else 1)
            self.assertTrue(all('RAWS_CODEC_TRIAL='+CODEC_OPT+' RAWS_UNSIGNED_TEST_APK=true' in s for s in selected))
        self.assertNotIn('RAWS_CODEC_TRIAL', str(self.config['jobs']['raws-full-stage-1']))
        self.assertNotIn('RAWS_UNSIGNED_TEST_APK', self.config['parameters'])
        for owner in (self.compile, self.sign, self.config['jobs'][PROBE]):
            self.assertNotIn('RAWS_UNSIGNED_TEST_APK', owner.get('environment', {}))
        for owner in (self.config['jobs']['raws-full-stage-1'], self.config['jobs'][PROBE]):
            self.assertNotIn('RAWS_UNSIGNED_TEST_APK', str(owner))

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
            self.assertIn('RAWS_CODEC_TRIAL='+CODEC_OPT+' RAWS_UNSIGNED_TEST_APK=true RAWS_DISTINCT_TEST_IDENTITY=true RAWS_ALLOW_FRESH_SEED=false '
                          'python3 -u tools/ci_restore_only.py ' + phase, selected)
        preflight = next(cmd for cmd in commands if 'unittest discover' in cmd)
        self.assertNotIn('RAWS_DISTINCT_TEST_IDENTITY', preflight)

    def test_exact_restore_private_inputs_no_compile_cache_save_or_artifact(self):
        steps = self.compile['steps']
        from ci_restore_only import BASE_CACHE, RECEIPT_CACHE
        self.assertTrue(any('ci_restore_only.py completed' in s.get('run', {}).get('command', '')
                            for s in steps if isinstance(s, dict)))
        restored = [s['restore_cache']['keys'] for s in steps
                    if isinstance(s, dict) and 'restore_cache' in s]
        self.assertEqual(restored, [[RECEIPT_CACHE], [BASE_CACHE]])
        names = str(steps)
        for before, after in (('ci_restore_only.py select', 'Restore exact verified RawS #1396 final archive'),
                              ('ci_full.py restore-finish', 'ci_restore_only.py compile'),
                              ('ci_restore_only.py compile', 'ci_restore_only.py completed'),
                              ('ci_restore_only.py completed', 'persist_to_workspace')):
            self.assertLess(names.index(before), names.index(after))
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
