"""Pinned real-source composition checks for ordinary native-page blur."""
import importlib.util
from pathlib import Path
import unittest
import re, shutil, subprocess, tempfile
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
 def test_virtual_defaults_are_out_of_line_and_migrate_old_checkpoint(self):
  h=native.header(full.transform_transition_h(self.h))
  cc=native.implementation(full.transform_transition_cc(self.cc))
  for ret,name,body in [('SkBitmap','MaybeCopyNativeContent','return SkBitmap();'),('int','GetTopControlsHeight','return 0;')]:
   declaration=f'virtual {ret} {name}();'
   self.assertEqual(h.count(declaration),1)
   self.assertNotRegex(h,rf'virtual\s+{ret}\s+{name}\(\)\s*\{{')
   definition=f'{ret} BlurTransitionAnimationManager::WebContentsViewAndroidDelegate::\n    {name}() {{\n  {body}\n}}'
   self.assertEqual(cc.count(definition),1)
   h=h.replace(declaration,f'virtual {ret} {name}() {{ {body} }}',1)
  expected=native.header(full.transform_transition_h(self.h))
  self.assertEqual(expected,native.header(h))

 @unittest.skipUnless(shutil.which('g++') or shutil.which('clang++'),'C++ compiler unavailable')
 def test_exact_default_declarations_link_and_dispatch(self):
  h=native.header(full.transform_transition_h(self.h))
  cc=native.implementation(full.transform_transition_cc(self.cc))
  declarations='\n'.join(re.findall(r'    virtual (?:SkBitmap MaybeCopyNativeContent|int GetTopControlsHeight)\(\);',h))
  definitions=[]
  for name in ['MaybeCopyNativeContent','GetTopControlsHeight']:
   pattern=r'(?:SkBitmap|int) BlurTransitionAnimationManager::WebContentsViewAndroidDelegate::\n    '+name+r'\(\) \{[^}]+\}'
   definitions.append(re.search(pattern,cc).group())
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory)
   (root/'delegate.h').write_text('#pragma once\nnamespace content { struct SkBitmap { bool empty() const { return true; } }; class BlurTransitionAnimationManager { public: class WebContentsViewAndroidDelegate { public: virtual ~WebContentsViewAndroidDelegate() = default;\n'+declarations+'\n}; }; }\n')
   (root/'delegate.cc').write_text('#include "delegate.h"\nnamespace content {\n'+'\n'.join(definitions)+'\n}\n')
   (root/'main.cc').write_text('#include "delegate.h"\nint main() { using Delegate = content::BlurTransitionAnimationManager::WebContentsViewAndroidDelegate; Delegate d; if (!d.MaybeCopyNativeContent().empty() || d.GetTopControlsHeight() != 0) return 1; struct Override : Delegate { int GetTopControlsHeight() override { return 7; } }; Override o; Delegate& b = o; return b.GetTopControlsHeight() == 7 ? 0 : 2; }')
   compiler=shutil.which('g++') or shutil.which('clang++')
   subprocess.run([compiler,'-std=c++20','-Wall','-Wextra','-Werror',str(root/'delegate.cc'),str(root/'main.cc'),'-o',str(root/'probe')],check=True)
   subprocess.run([str(root/'probe')],check=True)

 def test_malformed_anchor_rejected(self):
  with self.assertRaises(ValueError): native.implementation(self.cc.replace('return web_contents_->GetThemeColor();','return {};'))
if __name__=='__main__':unittest.main()
