"""Reset-owner-only migration; never reclassify historical resource findings."""
import copy
import gzip
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/1402-lint-provenance'
DATA = ROOT / '.circleci/features/lint-resources'
sha = lambda data: hashlib.sha256(data).hexdigest()
OWNERS = [
    'chrome/browser/notifications/android/java/src/org/chromium/chrome/browser/notifications/permissions/NotificationPermissionController.java',
    'chrome/android/java/src/org/chromium/chrome/browser/tabbed_mode/TabbedRootUiCoordinator.java',
]
PATCH = 'patches/chrome-android-java-src-org-chromium-chrome-browser-tabbed_mode-TabbedRootUiCoordinator.java.patch'

class ResetOnlyLintProvenance(unittest.TestCase):
    def setUp(self):
        self.proof = json.loads((FIXTURE / 'proof.json').read_text())

    def test_exact_reset_only_recipe_delta(self):
        old = gzip.decompress((FIXTURE / 'old-removal-recipe.json.gz').read_bytes())
        new = (ROOT / '.circleci/features/removal-recipe.json').read_bytes()
        self.assertEqual(sha(old), self.proof['old_recipe_sha256'])
        self.assertEqual(sha(new), self.proof['new_recipe_sha256'])
        expected = json.loads(old)
        for key in ('chromium_restore', 'ui_only_chromium_restore'):
            self.assertTrue(all(p not in expected[key] for p in OWNERS))
            expected[key].extend(OWNERS)
        self.assertNotIn(OWNERS[1], expected['chromium_restore_patches'])
        expected['chromium_restore_patches'][OWNERS[1]] = PATCH
        self.assertEqual(json.loads(new), expected)  # Includes all groups, steps and resources.

    def test_all_historical_evidence_and_rows_byte_reconstruct(self):
        for name, proof in self.proof['inventories'].items():
            with self.subTest(inventory=name):
                data = json.loads((DATA / name).read_text())
                if name == 'inventory.json':
                    # Only the Settings-scoped palette adapter changed. Verify its live proof,
                    # then reconstruct the precise historical #1402 record for this test.
                    proofs = [r['removal_evidence'] for r in data['resources']
                              if r['resource'] == 'R.color.gm3_baseline_surface_container_lowest_dark']
                    self.assertEqual(len(proofs), 1)
                    palette = proofs[0]
                    self.assertEqual(palette['source_path'],
                                     '.circleci/scripts/apply-sandium-native-theme.py')
                    self.assertEqual(palette['sha256'], sha((ROOT / palette['source_path']).read_bytes()))
                    palette['sha256'] = '9260eb297226fa5bd06b25183f2b7f3433851f6ba6f9995c236afa74dac92c53'
                content = {k: v for k, v in data.items() if k != 'provenance'}
                self.assertEqual(sha(json.dumps(content, sort_keys=True, separators=(',', ':')).encode()),
                                 proof['content_without_provenance_sha256'])
                expected = dict(proof['provenance'])
                expected['removal_recipe_sha256'] = self.proof['new_recipe_sha256']
                if name == 'inventory-1401.json':
                    expected['base_inventory_sha256'] = sha((DATA / 'inventory.json').read_bytes())
                self.assertEqual(data['provenance'], expected)
                data['provenance'] = proof['provenance']
                self.assertEqual(sha((json.dumps(data, indent=2) + '\n').encode()), proof['sha256'])

    def test_runtime_load_and_render_unchanged(self):
        spec = importlib.util.spec_from_file_location('lint1402provenance', ROOT / '.circleci/scripts/apply-sandium-lint-resources.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        base, upstream = module.load(); supplement = module.load_supplement(base)
        self.assertEqual((len(base['resources']), len(supplement['resources'])), (328, 644))
        self.assertEqual(sum(r['approved'] for r in base['resources']), 320)
        before_base, before_supplement = copy.deepcopy(base), copy.deepcopy(supplement)
        before_base['provenance'] = self.proof['inventories']['inventory.json']['provenance']
        before_supplement['provenance'] = self.proof['inventories']['inventory-1401.json']['provenance']
        before = module.render(before_base, upstream, supplement=before_supplement)
        after = module.render(base, upstream, supplement=supplement)
        self.assertEqual(before, after)
        self.assertEqual(after.count(b'<ignore regexp="^The resource'), 964)

if __name__ == '__main__':
    unittest.main()
