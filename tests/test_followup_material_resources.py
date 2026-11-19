"""Guard production follow-up Java resource ownership, including emitted Settings code."""
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class MaterialResourceOwnership(unittest.TestCase):
 def test_all_added_java_avoids_foreign_material_r(self):
  # Do not fabricate this foreign R in tests: Chromium generates target-owned R.
  paths=list((ROOT/'android').rglob('*.java'))+list((ROOT/'experiments').rglob('*.java'))
  for path in paths:
   if 'fixtures' in path.parts: continue
   self.assertNotIn('com.google.android.material.R',path.read_text(),str(path))
 def test_generated_settings_and_prior_helper_upgrade(self):
  spec=importlib.util.spec_from_file_location('theme',ROOT/'.circleci/scripts/apply-sandium-native-theme.py')
  theme=importlib.util.module_from_spec(spec);spec.loader.exec_module(theme)
  original=(ROOT/'.circleci/tests/fixtures/motion/BraveSettingsActivity.java').read_text()
  fresh=theme.settings_surface(original)
  self.assertNotIn('com.google.android.material.R',fresh)
  self.assertIn('import org.chromium.components.browser_ui.styles.SemanticColorUtils;',fresh)
  self.assertIn('SemanticColorUtils.getColorSurfaceContainerLowest(this)',fresh)
  start=fresh.index('            try {');end=fresh.index('\n        }',start)
  legacy='''            android.util.TypedValue color = new android.util.TypedValue();
            if (getTheme().resolveAttribute(
                    com.google.android.material.R.attr.colorSurfaceContainerLowest, color, true)) {
                return color.resourceId != 0 ? getColor(color.resourceId) : color.data;
            }
            return getColor(R.color.container_background);'''
  self.assertEqual(theme.settings_surface(fresh[:start]+legacy+fresh[end:]),fresh)
  self.assertEqual(theme.settings_surface(fresh),fresh)
 def test_same_semantic_colors_and_fallbacks(self):
  menu=(ROOT/'android/java/org/chromium/chrome/browser/ui/appmenu/SandiumPagedMenu.java').read_text()
  method=menu.split('private static int shieldsMatchedPanel',1)[1].split('// Paint-only',1)[0]
  self.assertIn('.getColorSurfaceContainerLowest(context)',method)
  self.assertIn('catch (IllegalArgumentException missingThemeAttribute)',method)
  self.assertIn('return fallback;',method)
  self.assertIn('isDynamicColorsEnabled()',method)
  self.assertIn('UI_MODE_NIGHT_YES',method)
if __name__=='__main__': unittest.main()
