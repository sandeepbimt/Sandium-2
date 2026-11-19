#!/usr/bin/env python3
import importlib.util,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[2]
def load(name,p):
 s=importlib.util.spec_from_file_location(name,R/p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
popup=load('popup','.circleci/scripts/apply-sandium-shields-popup.py')
dark=load('dark','.circleci/scripts/apply-sandium-dark-pages.py')
element=load('element','.circleci/features/element-corrector/android/apply.py')
class Groups(unittest.TestCase):
 def test_three_groups_and_repeat_composition(self):
  base=(R/'tests/fixtures/dark-pages/brave'/popup.LAYOUT).read_text()
  out=element.layout(dark.layout(popup.layout(base)))
  root=element.ET.fromstring(out);A=element.A
  def byid(n):return next(e for e in root.iter() if e.get(A+'id')=='@+id/'+n)
  appearance=byid('sandium_appearance_group'); controls=byid('advanced_options_content')
  self.assertEqual([e.get(A+'id') for e in appearance if e.get(A+'id')],['@+id/sandium_dark_pages_button','@+id/sandium_element_colors_button'])
  self.assertEqual(appearance[0].tag,'androidx.appcompat.widget.SwitchCompat')
  self.assertEqual([e.get(A+'id') for e in controls[0] if e.get(A+'id')],['@+id/trackers_item','@+id/block_element_item','@+id/clear_blocked_elements_divider','@+id/clear_blocked_elements_button'])
  self.assertEqual([e.get(A+'id') for e in byid('sandium_cookies_group') if e.get(A+'id')],['@+id/cookies_item','@+id/shred_data_item'])
  self.assertEqual([root[i].get(A+'id') for i in (1,2,3)],['@+id/advanced_options_content','@+id/sandium_appearance_group','@+id/sandium_cookies_group'])
  hidden=next(e for e in root if e.get(A+'importantForAccessibility')=='noHideDescendants')
  self.assertIn(byid('shields_toggle_switch'), list(hidden.iter()))
  self.assertEqual(byid('sandium_shields_panel_mark').get(A+'src'),'@drawable/sandium_toolbar_mark')
  self.assertEqual(element.layout(dark.layout(out)),out)
  self.assertNotIn(appearance,list(controls)) # appearance works even when Shields off
 def test_toggle_live_binding_not_dialog(self):
  base=(R/'tests/fixtures/dark-pages/brave'/popup.JAVA).read_text()
  out=element.handler(dark.shields(popup.java(base)))
  self.assertIn('bindSiteToggle(',out);self.assertNotIn('SandiumDarkPagesUi.showSite(',out)
  self.assertIn('.enabled(selectedTab.getWebContents(), selectedTab.getUrl())',out)
  self.assertEqual(dark.shields(out),out)
 def test_policy_save_then_reload_and_safe_failure(self):
  s=(R/'.circleci/features/dark-pages/java/org/chromium/chrome/browser/sandium/dark/SandiumDarkPagesUi.java').read_text().split('private static final int[] LABELS')[0]
  self.assertIn('checked ? Choice.ON : Choice.OFF',s)
  self.assertLess(s.index('SandiumDarkPages.set('),s.index('tab.reload()'))
  self.assertIn('correct.setEnabled(checked)',s)
  self.assertIn('if (!current(tab, profile, origin))',s)
  self.assertIn('catch (IllegalStateException failure)',s)
  self.assertNotIn('clearSite',s);self.assertNotIn('clearRules',s)
if __name__=='__main__':unittest.main()
