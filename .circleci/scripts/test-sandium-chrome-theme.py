#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest
spec = importlib.util.spec_from_file_location('chrome_theme', Path(__file__).with_name('apply-sandium-chrome-theme.py'))
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
FIXTURE = Path(__file__).resolve().parents[1] / 'tests/fixtures/theme/TopUiThemeColorProvider.java'

class ChromeThemeTests(unittest.TestCase):
    def test_pinned_transform_is_idempotent(self):
        source = FIXTURE.read_text(); new = m.transform(source)
        self.assertEqual(new, m.transform(new))
        self.assertEqual(new.replace(m.REPLACEMENT, m.ANCHOR), source)
    def test_single_shared_seam_preserves_foreground_color_pair(self):
        new = m.transform(FIXTURE.read_text())
        self.assertIn('calculateBrandedColorScheme(tab.isIncognito(), mIsDefaultColorUsed)', new)
        self.assertIn('ChromeColors.getDefaultThemeColor(mContext, tab.isIncognito())', new)
        self.assertIn('ThemeUtils.getThemedToolbarIconTint(mContext, brandedColorScheme)', new)
    def test_activity_scope_and_no_web_or_preference_mutation(self):
        self.assertIn('"ChromeTabbedActivity".equals(context.getClass().getSimpleName())', m.REPLACEMENT)
        self.assertIn('base == context', m.REPLACEMENT)
        self.assertNotIn('setThemeColor', m.REPLACEMENT)
        self.assertNotIn('writeBoolean', m.REPLACEMENT)
        self.assertNotIn('isDynamicColorsEnabled', m.REPLACEMENT)
    def test_bottom_provider_keeps_theme_pair_and_special_activities(self):
        source = FIXTURE.with_name('BottomUiThemeColorProvider.java').read_text()
        new = m.transform_bottom(source)
        self.assertEqual(new, m.transform_bottom(new))
        self.assertEqual(new.replace(m.BOTTOM_REPLACEMENT, m.BOTTOM_ANCHOR), source)
        self.assertIn('!mIncognito', m.BOTTOM_REPLACEMENT)
        self.assertIn('mIsBottomBarEnabled && sandiumRegularBrowser', new)
        self.assertIn('updatePrimaryColor(getColorForTopAnchoredToolbar(), animate)', new)
        self.assertIn('updateTint(tint, tint, getBrandedColorSchemeForTopAnchoredToolbar())', new)
        self.assertIn('SemanticColorUtils.getColorSurface(context)', new)
        self.assertNotIn('setThemeColor', m.BOTTOM_REPLACEMENT)
    def test_unknown_source_fails(self):
        with self.assertRaises(ValueError): m.transform('changed upstream source')

if __name__ == '__main__': unittest.main()
