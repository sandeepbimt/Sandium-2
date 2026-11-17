from pathlib import Path
import unittest, importlib.util
ROOT=Path(__file__).resolve().parents[1]
class MenuFit(unittest.TestCase):
 def test_bounded_empty_cells_and_stable_sheet(self):
  s=(ROOT/'android/java/org/chromium/chrome/browser/ui/appmenu/SandiumPagedMenu.java').read_text()
  self.assertNotIn('weighted(line, new View',s)
  self.assertIn('int preferredHeight(int width, int available)',s)
  self.assertNotIn('mBody.measure(exactWidth',s)
  self.assertIn('Math.min(available, dp(8 + 48 + 24)',s)
  self.assertIn('new LinearLayout.LayoutParams(0, 1, 1)',s)
 def test_editor_tile_keeps_target_and_native_dispatch(self):
  s=(ROOT/'android/java/org/chromium/chrome/browser/ui/appmenu/SandiumPagedMenu.java').read_text()
  self.assertIn('Math.max(dp(48), dp(26 + 2 + 4 + 4) + labelHeight())',s)
  self.assertIn('weighted(line, tile)',s)
  self.assertIn('mDraft.show(key)',s); self.assertIn('mDraft.hide(key)',s)
  self.assertIn('ScrollView scroll = new ScrollView',s)
 def test_home_action_in_live_and_customization_models(self):
  spec=importlib.util.spec_from_file_location('home',ROOT/'.circleci/scripts/apply-sandium-home-shortcuts.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  original=(ROOT.parent/'brave-core-audit/android/java/org/chromium/chrome/browser/tabbed_mode/BraveTabbedAppMenuPropertiesDelegate.java').read_text()
  out=m.delegate(original);self.assertEqual(out,m.delegate(out))
  live=out[out.index('public MVCListAdapter.ModelList buildMenuModelList()'):out.index('private void populateBravePageModeMenu')]
  self.assertIn('R.id.sandium_add_home_shortcut',live)
  self.assertIn('sandiumAddHomeModel.set(AppMenuItemProperties.ENABLED, sandiumCanAddHome)',live)
  self.assertIn('!sandiumHomeTab.isIncognito()',live)
  self.assertIn('"https".equals',live);self.assertIn('"http".equals',live)
if __name__=='__main__':unittest.main()
