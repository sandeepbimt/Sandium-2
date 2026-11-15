"""Source guard regression only; these do not replace native runtime tests."""
import pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class Guards(unittest.TestCase):
 def test_preview_document_guard(self):
  text=(ROOT/'native/element_color_renderer.cc').read_text().split('void ElementColorRenderer::PreviewColor(',1)[1].split('bool ElementColorRenderer::DescriptorMatches',1)[0]
  self.assertIn('found->second.GetDocument()==document_',text)
 def test_cleanup_uses_captured_document(self):
  text=(ROOT/'native/element_color_renderer.cc').read_text().split('void ElementColorRenderer::Reset(',1)[1].split('void ElementColorRenderer::ReadyToCommitNavigation',1)[0]
  self.assertIn('document_.DocumentElement()',text)
  self.assertNotIn('pair.second.Sandium',text)
 def test_begin_reentrant_lifetime_guard(self):
  text=(ROOT/'native/element_color_session.cc').read_text().split('bool ElementColorSession::Begin(',1)[1].split('bool ElementColorSession::OfferSelection',1)[0]
  self.assertLess(text.index('lifetime_factory_.GetWeakPtr()'),text.index('Cancel();'))
  self.assertIn('if(!alive || begin_generation_!=generation)return false;',text)
 def test_native_commit_revalidates_descriptor(self):
  text=(ROOT/'native/element_color_renderer.cc').read_text().split('void ElementColorRenderer::CommitColor(',1)[1].split('void ElementColorRenderer::ClearColorRules',1)[0]
  self.assertIn('DescriptorMatches(id,found->second)',text)
 def test_private_store_never_receives_pref_service(self):
  text=(ROOT/'native/element_color_rule_store.cc').read_text()
  self.assertIn('prefs_(off_the_record ? nullptr : prefs)',text)
  self.assertNotIn('GetOriginalProfile',text)
if __name__=='__main__':unittest.main()
