#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import unittest
p=Path(__file__).with_name('apply-sandium-native-feature-map.py')
spec=importlib.util.spec_from_file_location('feature_map',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
original=(p.parents[1]/'tests/fixtures/native-feature-map/chrome_feature_list.cc').read_text()
class Tests(unittest.TestCase):
 def test_removed_native_consumers(self):
  result=m.transform(original)
  for token in ('ai_chat::','BRAVE_AI_CHAT_FLAGS','brave_rewards::','playlist::','components/ai_chat/','components/brave_news/'):
   self.assertNotIn(token,result)
 def test_origin_and_retained_features_unchanged(self):
  result=m.transform(original)
  for line in original.splitlines(True):
   if any(t in line for t in ('brave_origin','brave_shields','safe_browsing','net::features','brave_search_conversion','webcompat')):
    self.assertIn(line,result)
 def test_idempotent(self):
  result=m.transform(original);self.assertEqual(result,m.transform(result))
 def test_drift_fails_closed(self):
  with self.assertRaises(ValueError):m.transform(original+'\n')
 def test_legacy_toolbar_variants(self):
  s=(p.parents[1]/'tests/fixtures/native-feature-map/BraveAdaptiveToolbarStatePredictor.java').read_text()
  result=m.transform_predictor(s)
  self.assertNotIn('ChromeFeatureList',result)
  self.assertNotIn('BraveFeatureList',result)
  for variant in ('LEO','WALLET'):
   self.assertIn('case AdaptiveToolbarButtonVariant.'+variant+':\n                return false;',result)
  for variant in ('BOOKMARKS','HISTORY','DOWNLOADS'):
   self.assertIn('case AdaptiveToolbarButtonVariant.'+variant+':',result)
  self.assertIn('return true;',result)
  self.assertEqual(result,m.transform_predictor(result))
  with self.assertRaises(ValueError):m.transform_predictor(s+'\n')
if __name__=='__main__':unittest.main()
