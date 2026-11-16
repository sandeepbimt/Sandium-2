#!/usr/bin/env python3
import hashlib,importlib.util,json,tempfile,shutil,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def load(name):
 spec=importlib.util.spec_from_file_location(name,ROOT/'.circleci/scripts'/f'{name}.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
patch=load('apply-sandium-dark-pages');popup=load('apply-sandium-shields-popup')
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.src=Path(self.tmp.name);fixtures=ROOT/'tests/fixtures/dark-pages'
  for path,digest in json.loads((fixtures/'sha256.json').read_text()).items():
   raw=(fixtures/path).read_bytes();self.assertEqual(hashlib.sha256(raw).hexdigest(),digest)
   dest=self.src/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
  path=self.src/'brave'/patch.LAYOUT;path.write_text(popup.layout(path.read_text()))
  path=self.src/'brave'/patch.SHIELDS;path.write_text(popup.java(path.read_text()))
 def tearDown(self):self.tmp.cleanup()
 def test_full_transformation_idempotence(self):
  outputs=patch.transformations(self.src,ROOT)
  for path,text in outputs.items():path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
  self.assertEqual(outputs,patch.transformations(self.src,ROOT))
 def test_explicit_document_contract(self):
  text=patch.theme((self.src/patch.THEME).read_text())
  self.assertIn('@JniType("GURL") GURL documentUrl',text)
  self.assertIn('SandiumDarkPages.flags(webContents, documentUrl)',text)
  adapter=(ROOT/'.circleci/features/dark-pages/java/org/chromium/chrome/browser/night_mode/SandiumDarkPages.java').read_text()
  self.assertNotIn('getVisibleUrl',adapter)
 def test_pin_anchor_drift_rejected(self):
  with self.assertRaises(ValueError):patch.theme('public class Changed {}')
 def test_settings_and_independent_shields_control(self):
  outputs=patch.transformations(self.src,ROOT);xml=outputs[self.src/'brave'/patch.LAYOUT]
  root=patch.ET.fromstring(xml);button=next(n for n in root if n.get(patch.A+'id')=='@+id/sandium_dark_pages_button')
  self.assertEqual(button.get(patch.A+'minHeight'),'48dp')
  self.assertIn('getProfile()',outputs[self.src/'brave'/patch.APPEARANCE])
 def test_simplified_control_scope(self):
  ui=(ROOT/'.circleci/features/dark-pages/java/org/chromium/chrome/browser/sandium/dark/SandiumDarkPagesUi.java').read_text()
  self.assertNotIn('PRESERVE_CAPTCHA',ui)
  self.assertNotIn('PRESERVE_IMAGES',ui)
  self.assertNotIn('HEADER_CONTRAST',ui)
  adapter=(ROOT/'.circleci/features/dark-pages/java/org/chromium/chrome/browser/night_mode/SandiumDarkPages.java').read_text()
  self.assertIn('? 1 : 0',adapter)
 def test_not_pipeline_wired(self):
  pipeline=(ROOT/'.circleci/experimental-steps/product-overlay-29-0.sh').read_text()
  self.assertNotIn('apply-sandium-dark-pages.py',pipeline)
if __name__=='__main__':unittest.main()
