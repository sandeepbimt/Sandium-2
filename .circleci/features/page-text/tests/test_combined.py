"""Pinned fixture end-to-end page-text composition, not Android compilation."""
import importlib.util,shutil,tempfile,unittest,json
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
combined=load('text_combined',ROOT/'.circleci/features/page-text/apply.py')
dark=load('text_dark_combined',ROOT/'.circleci/scripts/apply-sandium-dark-combined.py')
popup=load('text_popup',ROOT/'.circleci/scripts/apply-sandium-shields-popup.py')
java=load('text_dark_java',ROOT/'.circleci/scripts/apply-sandium-dark-pages.py')
class CombinedTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.src=Path(self.tmp.name)
  for p in ('.circleci/features/dark-pages/renderer/fixtures','tests/fixtures/dark-pages','.circleci/features/page-text/renderer/fixtures','.circleci/features/page-text/renderer/oopif-fixtures'):
   shutil.copytree(ROOT/p,self.src,dirs_exist_ok=True)
  layout=self.src/'brave'/java.LAYOUT;layout.write_text(popup.layout(layout.read_text()))
  handler=self.src/'brave'/java.SHIELDS;handler.write_text(popup.java(handler.read_text()))
  for path,text in dark.compose(self.src,ROOT).items():path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
 def snapshot(self):return {p:p.read_bytes() for p in self.src.rglob('*') if p.is_file()}
 def test_full_compose_replay_and_native_before_controls(self):
  original=self.snapshot();outputs=combined.compose(self.src,ROOT)
  self.assertEqual(original,self.snapshot())
  for path,text in outputs.items():path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
  self.assertEqual(outputs,combined.compose(self.src,ROOT))
  doc=(self.src/'third_party/blink/renderer/core/dom/document.cc').read_text()
  self.assertIn('text-size-adjust:',doc);self.assertIn('Url().IsAboutSrcdocUrl()',doc)
  font=(self.src/'third_party/blink/renderer/core/css/resolver/font_builder.cc').read_text()
  self.assertNotIn('SandiumPageText',font)
  panel=(self.src/'brave'/java.SHIELDS).read_text();self.assertNotIn('SandiumPageTextUi',panel)
 def test_interrupted_write_recovers_without_duplicate_layers(self):
  expected=combined.compose(self.src,ROOT)
  for index,(path,text) in enumerate(expected.items()):
   if index%2==0:
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
  self.assertEqual(expected,combined.compose(self.src,ROOT))
 def test_atomic_late_failure(self):
  path=self.src/'content/browser/renderer_host/page_impl.h';path.write_text('bad pin')
  before=self.snapshot()
  with self.assertRaises(ValueError):combined.compose(self.src,ROOT)
  self.assertEqual(before,self.snapshot())
 def test_pin_verify_and_apply_readback(self):
  manifest=json.loads((ROOT/'.circleci/features/page-text/integration-plan.json').read_text())
  pins=[manifest['chromium_pin'],manifest['brave_pin']]
  before=self.snapshot()
  with patch.object(combined.subprocess,'check_output',return_value='wrong'):
   with self.assertRaises(ValueError):combined.apply(self.src,ROOT)
  self.assertEqual(before,self.snapshot())
  with patch.object(combined.subprocess,'check_output',side_effect=pins):
   self.assertGreater(combined.apply(self.src,ROOT),0)
  with patch.object(combined.subprocess,'check_output',side_effect=pins):
   self.assertEqual(combined.apply(self.src,ROOT,True),0)
  with patch.object(combined.subprocess,'check_output',side_effect=pins):
   self.assertEqual(combined.apply(self.src,ROOT),0)
if __name__=='__main__':unittest.main()
