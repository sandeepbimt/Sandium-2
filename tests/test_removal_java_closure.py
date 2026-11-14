import importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('closure',ROOT/'.circleci/scripts/apply-sandium-removal-java-closure.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Closure(unittest.TestCase):
 def test_playlist_only_keep_rule_removed(self):
  other='-keep class example.Surviving { *; }\n'
  result=m.transform(m.PROGUARD,m.PLAYLIST_RULE+other)
  self.assertNotIn('TypeToken',result)
  self.assertIn(other,result)
  self.assertEqual(result,m.transform(m.PROGUARD,result))
  with self.assertRaises(ValueError):m.transform(m.PROGUARD,other)
 def test_proguard_reset_declared(self):
  recipe=json.loads((ROOT/'.circleci/features/removal-recipe.json').read_text())
  self.assertIn(m.PROGUARD,recipe['core_restore'])
 def test_registry_only_removed_providers(self):
  keep='                    org.chromium.chrome.browser.settings.AppearancePreferences.SEARCH_INDEX_DATA_PROVIDER,\n'
  source=''.join('                    org.chromium.chrome.browser.'+p+'.SEARCH_INDEX_DATA_PROVIDER,\n' for p in m.PROVIDERS)+keep
  result=m.transform(m.REGISTRY,source)
  self.assertIn(keep,result)
  for p in m.PROVIDERS:self.assertNotIn(p,result)
  self.assertEqual(m.transform(m.REGISTRY,result),result)
 def test_registry_missing_contract_rejected(self):
  with self.assertRaises(ValueError):m.transform(m.REGISTRY,'class Registry {}')
 def test_observer_method_only(self):
  source='class X {\n    @Override\n    public void onTermsOfServiceUpdateAccepted() { showOrHideRewardsBadge(false); }\n    public void keepShields() {}\n}'
  result=m.transform('toolbar/top/BraveToolbarLayoutImpl.java',source)
  self.assertNotIn('@Override',result);self.assertNotIn('onTermsOfServiceUpdateAccepted',result);self.assertIn('keepShields',result)
 def test_registry_reset_and_replay(self):
  recipe=json.loads((ROOT/'.circleci/features/removal-recipe.json').read_text())
  self.assertIn(m.REGISTRY,recipe['chromium_restore'])
  self.assertIn(m.REGISTRY,recipe['chromium_restore_patches'])
  self.assertTrue((ROOT/'.circleci/tests/fixtures/reporting-pinned/chromium'/m.REGISTRY).is_file())
if __name__=='__main__':unittest.main()
