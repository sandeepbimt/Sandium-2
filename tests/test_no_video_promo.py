import importlib.util
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('promo', ROOT / '.circleci/scripts/apply-sandium-no-video-promo.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
FIX = ROOT / 'tests/fixtures/video-promo'

class PromoTests(unittest.TestCase):
    def test_launch_removed_and_dismissal_persisted(self):
        source = (FIX / 'activity-method.txt').read_text()
        result = m.activity('UNCHANGED PREFIX\n' + source + '\nUNCHANGED SUFFIX')
        self.assertNotIn('new BraveAdFreeCalloutDialogFragment', result)
        self.assertIn('BRAVE_AD_FREE_CALLOUT_DIALOG, false', result)
        self.assertTrue(result.startswith('UNCHANGED PREFIX\n'))
        self.assertTrue(result.endswith('\nUNCHANGED SUFFIX'))
        self.assertEqual(result, m.activity(result))

    def test_old_saved_fragment_has_no_window_or_content(self):
        source = (FIX / 'BraveAdFreeCalloutDialogFragment.java').read_text()
        result = m.fragment(source)
        self.assertIn('setShowsDialog(false)', result)
        self.assertIn('dismissAllowingStateLoss()', result)
        self.assertNotIn('inflate(', result)
        self.assertNotIn('focusSearchBox', result)
        self.assertEqual(result, m.fragment(result))
        self.assertTrue(result.startswith(source[:source.index('package ')]))

    def test_anchor_changes_fail_closed(self):
        with self.assertRaises(ValueError):
            m.activity('class Unexpected {}')
        with self.assertRaises(ValueError):
            m.fragment('class Unexpected {}')

if __name__ == '__main__':
    unittest.main()
