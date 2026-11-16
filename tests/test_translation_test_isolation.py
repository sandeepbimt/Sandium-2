"""Keep the experimental JNI build independent of normal reference publication."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / '.circleci/translation-test/build_config.py'
spec = importlib.util.spec_from_file_location('translation_config', PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def walk(value, key):
    if isinstance(value, dict):
        if key in value:
            yield value[key]
        for child in value.values():
            yield from walk(child, key)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child, key)


class TranslationBuildIsolation(unittest.TestCase):
    def setUp(self):
        self.normal = yaml.safe_load((ROOT / '.circleci/original-full/candidate.yml').read_text())
        self.cfg = module.derive(self.normal)

    def test_derivation_preserves_normal_and_is_deterministic(self):
        before = copy.deepcopy(self.normal)
        self.assertEqual(self.cfg, module.derive(self.normal))
        self.assertEqual(before, self.normal)
        raw = (ROOT / '.circleci/translation-test/config.yml').read_bytes()
        self.assertEqual(self.cfg, yaml.safe_load(raw))
        self.assertEqual(hashlib.sha256(raw).hexdigest(), (ROOT / '.circleci/translation-test/config.sha256').read_text().strip())

    def test_no_shared_cache_writes_or_maintenance(self):
        self.assertNotIn('renew-fixed-reference', self.cfg['jobs'])
        self.assertNotIn('fixed-reference-maintenance', self.cfg['workflows'])
        writes = list(walk(self.cfg, 'save_cache'))
        self.assertEqual(len(writes), 2)
        for write in writes:
            self.assertIn('{{ .Branch }}', write['key'])
            self.assertIn('{{ .Environment.CIRCLE_WORKFLOW_ID }}', write['key'])
            self.assertTrue(write['key'].startswith(('sandium-brave-handoff-v2-', 'sandium-brave-apk-complete-v2-')))
        self.assertEqual(list(walk(self.normal['jobs']['brave-android-staged-build'], 'restore_cache')),
                         list(walk(self.cfg, 'restore_cache')))

    def test_only_test_branch_and_manual_build_gate(self):
        for job in self.cfg['workflows']['sandium-full-mode']['jobs']:
            self.assertEqual(job['brave-android-staged-build']['filters']['branches']['only'], module.BRANCH)
        self.assertFalse(self.cfg['parameters']['run_build']['default'])
        self.assertEqual(self.cfg['workflows']['sandium-full-mode']['when'], self.normal['workflows']['sandium-full-mode']['when'])

    def test_guard_after_reset_overlays_before_build(self):
        steps = self.cfg['jobs']['brave-android-staged-build']['steps']
        runs = [step['run'] for step in steps if isinstance(step, dict) and 'run' in step]
        commands = [run['command'] for run in runs]
        overlay = commands.index('bash .circleci/experimental-steps/product-overlay-30-0.sh')
        guard = next(i for i, command in enumerate(commands) if module.GUARD in command)
        graph = next(i for i, run in enumerate(runs) if run['name'] == 'Validate build graph and remote-execution settings')
        self.assertEqual(guard, overlay + 1)
        self.assertLess(guard, graph)
        self.assertIn('test "${CIRCLE_BRANCH:-}" = "' + module.BRANCH + '"', commands[guard])
        self.assertEqual([{'path': 'brave-apk', 'destination': 'sandium-arm-translation-test-only/brave-apk'}], list(walk(self.cfg, 'store_artifacts')))

    def test_wiring_accepts_exact_test_fixture_rejects_mutation(self):
        spec = importlib.util.spec_from_file_location('translation_wiring', ROOT / '.circleci/scripts/flow_wiring.py')
        wiring = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(wiring)
        from unittest import mock
        import shutil
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for rel in ('.circleci/original-full/config.sha256', '.circleci/translation-test/config.yml', '.circleci/translation-test/config.sha256'):
                dest = root / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / rel, dest)
            active = root / '.circleci/config.yml'
            shutil.copy2(root / '.circleci/translation-test/config.yml', active)
            with mock.patch.object(wiring, 'verify_product_wrappers') as wrappers:
                self.assertEqual(['brave-android-staged-build'], wiring.verify_full_wiring(root))
                wrappers.assert_called_once_with(root)
                active.write_text(active.read_text() + '# unreviewed mutation\n')
                with self.assertRaisesRegex(ValueError, 'configuration differs'):
                    wiring.verify_full_wiring(root)

    def test_only_explicit_derivation_changes(self):
        normal_steps = self.normal['jobs']['brave-android-staged-build']['steps']
        test_steps = self.cfg['jobs']['brave-android-staged-build']['steps']
        for name in ('Build bounded Brave Android APK slice', 'Export APK status and artifacts', 'Skip large handoff after verified APK publication', 'Final five-stage completion gate'):
            find = lambda steps: next(step['run'] for step in steps if isinstance(step, dict) and step.get('run', {}).get('name') == name)
            self.assertEqual(find(normal_steps), find(test_steps))


if __name__ == '__main__':
    unittest.main()
