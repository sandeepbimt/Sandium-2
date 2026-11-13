"""Pinned-source regression checks for the missing Origin preference crash.

These test patch composition, not an Android Settings lifecycle/device run.
"""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('ui_prune', ROOT / '.circleci/scripts/apply-sandium-ui-prune.py')
OVERLAY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OVERLAY)
REL = Path('android/java/org/chromium/chrome/browser/settings/BraveMainPreferencesBase.java')
ORIGINAL = (ROOT / 'tests/fixtures/settings/BraveMainPreferencesBase.java').read_text()
OLD = '''        if (ChromeFeatureList.isEnabled(BraveFeatureList.BRAVE_ORIGIN)) {
            setPreferenceOrder(PREF_BRAVE_ORIGIN, ++generalOrder);
'''
NEW = '''        // SANDIUM_REMOVED_ORIGIN_ORDER_GUARD
        if (ChromeFeatureList.isEnabled(BraveFeatureList.BRAVE_ORIGIN)
                && findPreference(PREF_BRAVE_ORIGIN) != null) {
            setPreferenceOrder(PREF_BRAVE_ORIGIN, ++generalOrder);
'''

class OriginOrderingPatchTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.core = Path(self.temp.name)
        self.path = self.core / REL
        self.path.parent.mkdir(parents=True)
        self.path.write_text(ORIGINAL)

    def test_exact_pinned_source_changes_only_origin_guard(self):
        self.assertEqual(ORIGINAL.count(OLD), 1)
        OVERLAY.patch_removed_origin_ordering(self.core)
        self.assertEqual(self.path.read_text(), ORIGINAL.replace(OLD, NEW, 1))

    def test_idempotent(self):
        OVERLAY.patch_removed_origin_ordering(self.core)
        first = self.path.read_bytes()
        OVERLAY.patch_removed_origin_ordering(self.core)
        self.assertEqual(first, self.path.read_bytes())

    def test_unexpected_upstream_anchor_fails_closed(self):
        self.path.write_text(ORIGINAL.replace(OLD, '/* changed upstream */\n'))
        with self.assertRaisesRegex(RuntimeError, 'expected one source anchor'):
            OVERLAY.patch_removed_origin_ordering(self.core)

    def test_strict_mandatory_preference_helper_preserved(self):
        OVERLAY.patch_removed_origin_ordering(self.core)
        self.assertIn('''        Preference preference = findPreference(key);
        assumeNonNull(preference);
        preference.setOrder(order);''', self.path.read_text())

    def test_absent_origin_else_path_remains_null_safe(self):
        OVERLAY.patch_removed_origin_ordering(self.core)
        self.assertIn(NEW + '''        } else {
            removePreferenceIfPresent(PREF_BRAVE_ORIGIN);
        }''', self.path.read_text())
        self.assertIn('''        Preference preference = getPreferenceScreen().findPreference(key);
        if (preference != null) {''', self.path.read_text())

    def test_patch_is_wired_into_actual_overlay_entrypoint(self):
        script = (ROOT / '.circleci/scripts/apply-sandium-ui-prune.py').read_text()
        self.assertIn('    patch_removed_origin_ordering(core)\n', script.split('def main() -> None:')[1])

if __name__ == '__main__':
    unittest.main()
