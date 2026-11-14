import importlib.util,unittest,tempfile,hashlib
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
 def test_lookalike_compatibility_path_rejected(self):
  self.assertTrue(m.compatibility_violations('//brave/components/evil/pref_registry.cc',m.REWARDS_COMPAT))
  self.assertIn('rewards_ads',m.violations('//brave/components/services/bat_ads:service'))
 def test_protocol_targets_are_exact(self):
  for target in m.PROTOCOL_TARGETS:
   self.assertFalse(m.violations(target))
   self.assertTrue(m.violations(target+'__engine'))
  self.assertTrue(m.violations('//brave/components/brave_ads/core/browser/service:implementation'))
  self.assertFalse(m.violations('//brave/components/brave_news/common/buildflags:buildflags'))
 def test_source_manifest_drift_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'protocol.mojom').write_text('module example;')
   manifest={'schema':1,'files':{'protocol.mojom':hashlib.sha256((root/'protocol.mojom').read_bytes()).hexdigest()}}
   self.assertEqual(m.verify_compatibility_sources(root,manifest),['protocol.mojom'])
   (root/'protocol.mojom').write_text('changed')
   with self.assertRaises(ValueError):m.verify_compatibility_sources(root,manifest)
 def test_sponsored_ntp_implementation_forbidden(self):
  self.assertIn('rewards_ads',m.violations('//brave/browser/ui/webui/new_tab_takeover/android:new_tab_takeover'))
  self.assertTrue(m.sponsored_source_violations('//brave/components/ntp_background_images/browser/sponsored_content/ntp_sponsored_images_component_installer.cc'))
  self.assertFalse(m.sponsored_source_violations('//brave/components/ntp_background_images/browser/ntp_background_images_component_installer.cc'))
 def test_shields_not_browser_ads(self):
  self.assertFalse(m.violations('//brave/components/brave_shields/core/browser:ad_block_service'))
if __name__=='__main__':unittest.main()
