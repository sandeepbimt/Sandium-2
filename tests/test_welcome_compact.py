from pathlib import Path
import runpy, unittest
ROOT=Path(__file__).resolve().parents[1]
VIEW=ROOT/'android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java'
class WelcomeCompact(unittest.TestCase):
 def test_tracer_exactly_matches_toolbar(self):
  toolbar=(ROOT/'.circleci/scripts/apply-sandium-branding-refresh.py').read_text().split('replacement += """',1)[1].split('\n"""',1)[0]
  self.assertIn(toolbar,VIEW.read_text())
 def test_scroll_and_colors(self):
  s=VIEW.read_text()
  for marker in ['setVerticalScrollBarEnabled(false)','setHorizontalScrollBarEnabled(false)','View.OVER_SCROLL_NEVER','mExpanded ? View.VISIBLE : View.GONE','Color.rgb(70, 200, 120)','allFiltersReady ? "✓   "','mContent.setPadding(dp(18), dp(6), dp(18), dp(4))']:
   self.assertIn(marker,s)
 def test_dark_policy_fresh_and_upgrade(self):
  patch=runpy.run_path(str(ROOT/'.circleci/scripts/apply-sandium-dark-pages.py'))['welcome']
  s=patch(VIEW.read_text())
  self.assertIn('mSandiumDarkPageSwitch = addRestartSwitchRow',s)
  self.assertIn('Applied with setup restart',s)
  self.assertIn('mRequiresRestart = true;',s)
  self.assertEqual(s,patch(s))
  old=s.replace('// Setup restart applies startup-only transition choices.\n        mRequiresRestart = true;','').replace('mSandiumDarkPageSwitch = addRestartSwitchRow','mSandiumDarkPageSwitch = addSwitchRow')
  self.assertIn('mSandiumDarkPageSwitch = addRestartSwitchRow',patch(old))
