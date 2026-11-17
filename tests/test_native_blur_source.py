"""Pinned real-source composition checks for ordinary native-page blur."""
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
def load(name):
 s=importlib.util.spec_from_file_location(name,ROOT/'.circleci/scripts'/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
full=load('apply-sandium-page-transition-full');native=load('sandium-native-blur-source')
class NativeBlurSource(unittest.TestCase):
 def setUp(self):
  self.cc=(ROOT/'tests/fixtures/ordinary-transition/blur_transition_animation_manager.cc').read_text()
  self.h=(ROOT/'tests/fixtures/ordinary-transition/blur_transition_animation_manager.h').read_text()
 def test_real_source_and_composed_replay(self):
  cc=native.implementation(full.transform_transition_cc(self.cc))
  h=native.header(full.transform_transition_h(self.h))
  self.assertEqual(cc,native.implementation(full.transform_transition_cc(cc)))
  self.assertEqual(h,native.header(full.transform_transition_h(h)))
  self.assertIn('scoped_refptr<cc::slim::Layer> blur_layer_;',h)
  self.assertIn('native_pixels',cc)
  self.assertIn('MaybeCopyContentAreaAsBitmapSync()',cc)
 def test_no_wrong_surface_or_stretched_native_image(self):
  cc=native.implementation(full.transform_transition_cc(self.cc))
  self.assertIn('!outgoing_web && !native_pixels',cc)
  self.assertIn('native_bitmap.width() == size.width()',cc)
  self.assertIn('native_bitmap.height() == size.height()',cc)
  branch=cc.split('  if (native_pixels) {',1)[1].split('  } else {',1)[0]
  self.assertNotIn('SetSurfaceId',branch)
  self.assertNotIn('SetStretchContent',branch)
  self.assertIn('SetMasksToBounds(true)',branch)
 def test_lifecycle_and_user_intensity_unchanged(self):
  cc=native.implementation(full.transform_transition_cc(self.cc))
  for text in ['navigation_handle->IsServedFromBackForwardCache()', 'GetCurrentAnimationStage()', 'GetBlurHoldDuration()', 'GetBlurFadeOutDuration()', 'blur_layer_.reset();', 'ignore_input_scope_.reset();']:
   self.assertIn(text,cc)
  self.assertNotIn('GetBackgroundColor()',cc)
  self.assertIn('return web_contents_->GetThemeColor();',cc)
 def test_capture_is_after_eligibility_and_before_transition_ownership(self):
  cc=native.implementation(full.transform_transition_cc(self.cc))
  ready=cc.split('void BlurTransitionAnimationManager::ReadyToCommitNavigation(',1)[1]
  capture=ready.index('native_bitmap = delegate->MaybeCopyNativeContent();')
  for guard in ['IsSameDocument()', 'IsServedFromBackForwardCache()', 'GetReloadType()', 'GetCurrentAnimationStage()', 'if (!should_show_animation)']:
   self.assertLess(ready.index(guard),capture)
  self.assertLess(capture,ready.index('navigation_id_ ='))
  self.assertLess(ready.index('!outgoing_web && !native_pixels'),ready.index('navigation_id_ ='))
  self.assertNotIn('native_bitmap.getColor',cc)
  self.assertIn('SandiumNativeBlurCapture',cc)
  self.assertLess(ready.index('!navigation_handle->GetURL().SchemeIsHTTPOrHTTPS() || navigation_handle->IsPdf()'),capture)
  self.assertIn('SandiumOrdinaryBlurState',cc)
  self.assertIn('SandiumOrdinaryBlurExit',cc)
 def test_malformed_anchor_rejected(self):
  with self.assertRaises(ValueError): native.implementation(self.cc.replace('return web_contents_->GetThemeColor();','return {};'))
if __name__=='__main__':unittest.main()
