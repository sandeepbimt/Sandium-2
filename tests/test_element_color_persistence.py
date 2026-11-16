"""Source contracts supplement JS fresh-document restart tests, not Android disk tests."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]/'.circleci/features/element-corrector'

class Persistence(unittest.TestCase):
 def test_normal_profile_requests_disk_flush_after_update_is_released(self):
  source=(ROOT/'native/element_color_rule_store.cc').read_text()
  self.assertIn('update->Set(key,std::move(result)); }\n    prefs_->CommitPendingWrite();', source)
  self.assertIn('update->Remove(origin.Serialize()); }\n    prefs_->CommitPendingWrite();', source)
  self.assertIn('prefs_->ClearPref(kPref); prefs_->CommitPendingWrite();', source)
 def test_origin_and_private_isolation_remain_browser_owned(self):
  source=(ROOT/'native/element_color_rule_store.cc').read_text()
  self.assertIn('prefs_(off_the_record ? nullptr : prefs)',source)
  self.assertIn('prefs_->GetDict(kPref).FindList(origin.Serialize())',source)
  self.assertNotIn('GetOriginalProfile',source)
  session=(ROOT/'native/element_color_session.cc').read_text()
  self.assertIn('auto origin=frame->GetLastCommittedOrigin()',session)
  self.assertIn('ElementColorRuleStore::ForProfile(*profile).Read(origin)',session)
 def test_locator_is_bounded_and_in_dedup_identity(self):
  source=(ROOT/'native/element_color_rule_store.cc').read_text()
  self.assertIn('steps->size()>23',source)
  self.assertIn('classes->size()>12',source)
  self.assertIn('*a.Find("locator") == *b.Find("locator")',source)
  self.assertIn('rule.size() != (locator ? 7u : 6u)',source)
 def test_no_object_serialization_order_dependency(self):
  source=(ROOT/'renderer/corrector.mjs').read_text()
  self.assertNotIn('JSON.stringify(descriptor.',source)
  self.assertIn('sameAncestors(descriptor.ancestors,rule.ancestors)',source)
  self.assertIn('sameLocator(descriptor.locator,rule.locator)',source)
if __name__=='__main__':unittest.main()
