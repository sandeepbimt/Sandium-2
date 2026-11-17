"""Exact source reversal. Not a claim of Android/device verification."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
native=load('native_status',ROOT/'.circleci/scripts/native-status-geometry.py')
scroll=load('scroll_status',ROOT/'.circleci/scripts/apply-sandium-scroll-status-bar.py')
class NativeStatus(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  for name,path in scroll.FILES.items():
   p=self.root/path;p.parent.mkdir(parents=True,exist_ok=True)
   p.write_text(scroll.transform(name,(ROOT/'.circleci/tests/fixtures/status-bar'/name).read_text()))
 def test_exact_native_geometry_and_paint_only(self):
  result=native.plan(self.root)
  for name,path in scroll.FILES.items():
   original=(ROOT/'.circleci/tests/fixtures/status-bar'/name).read_text()
   expected=original
   for old,new in native.PAINT.get(path,[]):expected=expected.replace(old,new,1)
   self.assertEqual(result[self.root/path],expected,name)
  toolbar=result[self.root/scroll.FILES['ToolbarPositionController.java']]
  self.assertNotIn('consumeTopInset = false;',toolbar)
  controller=result[self.root/scroll.FILES['EdgeToEdgeControllerImpl.java']]
  self.assertNotIn('Sandium',controller)
  paint=result[self.root/scroll.FILES['EdgeToEdgeBaseLayout.java']]
  self.assertIn('canvas.drawRect(mStatusBarRect, mSandiumTopProtectionPaint);',paint)
  self.assertNotIn('canvas.drawRect(0, 0, getWidth()',paint)
  inset=result[self.root/scroll.FILES['InsetObserver.java']]
  self.assertNotIn('mSandiumTopInsetForEdgeToEdge',inset)
 def test_repeat_and_preserve_unrelated_change(self):
  path=self.root/scroll.FILES['BrowserControlsManager.java'];path.write_text(path.read_text()+'\n// Unrelated customization retained.\n')
  first=native.plan(self.root)
  for p,s in first.items():p.write_text(s)
  self.assertEqual(first,native.plan(self.root))
  self.assertTrue(first[path].endswith('// Unrelated customization retained.\n'))
 def test_unknown_overlap_fails_without_writes(self):
  path=self.root/scroll.FILES['ToolbarPositionController.java'];path.write_text(path.read_text().replace('consumeTopInset = false;','consumeTopInset = unexpected;'))
  before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
  with self.assertRaises(RuntimeError):native.plan(self.root)
  self.assertEqual(before,{p:p.read_bytes() for p in before})
 def test_identifier_free_residual_bottom_override_rejected(self):
  name='ToolbarPositionController.java';path=self.root/scroll.FILES[name]
  original=(ROOT/'.circleci/tests/fixtures/status-bar'/name).read_text()
  path.write_text(original.replace('// Exits early if the top padding', 'consumeTopInset = false;\n        // Exits early if the top padding',1))
  before=path.read_text()
  with self.assertRaises(RuntimeError):native.plan(self.root)
  self.assertEqual(before,path.read_text())
 def test_native_input_supported_and_no_writer_or_wrapper(self):
  for name,path in scroll.FILES.items():
   (self.root/path).write_text((ROOT/'.circleci/tests/fixtures/status-bar'/name).read_text())
  result=native.plan(self.root)
  self.assertEqual(set(result),{self.root/p for p in scroll.FILES.values()})
  source=(ROOT/'.circleci/scripts/native-status-geometry.py').read_text();self.assertNotIn('.write_text(',source)
if __name__=='__main__':unittest.main()
