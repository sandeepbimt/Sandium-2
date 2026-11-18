"""Source contracts for targeted lint fixes, not an Android lint execution."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class LintSemantics(unittest.TestCase):
 def read(self,p): return (ROOT/p).read_text()
 def test_menu_durable_result_preserved(self):
  s=self.read('android/java/org/chromium/chrome/browser/ui/appmenu/SandiumMenuPreferences.java')
  self.assertIn('@android.annotation.SuppressLint("ApplySharedPref")\n    boolean save',s)
  self.assertIn('if (!committed) mPreferences.edit().putString(KEY, previous).commit()',s)
  self.assertNotIn('.apply()',s)
 def test_click_is_not_dispatched_for_swipe(self):
  s=self.read('android/java/org/chromium/chrome/browser/ui/appmenu/SandiumPagedMenu.java')
  self.assertIn('if (direction != 0) page(direction);\n            else performClick();',s)
  self.assertIn('public boolean performClick() {\n        super.performClick();',s)
  self.assertEqual(s.count('public boolean performClick()'),1)
  self.assertIn('if (restoreA11yFocus)',s)
  self.assertIn('if (accessibilityTag != null)',s)
 def test_quantity_and_resource_values(self):
  s=self.read('.circleci/scripts/apply-sandium-toolbar-refinements.py')
  self.assertIn('getQuantityString(',s)
  self.assertIn('<item quantity="one">',s);self.assertIn('<item quantity="other">',s)
  self.assertNotIn('R.string.sandium_toolbar_tabs_dual_action',s)
  s=self.read('.circleci/scripts/apply-sandium-filter-bootstrap.py')
  self.assertIn('@string/sandium_refresh_filters',s)
  self.assertNotIn('android:title="Refresh filters"',s)
 def test_color_is_nontranslatable_resource(self):
  s=self.read('.circleci/features/element-corrector/android/res/values/sandium_element_colors_strings.xml')
  self.assertIn('name="sandium_element_default_hex" translatable="false">#EEEEEE',s)
if __name__=='__main__': unittest.main()
