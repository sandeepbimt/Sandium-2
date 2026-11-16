"""Source guard regression only; these do not replace native runtime tests."""
import pathlib,re,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class Guards(unittest.TestCase):
 def test_pinned_html_tag_symbols(self):
  # Chromium d331de35 name_style_converter.py SHA256:
  # a1e3dd43238477fc04e68485b55e2001694cf9bef5eb41438cb1772f6f014783
  # make_names.py / name_utilities.tag_symbol_for_entry preserve HTML/IFrame.
  expected=set("kAudioTag kBodyTag kButtonTag kCanvasTag kEmbedTag kFormTag kFrameTag kHTMLTag kIFrameTag kInputTag kLinkTag kMetaTag kObjectTag kOptionTag kScriptTag kSelectTag kStyleTag kTextareaTag kVideoTag".split())
  text=(ROOT/'native/sandium_element_colors.cc').read_text()
  self.assertEqual(expected,set(re.findall(r'html_names::(k\w+Tag)',text)))
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
