"""Pinned-source transformation tests, not Android runtime/compile tests."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('back', ROOT/'.circleci/scripts/apply-sandium-back-transition.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class BackTransition(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'src'
        shutil.copytree(ROOT/'tests/fixtures/back-transition',self.root)
    def test_pinned_application_and_idempotence(self):
        first=m.plan(self.root)
        for p,s in first.items():p.write_text(s)
        self.assertEqual(first,m.plan(self.root))
    def test_unknown_source_rejected_before_write(self):
        rel,old,_=m.CHANGES[-1];p=self.root/rel;p.write_text(p.read_text().replace(old,old+'changed',1).replace('return ChromeColors', 'return OtherColors'))
        # Make the exact pinned Java method unavailable.
        p.write_text(p.read_text().replace('getBackForwardTransitionFallbackUXPageBackgroundColor()', 'unknown()'))
        before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with self.assertRaises(RuntimeError):m.plan(self.root)
        self.assertEqual(before,{p:p.read_bytes() for p in before})
    def test_duplicate_old_and_new_rejected(self):
        with self.assertRaises(RuntimeError):m.transform('new\nold', 'old', 'new')
    def test_valid_screenshot_and_motion_preserved(self):
        result=m.plan(self.root)
        for p,s in result.items():
            if p.name=='back_forward_transition_animator.cc':
                for region in ['void BackForwardTransitionAnimator::SetupForScreenshotPreview(', 'void BackForwardTransitionAnimator::OnGestureProgressed(']:
                    orig=p.read_text();start=orig.index(region);end=orig.index('\n}\n',start)+3
                    self.assertIn(orig[start:end],s)
                self.assertIn('ResetTransformForLayer(screenshot_layer_.get());',s)
                self.assertIn('SandiumBackPreviewSelection',s)
                self.assertIn('SandiumBackHandoffState',s)
    def test_capture_guards_and_both_navigation_types(self):
        texts='\n'.join(m.plan(self.root).values())
        self.assertEqual(texts.count('SandiumCapturePageBackground(navigation_request, last_committed_entry);'),2)
        for guard in ['request.IsInPrimaryMainFrame()', 'GetParentOrOuterDocumentOrEmbedder()', 'frame->GetLastCommittedURL() != entry->GetURL()', 'SkColorGetA(*color) == 255', 'entry->GetPageType() != PAGE_TYPE_NORMAL']:
            self.assertIn(guard,texts)
        self.assertIn('frame->GetPage().background_color()',texts)
        self.assertNotIn('view->GetBackgroundColor()',texts)
        self.assertIn('destination_entry->navigation_transition_data()\n                                .sandium_page_background()',texts)
    def test_fixture_pin_provenance_and_no_persistent_storage(self):
        self.assertEqual(m.CHROMIUM_SHA,'d331de35ca8ab1358c7a17e4bd41627d55eaef51')
        for _,_,new in m.CHANGES:
            self.assertNotIn('SetExtraData',new)
            self.assertNotIn('PrefService',new)
if __name__=='__main__':unittest.main()
