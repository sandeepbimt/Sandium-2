"""Paint and lifecycle source contracts; Android visual/runtime validation remains required."""
from pathlib import Path
import importlib.util
import unittest
import xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parents[1]
def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'.circleci/scripts'/('apply-sandium-'+name+'.py'))
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result); return result
class PopupRimMotion(unittest.TestCase):
    def test_shields_rim_preserves_shadow_and_theme(self):
        m = module('shields-popup')
        original = '''<layer-list xmlns:android="http://schemas.android.com/apk/res/android"><!-- License retained -->
        <item android:top="@dimen/app_menu_shadow_length" android:bottom="@dimen/app_menu_shadow_length"><shape><solid android:color="?attr/colorSurfaceContainerLowest"/><corners android:radius="28dp"/></shape></item></layer-list>'''
        actual = m.raised_panel(original)
        self.assertEqual(actual, m.raised_panel(actual))
        self.assertIn('License retained', actual)
        root = ET.fromstring(actual)
        self.assertEqual(root[0].get(m.A+'top'), '@dimen/app_menu_shadow_length')
        layers = root[0][0]
        self.assertEqual(len(layers),7)
        self.assertEqual(layers[-1][0].find('solid').get(m.A+'color'), '?attr/colorSurfaceContainerLowest')
        self.assertEqual([g.get(m.A+'startColor') for g in root.iter('gradient')], ['#507D8085','#287D8085','#107D8085'])
    def test_prior_popup_motion_migrates_once(self):
        m=module('paged-menu')
        prior='before\n'+m.LEGACY_POPUP_MOTION+'after\n'
        actual=m.migrate_popup_motion(prior)
        self.assertEqual(actual,'before\n'+m.POPUP_MOTION+'after\n')
        self.assertEqual(actual,m.migrate_popup_motion(actual))
    def test_menu_one_outer_motion_owner_and_native_back(self):
        s=(ROOT/'.circleci/scripts/apply-sandium-paged-menu.py').read_text()
        self.assertIn('org.chromium.ui.R.style.AnchoredPopupAnimEndBottom',s)
        self.assertIn('SysUtils.isLowEndDevice() || !ValueAnimator.areAnimatorsEnabled()',s)
        self.assertIn('popup.setEnterTransition(null)',s)
        self.assertIn('popup.setExitTransition(null)',s)
        self.assertNotIn('new android.transition.Fade',module('paged-menu').POPUP_MOTION)
        self.assertIn('!mSandiumMenu.handleBack()) dismiss()',s)
    def test_shared_root_and_internal_motion_unchanged(self):
        s=(ROOT/'android/java/org/chromium/chrome/browser/ui/appmenu/SandiumPagedMenu.java').read_text()
        self.assertEqual(s.count('setBackground(raisedPanel(mPanelColor, 16))'),1)
        self.assertNotIn('mEntranceAnimator',s)
        self.assertIn('PADDING_MODE_STACK',s)
        self.assertIn('finishPanelMotion(); finishPageMotion();',s)
        self.assertIn('setDuration(180)',s)
        self.assertIn('setDuration(120)',s)
if __name__=='__main__': unittest.main()
