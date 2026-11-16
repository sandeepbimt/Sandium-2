#!/usr/bin/env python3
"""Local Java+renderer source composition. Does not invoke CI or compile Android."""
import importlib.util,json,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
java=load('dark_java',ROOT/'.circleci/scripts/apply-sandium-dark-pages.py')
renderer=load('dark_renderer',ROOT/'.circleci/features/dark-pages/renderer/apply.py')
popup=load('dark_popup',ROOT/'.circleci/scripts/apply-sandium-shields-popup.py')
element_ui=load('element_ui',ROOT/'.circleci/features/element-corrector/android/apply.py')
manual=[load('manual_'+kind,ROOT/'.circleci/features/element-corrector'/('apply-'+kind+'-draft.py')) for kind in ['native','browser','transport']]
combined=load('combined',ROOT/'.circleci/scripts/apply-sandium-dark-combined.py')
class Composition(unittest.TestCase):
 def test_clean_compose_replay_and_contract(self):
  with tempfile.TemporaryDirectory() as t:
   src=Path(t)
   shutil.copytree(ROOT/'.circleci/features/dark-pages/renderer/fixtures',src,dirs_exist_ok=True)
   shutil.copytree(ROOT/'tests/fixtures/dark-pages',src,dirs_exist_ok=True)
   layout=src/'brave'/java.LAYOUT;layout.write_text(popup.layout(layout.read_text()))
   handler=src/'brave'/java.SHIELDS;handler.write_text(popup.java(handler.read_text()))
   initial_handler=handler.read_text()
   corrected_handler=element_ui.handler(initial_handler)
   self.assertIn('Context correctionContext = mContext;',corrected_handler)
   self.assertNotIn('Context context = mContext;',corrected_handler)
   old_handler=corrected_handler.replace('correctionContext','context')
   self.assertEqual(element_ui.handler(old_handler),corrected_handler)
   self.assertEqual(element_ui.handler(corrected_handler),corrected_handler)
   full=combined.compose(src,ROOT)
   outputs=java.transformations(src,ROOT)
   for path,text in outputs.items():path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
   element_ui.apply(src/'brave')
   self.assertIn('"//brave/android/java/'+element_ui.PACKAGE+'"', (src/'brave/build/android/config.gni').read_text().split('brave_jni_headers_sources = [',1)[1].split(']',1)[0])
   ui_expected=element_ui.plan(src/'brave')
   self.assertGreater(renderer.apply(src),0)
   self.assertEqual(renderer.apply(src),0)
   for module in manual:
    for path,text in module.compose(src).items():
     path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
   for module in manual:
    for path,text in module.compose(src).items():self.assertEqual(path.read_text(),text)
   self.assertEqual(full,combined.compose(src,ROOT))
   for path,text in full.items():self.assertEqual(path.read_text(),text)
   style=(src/'third_party/blink/renderer/core/css/resolver/style_adjuster.cc').read_text()
   self.assertLess(style.index('  ApplySandiumPaintPolicy(builder, element'),style.index('colors->Apply(element, builder)'))
   replay=java.transformations(src,ROOT)
   for path,text in replay.items(): self.assertEqual(path.read_text(),text)
   self.assertEqual(ui_expected,element_ui.plan(src/'brave'))
   with patch.object(combined.subprocess,'check_output',side_effect=[java.CHROMIUM_PIN,java.BRAVE_PIN]):
    self.assertEqual(combined.apply(src,ROOT,True),0)
   before={p:p.read_bytes() for p in src.rglob('*') if p.is_file()}
   with patch.object(combined.subprocess,'check_output',return_value='wrong'):
    with self.assertRaises(ValueError):combined.apply(src,ROOT)
   self.assertEqual(before,{p:p.read_bytes() for p in src.rglob('*') if p.is_file()})
   with patch.object(combined.subprocess,'check_output',side_effect=[java.CHROMIUM_PIN,'wrong-brave']):
    with self.assertRaises(ValueError):combined.apply(src,ROOT)
   self.assertEqual(before,{p:p.read_bytes() for p in src.rglob('*') if p.is_file()})
   real_load=combined.load
   def fail_last(name,path):
    module=real_load(name,path)
    if name=='combined_android':
     def fail(_):raise ValueError('simulated late-stage failure')
     module.plan=fail
    return module
   with patch.object(combined,'load',side_effect=fail_last):
    with self.assertRaises(ValueError):combined.compose(src,ROOT)
   self.assertEqual(before,{p:p.read_bytes() for p in src.rglob('*') if p.is_file()})
   drift=src/'brave/android/java/org/chromium/chrome/browser/sandium/dark/SandiumElementColorsUtils.java'
   drift.write_text('broken generated copy')
   with patch.object(combined.subprocess,'check_output',side_effect=[java.CHROMIUM_PIN,java.BRAVE_PIN]):
    with self.assertRaises(ValueError):combined.apply(src,ROOT,True)
   self.assertEqual(drift.read_text(),'broken generated copy')
   with patch.object(combined.subprocess,'check_output',side_effect=[java.CHROMIUM_PIN,java.BRAVE_PIN]):
    self.assertEqual(combined.apply(src,ROOT),1)
   j=(src/java.THEME).read_text()
   c=(src/'chrome/browser/android/web_contents_theme_client.cc').read_text()
   self.assertIn('sandiumDarkPageFlags(',j)
   self.assertIn('@JniType("GURL") org.chromium.url.GURL documentUrl',j)
   self.assertIn('Java_WebContentsThemeClient_sandiumDarkPageFlags',c)
   self.assertIn('document_url',c)
   self.assertIn('url/android/gurl_android.h',c)
   # Brave's derived WebPreferences retains Chromium base fields and copies them normally.
   self.assertIn('sandium_dark_page_flags', (src/'third_party/blink/public/common/web_preferences/web_preferences.h').read_text())
 def test_pipeline_uses_combined_after_existing_consumers(self):
  flow=(ROOT/'.circleci/experimental-steps/product-overlay-29-0.sh').read_text()
  self.assertNotIn('apply-sandium-dark-pages.py',flow)
  self.assertNotIn('dark-pages/renderer/apply.py',flow)
  flow=(ROOT/'.circleci/experimental-steps/product-overlay-30-0.sh').read_text()
  self.assertEqual(flow.count('python3 .circleci/scripts/apply-sandium-dark-combined.py'),2)
  self.assertLess(flow.index('apply-sandium-video-gestures.py'),flow.index('apply-sandium-dark-combined.py'))
  self.assertIn('apply-sandium-dark-combined.py "$SRC" --repo "$ROOT" --verify-only',flow)
if __name__=='__main__':unittest.main()
