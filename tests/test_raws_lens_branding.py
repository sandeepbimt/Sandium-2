"""Exercise adopted Lens labels through the active RawS overlay resource paths."""
import json
from pathlib import Path
import re
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import restore_only_feature as feature

CHROME = 'chrome/android/java/'
SETTINGS = CHROME + 'src/org/chromium/chrome/browser/settings/'
TOOLBAR = 'chrome/browser/ui/android/toolbar/java/res/'
GLOBAL = CHROME + 'res/values/raws_global_shield_strings.xml'
MAIN = CHROME + 'res/values/raws_main_settings_strings.xml'
ADDRESS = TOOLBAR + 'values/raws_address_controls.xml'


class LensBranding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest = json.loads((ROOT / feature.RECIPE).read_bytes())
        cls.overlay = feature.load(ROOT, manifest['baseline_fingerprint'],
                                   manifest['chromium_revision'])
        cls.entries = manifest['files']

    def source(self, path):
        digest = self.entries[path]['after_sha256']
        return (ROOT / feature.POSTIMAGES / digest).read_text()

    def test_visible_entry_points_share_lens_copy_and_stable_ids(self):
        # A partial rename can paint the panel's heading correctly while the
        # page toolbar still announces the former name on long press/TalkBack.
        values = {}
        for path in (GLOBAL, MAIN, ADDRESS):
            for element in ET.fromstring(self.source(path)).findall('string'):
                values[element.attrib['name']] = element.text
        surfaces = (
            (CHROME + 'res/layout/raws_global_shield_sheet.xml',
             'android:text="@string/raws_ui_protection"', 'raws_ui_protection', 'Sandium Lens'),
            (CHROME + 'res/layout/raws_global_shield_sheet.xml',
             'android:text="@string/raws_global_shield_settings"', 'raws_global_shield_settings',
             'Lens settings'),
            (TOOLBAR + 'layout/toolbar_phone.xml',
             'android:contentDescription="@string/raws_toolbar_shields"', 'raws_toolbar_shields',
             'Sandium Lens'),
            (TOOLBAR + 'layout/toolbar_phone.xml',
             'android:tooltipText="@string/raws_toolbar_shields"', 'raws_toolbar_shields',
             'Sandium Lens'),
            (CHROME + 'res/xml/main_preferences.xml',
             'android:title="@string/raws_ui_shields_and_privacy"', 'raws_ui_shields_and_privacy',
             'Lens & privacy'),
            (SETTINGS + 'RawsProtectionSettings.java',
             'mPageTitle.set(getString(R.string.raws_ui_shields_and_privacy));',
             'raws_ui_shields_and_privacy', 'Lens & privacy'),
            (SETTINGS + 'RawsGlobalShieldSheet.java', 'return R.string.raws_global_shield_closed;',
             'raws_global_shield_closed', 'Lens panel closed'),
            (CHROME + 'res/xml/appearance_preferences.xml',
             'android:summary="@string/raws_dark_pages_next_load"', 'raws_dark_pages_next_load',
             'Applies when a page loads. Sites can override this in Sandium Lens.'),
            (CHROME + 'src/org/chromium/chrome/browser/tabbed_mode/TabbedAppMenuPropertiesDelegate.java',
             'R.string.raws_global_shield_menu,', 'raws_global_shield_menu', 'Sandium Lens'),
        )
        for path, reference, key, label in surfaces:
            with self.subTest(path=path, reference=reference):
                self.assertIn(reference, self.source(path))
                self.assertEqual(values[key], label)
        self.assertIn('android:key="raws_ui_protection_settings"',
                      self.source(CHROME + 'res/xml/main_preferences.xml'))
        self.assertIn('<item type="id" name="raws_global_shield_menu_id" />', self.source(GLOBAL))

    def test_no_retired_sandium_product_label_in_active_resource_variants(self):
        for path in self.entries:
            if not re.search(r'^chrome/.+/res(?:_[^/]+)?/values[^/]*/[^/]+\.xml$', path):
                continue
            with self.subTest(path=path):
                self.assertNotRegex(self.source(path), r'(?i)\bsandium\s+shields?\b')


if __name__ == '__main__':
    unittest.main()
