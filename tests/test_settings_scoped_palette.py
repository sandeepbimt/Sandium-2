"""Scoped palette contracts, not a screenshot/Android rendering certification."""
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('theme',ROOT/'.circleci/scripts/apply-sandium-native-theme.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
class ScopedPalette(unittest.TestCase):
 def test_palette_has_no_shared_token_writes(self):
  xml=m.settings_palette_resource('<resources/>'.replace('/>','></resources>'))
  self.assertEqual(xml,m.settings_palette_resource(xml))
  style=ET.fromstring(xml).find('style')
  items={x.get('name'):x.text for x in style}
  self.assertEqual(items['colorSurface'],'?attr/colorSurfaceContainerLowest')
  self.assertNotIn('colorSurfaceContainerLowest',items)
  self.assertNotIn('colorPrimary',items)
  self.assertEqual(items['colorSurfaceContainerHigh'],'@color/card_background_solid')
  self.assertEqual(m.COMMON['toolbar_background_primary_dark'],'#000000')
  self.assertEqual(m.LIGHT['schemes_surface_container'],'#F3F3F3')
 def test_prior_emitted_helper_migrates_without_duplicate(self):
  original=(ROOT/'tests/fixtures/native-theme/BraveSettingsActivity.java')
  # The production test suite separately exercises the full pinned Activity.
  source='contentView.setBackgroundColor(SemanticColorUtils.getSettingsBackgroundColor(this));\n    private void onSettingsFragmentViewReady(Fragment fragment, View fragmentView) {\n        View insetView = getInsetView(fragment, fragmentView);\n        super.initializeSystemBarColors(edgeToEdgeSystemBarColorHelper);'
  fresh=m.settings_surface(source)
  start=fresh.index('            android.util.TypedValue color')
  end=fresh.index('            return getColor(R.color.container_background);',start)
  prior=fresh[:start]+fresh[end:]
  migrated=m.settings_surface(prior)
  self.assertEqual(migrated,fresh)
  self.assertEqual(migrated,m.settings_surface(migrated))
 def test_activity_ownership_and_guard(self):
  source='    @Override\n    protected void onCreate(@Nullable Bundle savedInstanceState) {'
  actual=m.settings_palette_theme(source)
  self.assertEqual(actual,m.settings_palette_theme(actual))
  self.assertLess(actual.index('super.applyThemeOverlays()'),actual.index('getTheme().applyStyle'))
  self.assertIn('night && !org.chromium.chrome.browser.theme.BraveDynamicColors.isDynamicColorsEnabled()',actual)
  self.assertNotIn('ContextUtils',actual)
 def test_native_preference_and_custom_root_coverage(self):
  # Root routing applies to top-level fragments regardless of preference implementation;
  # rounded group decoration remains restricted to native PreferenceFragmentCompat.
  self.assertIn('PreferenceFragmentCompat',m.SETTINGS_GROUPS)
  source=(ROOT/'.circleci/scripts/apply-sandium-native-theme.py').read_text()
  self.assertIn('fragment.getParentFragment() == null',source)
  self.assertIn('fragmentView.setBackgroundColor(sandiumSettingsBackground())',source)
  self.assertIn('com.google.android.material.R.attr.colorSurfaceContainerLowest',source)
 def test_menu_dark_only_and_explicit_dependency(self):
  source=(ROOT/'android/java/org/chromium/chrome/browser/ui/appmenu/SandiumPagedMenu.java').read_text()
  helper=source.split('private static int shieldsMatchedPanel',1)[1].split('// Paint-only',1)[0]
  for value in ['UI_MODE_NIGHT_YES','isDynamicColorsEnabled()','return fallback','colorSurfaceContainerLowest']:
   self.assertIn(value,helper)
  patch=(ROOT/'.circleci/scripts/apply-sandium-paged-menu.py').read_text()
  self.assertIn('//brave/browser/ui/android/theme:dynamic_colors_java',patch)
if __name__=='__main__': unittest.main()

class WelcomePalette(unittest.TestCase):
    def test_welcome_dark_canvas_matches_shields_reference_and_keeps_cards(self):
        path = ROOT / 'android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java'
        source = path.read_text()
        self.assertIn('BACKGROUND = Color.rgb(15, 12, 19)', source)
        self.assertIn('CARD = Color.rgb(26, 26, 26)', source)
        for call in ('mRoot.setBackgroundColor(BACKGROUND)', 'setStatusBarColor(BACKGROUND)',
                     'setNavigationBarColor(BACKGROUND)'):
            self.assertIn(call, source)
