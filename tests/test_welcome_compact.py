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
  for marker in ['setVerticalScrollBarEnabled(false)','setHorizontalScrollBarEnabled(false)','View.OVER_SCROLL_NEVER','mExpanded ? View.VISIBLE : View.GONE','Color.rgb(70, 200, 120)','allFiltersReady ? R.string.sandium_welcome_filters_ready','mContent.setPadding(dp(18), dp(6), dp(18), dp(4))']:
   self.assertIn(marker,s)
 def test_dark_policy_fresh_and_upgrade(self):
  patch=runpy.run_path(str(ROOT/'.circleci/scripts/apply-sandium-dark-pages.py'))['welcome']
  s=patch(VIEW.read_text())
  self.assertIn('mSandiumDarkPageSwitch = addSwitchRow',s)
  self.assertNotIn('mSandiumDarkPageSwitch = addRestartSwitchRow',s)
  self.assertNotIn('Applied with setup restart',s)
  self.assertIn('addRestartSwitchRow(card, "◐", "Darken transition"',s)
  self.assertIn('Needs a quick restart to apply',s)
  self.assertIn('mRequiresRestart = true;',s)
  self.assertEqual(s,patch(s))
  old=s.replace('// Setup restart applies startup-only transition choices.\n        mRequiresRestart = true;','').replace('mSandiumDarkPageSwitch = addSwitchRow','mSandiumDarkPageSwitch = addRestartSwitchRow')
  self.assertIn('mSandiumDarkPageSwitch = addSwitchRow',patch(old))
  self.assertNotIn('mSandiumDarkPageSwitch = addRestartSwitchRow',patch(old))
 def test_spare_height_belongs_to_complete_settings_groups(self):
  s=VIEW.read_text()
  build=s.split('private void buildMainSettingsCard()',1)[1].split('private void buildFilterProgressCard()',1)[0]
  self.assertIn('cardParams = matchWrap()',build)
  self.assertIn('cardParams.weight = 1f',build)
  self.assertIn('mMainSettingsCard = card',build)
  self.assertIn('updateSettingsStretch()',build)
  group=s.split('private LinearLayout addSettingGroup(',1)[1].split('private void addBlurRow(',1)[0]
  self.assertIn('group.setGravity(Gravity.CENTER_VERTICAL)',group)
  self.assertIn('parent == mMainSettingsCard',group)
  self.assertIn('params = matchWrap()',group)
  self.assertIn('float weight = mExpanded ? 0f : 1f',group)
  self.assertIn('params.weight = weight',group)
  self.assertIn('cardParams.weight = weight',group)
  self.assertNotIn('params.height = 0',group)
  switch=s.split('boolean checked, boolean showRestartHint,',1)[1].split('private void initializeSearchEngine()',1)[0]
  self.assertIn('group.addView(row, matchWrap())',switch)
  self.assertIn('group.addView(restartHint, matchWrap())',switch)
  self.assertIn('group.addView(mBlurRestartHint, matchWrap())',s)
