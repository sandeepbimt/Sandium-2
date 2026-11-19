"""Exact Brave1.100.58 / Chromium158 source replay, not native execution."""
import hashlib,json,pathlib,runpy,shutil,tempfile,unittest
R=pathlib.Path(__file__).resolve().parents[1]
S=R/'.circleci/scripts'
F=R/'tests/fixtures/upgrade1100/adblock'
class Adblock158Test(unittest.TestCase):
 def test_homepage_pin_pair_rejects_mixed_versions(self):
  from unittest.mock import patch
  from types import SimpleNamespace
  m=runpy.run_path(str(S/'apply-sandium-homepage-adblock-warmup.py'))
  vals=['v1.100.58','bd6d26d1bced03c17a98baa86d2cd3425d543d1b','d331de35ca8ab1358c7a17e4bd41627d55eaef51']
  with patch('subprocess.run',side_effect=[SimpleNamespace(stdout=v) for v in vals]):
   with self.assertRaisesRegex(RuntimeError,'Chromium pin mismatch'):
    m['verify_pin'](pathlib.Path('/unused/core'),pathlib.Path('/unused/src'))
  vals[-1]='52bdd21723d5db0c9ab11716d38feac74828cf84'
  with patch('subprocess.run',side_effect=[SimpleNamespace(stdout=v) for v in vals]):
   m['verify_pin'](pathlib.Path('/unused/core'),pathlib.Path('/unused/src'))
 def test_exact_replay_and_idempotence(self):
  with tempfile.TemporaryDirectory() as tmp:
   D=pathlib.Path(tmp);core=D/'brave'
   for row in json.loads((F/'manifest.json').read_text()):
    data=(F/row['repo']/row['path']).read_bytes()
    self.assertEqual(hashlib.sha256(data).hexdigest(),row['sha256'])
    dst=(D if row['repo']=='chromium' else core)/row['path']
    dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(data)
   names=['filter-subscriptions','filter-bootstrap','homepage-adblock-warmup','adblock-engine-race','adblock-resources','shields-two-state']
   mods={n:runpy.run_path(str(S/f'apply-sandium-{n}.py')) for n in names}
   mods['filter-subscriptions']['apply_android_sources'](core)
   mods['filter-subscriptions']['apply_android_sources'](core)
   mods['filter-bootstrap']['apply'](core)
   mods['filter-bootstrap']['apply'](core)
   mods['homepage-adblock-warmup']['apply'](core,D)
   mods['homepage-adblock-warmup']['apply'](core,D)
   a=mods['adblock-engine-race']
   for p,fn in [('components/brave_shields/content/browser/ad_block_service.h','transform_header'),('components/brave_shields/content/browser/ad_block_service.cc','transform_service_cc'),('components/brave_shields/content/test/ad_block_service_unittest.cc','transform_unit_test')]:a['write'](core/p,a[fn],fn);a['write'](core/p,a[fn],fn)
   a['verify_composed_service']((core/'components/brave_shields/content/browser/ad_block_service.cc').read_text())
   p=core/'components/brave_shields/content/test/ad_block_service_unittest.cc'
   p.write_text(a['transform_pref_test'](p.read_text()))
   mods['adblock-resources']['apply'](core)
   mods['adblock-resources']['apply'](core)
   # two-state exact transformations
   m=mods['shields-two-state']
   for p,fn in [('android/java/brave-res/values/array.xml','transform_array_xml'),('android/java/brave-res/xml/brave_privacy_preferences.xml','transform_privacy_xml'),('android/java/brave-res/layout/brave_trackers_ads_panel.xml','transform_site_layout'),('android/java/org/chromium/chrome/browser/shields/BraveUnifiedPanelHandler.java','transform_site_panel'),('android/java/org/chromium/chrome/browser/settings/BravePreferenceDialogFragment.java','transform_dialog_fragment'),('android/java/org/chromium/chrome/browser/privacy/settings/BravePrivacySettings.java','transform_privacy_settings'),('android/java/org/chromium/chrome/browser/preferences/website/BraveShieldsContentSettings.java','transform_shields_content_settings'),('components/brave_shields/core/common/brave_shields_settings_values.h','transform_native_default'),('browser/content_settings/brave_content_settings_registry_unittest.cc','transform_native_default_test')]:
    before=(core/p).read_text();after=m[fn](before);assert m[fn](after)==after;(core/p).write_text(after)

if __name__=="__main__":unittest.main()
