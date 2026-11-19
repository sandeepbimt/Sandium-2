"""Exact Brave 1.100.58 Appearance ordering and overlay replay."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import unittest
ROOT = Path(__file__).resolve().parents[1]
def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / '.circleci/scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
base = load('apply-sandium-blur-transition')
full = load('apply-sandium-page-transition-full')
class Appearance158(unittest.TestCase):
    def setUp(self):
        self.fixture = ROOT / 'tests/fixtures/appearance-158'
        self.source = (self.fixture / 'AppearancePreferences.java').read_text()
    def test_exact_pinned_blob(self):
        data = (self.fixture / 'AppearancePreferences.java').read_bytes()
        proof = json.loads((self.fixture / 'provenance.json').read_text())
        self.assertEqual(hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest(), proof['git_blob'])
        self.assertEqual(hashlib.sha256(data).hexdigest(), proof['sha256'])
    def test_base_and_full_replay_preserve_native_rows(self):
        first = base.transform_appearance_java(self.source)
        self.assertEqual(first, base.transform_appearance_java(first))
        composed = full.transform_appearance_java(first)
        self.assertEqual(composed, full.transform_appearance_java(composed))
        replayed = full.transform_appearance_java(base.transform_appearance_java(composed))
        self.assertEqual(replayed, full.transform_appearance_java(base.transform_appearance_java(replayed)))
        self.assertEqual(replayed.count(full.JAVA_DARKEN_PREF), 1)
        self.assertIn(base.JAVA_ORDER_ANCHOR_158, composed)
        self.assertNotIn('PREF_ADS_SWITCH', composed)
        method = composed.split('private void applyOrdering() {', 1)[1].split('\n    }', 1)[0]
        orders = dict(re.findall(r'setPreferenceOrder\(([^,]+), (\d+)\);', method))
        self.assertEqual(orders['PREF_GENERAL_SECTION'], '9')
        self.assertEqual(orders['PREF_BRAVE_NIGHT_MODE_ENABLED'], '10')
        self.assertEqual(orders['PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL'], '11')
        self.assertEqual(orders['PREF_SANDIUM_PAGE_TRANSITION_DARKEN'], '12')
        self.assertEqual(orders['PREF_BRAVE_DISABLE_SHARING_HUB'], '13')
        self.assertEqual(orders['PREF_SHOW_UNDO_WHEN_TABS_CLOSED'], '17')
    def test_unreviewed_ordering_rejected(self):
        with self.assertRaises(RuntimeError):
            base.transform_appearance_java(self.source.replace('PREF_BRAVE_NIGHT_MODE_ENABLED, 10', 'PREF_BRAVE_NIGHT_MODE_ENABLED, 99'))
        source = base.transform_appearance_java(self.source)
        with self.assertRaises(RuntimeError):
            full.transform_appearance_java(source.replace('PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL, 11', 'PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL, 99'))
if __name__ == '__main__':
    unittest.main()
