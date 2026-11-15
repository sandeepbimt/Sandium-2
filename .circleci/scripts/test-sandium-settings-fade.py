#!/usr/bin/env python3
"""Pinned source/resource contracts; not Android rendering validation."""
import importlib.util
from pathlib import Path
import unittest
import json
import xml.etree.ElementTree as ET
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def load(n):
    spec=importlib.util.spec_from_file_location(n,HERE/(n+'.py')); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
m=load('apply-sandium-settings-fade'); theme=load('apply-sandium-native-theme')
class SettingsFade(unittest.TestCase):
    def test_native_transaction_idempotence(self):
        original=(ROOT/'.circleci/tests/fixtures/settings-fade/SettingsActivity.java').read_text()
        out=m.settings(original)
        self.assertEqual(out,m.settings(out))
        self.assertNotIn('shared_x_axis_',out)
        self.assertIn('ValueAnimator.areAnimatorsEnabled()',out)
        self.assertIn('transaction.setCustomAnimations(0, 0, 0, 0)',out)
        self.assertIn('case SettingsFragment.AnimationType.TWEEN',out)
        self.assertIn('case SettingsFragment.AnimationType.PROPERTY',out)
        # Native lifecycle/back and saved-state ownership must stay byte-identical.
        self.assertEqual(original.split('    public void finishCurrentSettings(')[1],out.split('    public void finishCurrentSettings(')[1])
    def test_brave_no_double_fade(self):
        original=(ROOT/'.circleci/tests/fixtures/motion/BraveSettingsActivity.java').read_text()
        before=theme.settings_surface(theme.settings_motion(original)); out=m.brave(before)
        self.assertEqual(out,m.brave(out))
        self.assertNotIn('view.setAlpha(0f)',out)
        self.assertNotIn('view.animate()',out)
        self.assertIn('sandiumSettingsBackground()',out)
        self.assertIn('super.finish();',out)
        self.assertIn('OVERRIDE_TRANSITION_CLOSE',out)
        self.assertIn('savedInstanceState == null',out)
        self.assertIn('android.os.Build.VERSION.SDK_INT >= 34',out)
        self.assertNotIn('postDelayed',out)
        self.assertIn('startActivity(intent);\n            overridePendingTransition(sandiumFadeIn(), sandiumFadeOut());',out)
        self.assertIn('Intent.FLAG_ACTIVITY_REORDER_TO_FRONT',out)
    def test_resources_scoped_and_fast(self):
        r=m.resources(); self.assertEqual(len(r),4)
        for path,text in r.items():
            root=ET.fromstring(text)
            self.assertIn(root.tag,('alpha','objectAnimator'))
            self.assertNotIn('translate',text); self.assertNotIn('scale',text)
            duration=int(root.attrib['{http://schemas.android.com/apk/res/android}duration'])
            self.assertLessEqual(duration,120)
    def test_resource_wiring(self):
        before=(ROOT/'.circleci/tests/fixtures/settings-fade/BUILD.gn').read_text(); out=m.build(before)
        self.assertEqual(out,m.build(out))
        for path in m.resources():self.assertEqual(out.count('"'+path.removeprefix('android/')+'"'),1)
    def test_reset_and_wiring(self):
        recipe=json.loads((ROOT/'.circleci/features/removal-recipe.json').read_text())
        for key in ('chromium_restore','ui_only_chromium_restore'):
            self.assertIn(m.SETTINGS,recipe[key])
        for key in ('core_restore','ui_only_core_restore'):
            self.assertIn('android/BUILD.gn',recipe[key])
            self.assertIn(m.BRAVE_SETTINGS,recipe[key])
        self.assertNotIn(m.SETTINGS,recipe['chromium_restore_patches'])
        flow=load('flow_wiring'); flow.verify_full_wiring(ROOT)
    def test_drift_fails_closed(self):
        for fn in (m.settings,m.brave,m.build):
            with self.assertRaises(ValueError):fn('unrelated')
if __name__=='__main__':unittest.main()
