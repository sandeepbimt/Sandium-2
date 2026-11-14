import importlib.util,unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'.circleci/scripts/audit-sandium-removal-graph.py'
spec=importlib.util.spec_from_file_location('graph',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Graph(unittest.TestCase):
 def test_each_feature_engine_rejected(self):
  for group,prefixes in m.PREFIXES.items():
   for p in prefixes:self.assertIn(group,m.violations('//brave/'+p+'/browser:engine'))
 def test_exact_metadata_only(self):
  self.assertFalse(m.violations('//brave/components/brave_wallet/common/buildflags:buildflags'))
  self.assertIn('wallet',m.violations('//brave/components/brave_wallet/common/buildflags:unexpected_engine'))
 def test_rewards_compatibility_cannot_grow_service(self):
  self.assertFalse(m.compatibility_violations('//brave/components/brave_rewards/core/pref_registry.cc',m.REWARDS_COMPAT))
  self.assertTrue(m.compatibility_violations('//brave/components/brave_rewards/core/service.cc',m.REWARDS_COMPAT))
 def test_shields_not_browser_ads(self):
  self.assertFalse(m.violations('//brave/components/brave_shields/core/browser:ad_block_service'))
if __name__=='__main__':unittest.main()
