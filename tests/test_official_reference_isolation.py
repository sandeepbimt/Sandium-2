"""The official candidate may read a frozen seed but cannot promote into it."""
from pathlib import Path
import unittest
import yaml
ROOT = Path(__file__).resolve().parents[1]
BRANCH = 'fix/official-checkpoint-1392'

def entries(obj, key):
    if isinstance(obj, dict):
        for k, value in obj.items():
            if k == key:
                yield value
            yield from entries(value, key)
    elif isinstance(obj, list):
        for value in obj:
            yield from entries(value, key)

class OfficialIsolation(unittest.TestCase):
    def setUp(self):
        self.config = yaml.safe_load((ROOT / '.circleci/config.yml').read_text())
        self.job = self.config['jobs']['brave-android-staged-build']

    def test_all_writes_are_private_or_package_only(self):
        writes = list(entries(self.job, 'save_cache'))
        self.assertEqual(len(writes), 4)
        for write in writes:
            key = write['key']
            self.assertTrue(key.startswith(('sandium-official-handoff-v1-',
                'sandium-official-apk-complete-v1-', 'sandium-brave-apt-v1-',
                'sandium-brave-node-v1-')), key)
            if key.startswith('sandium-official-'):
                self.assertIn('{{ .Branch }}', key)
                self.assertIn('{{ .Environment.CIRCLE_WORKFLOW_ID }}', key)
            if key.startswith('sandium-official-apk-'):
                self.assertIn('{{ .Revision }}', key)
        self.assertNotIn('promote-brave-reference', str(self.job))
        self.assertNotIn('renewal-prepare', str(self.job))
        self.assertNotIn('full_driver.py capture', str(self.job))

    def test_reads_do_not_mix_current_stage_outputs(self):
        restores = list(entries(self.job, 'restore_cache'))
        keys = [key for restore in restores for key in restore['keys']]
        self.assertTrue(any(k.startswith('fixed-sandium-reference-v1-') for k in keys))
        self.assertTrue(any(k.startswith('sandium-bridge-base-v1-') for k in keys))
        self.assertFalse(any(k.startswith(('sandium-brave-apk-complete-v2-',
            'sandium-brave-handoff-v2-', 'sandium-brave-handoff-v1-')) and '{{' in k for k in keys))
        literal_seeds = [k for k in keys if 'fix-archive-completion-gate' in k]
        self.assertEqual(literal_seeds, ['sandium-brave-handoff-v2-sandium/fix-archive-completion-gate-d0bc6af6-e2a7-451e-8561-3c90eb48c2e1-stage-1'] * 5)
        stage_keys = [k for k in keys if k.startswith('sandium-official-handoff-v1-') and '{{' in k]
        self.assertTrue(stage_keys)
        for key in stage_keys:
            self.assertIn('{{ .Branch }}', key)
            self.assertIn('{{ .Environment.CIRCLE_WORKFLOW_ID }}', key)

    def test_manual_full_only_branch_and_no_maintenance_path(self):
        parameters = self.config['parameters']
        self.assertFalse(parameters['run_build']['default'])
        self.assertFalse(parameters['run_maintenance']['default'])
        self.assertEqual(parameters['sandium_build_mode']['enum'], ['full'])
        jobs = self.config['workflows']['sandium-full-mode']['jobs']
        self.assertEqual(len(jobs), 5)
        for i, item in enumerate(jobs, 1):
            job = item['brave-android-staged-build']
            self.assertEqual(job['filters']['branches']['only'], [BRANCH])
            self.assertEqual(job['stage_index'], i)
            self.assertEqual(job.get('requires', []), [] if i == 1 else [f'SANDIUM-FULL-MODE-stage-{i-1}'])
        maintenance = self.config['workflows']['fixed-reference-maintenance']['jobs'][0]['renew-fixed-reference']
        self.assertEqual(maintenance['filters']['branches']['only'], 'experiment/sandium-back-transition')
        self.assertNotIn(BRANCH, str(maintenance))
        self.assertIn('STAGE_BUILD_BUDGET_SECONDS=1500', str(self.job))

if __name__ == '__main__':
    unittest.main()
