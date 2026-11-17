"""Coherent native-inset migration/replay; no device paint/navigation claim."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
def load(name):
 spec=importlib.util.spec_from_file_location(name,ROOT/'.circleci/scripts'/(name+'.py'))
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
native=load('apply-sandium-native-insets')
scroll=load('apply-sandium-scroll-status-bar')
flow=load('flow_wiring')
class NativeInsetsProduct(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name)
  for name,relative in scroll.FILES.items():
   path=self.root/relative;path.parent.mkdir(parents=True,exist_ok=True)
   path.write_text((ROOT/'.circleci/tests/fixtures/status-bar'/name).read_text())
  controller=self.root/'chrome/android/java/src/org/chromium/chrome/browser/ui/system/StatusBarColorController.java'
  controller.parent.mkdir(parents=True,exist_ok=True)
  controller.write_text((ROOT/'.circleci/tests/fixtures/opaque-status/StatusBarColorController.java').read_text())
 def snapshot(self):return {p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
 def test_native_input_exact_and_repeat(self):
  before=self.snapshot();native.apply(self.root);native.apply(self.root,True)
  for path,original in before.items():
   self.assertEqual(path.read_text(),native.paint.transform(str(path.relative_to(self.root)),original.decode()))
  self.assertEqual(set(native.plan(self.root)),set(before))
 def test_full_old_overlay_and_trace_removed_preserves_other_features(self):
  scroll.apply(self.root)
  traced=self.root/native.trace.PATH
  traced.write_text(native.trace.transform(traced.read_text()))
  unrelated=self.root/'navigation-unrelated.cc';unrelated.write_text('Sandium Back/cache/blur stays\n')
  toolbar=self.root/scroll.FILES['ToolbarPositionController.java']
  toolbar.write_text(toolbar.read_text()+'\n// unrelated address customization\n')
  native.apply(self.root);native.apply(self.root,True)
  for name,relative in scroll.FILES.items():
   expected=(ROOT/'.circleci/tests/fixtures/status-bar'/name).read_text()
   if name=='ToolbarPositionController.java':expected+='\n// unrelated address customization\n'
   self.assertEqual((self.root/relative).read_text(),native.paint.transform(relative,expected),name)
  self.assertEqual(unrelated.read_text(),'Sandium Back/cache/blur stays\n')
  first=self.snapshot();native.apply(self.root);self.assertEqual(first,self.snapshot())
 def test_disabled_old_overlay_also_restores_completely(self):
  scroll.apply(self.root,enabled=False)
  native.apply(self.root);native.apply(self.root,True)
  for name,relative in scroll.FILES.items():
   self.assertEqual((self.root/relative).read_text(),native.paint.transform(relative,(ROOT/'.circleci/tests/fixtures/status-bar'/name).read_text()))
 def test_old_native_comparison_gradient_removed(self):
  scroll.apply(self.root)
  for p,text in native.native.plan(self.root).items():p.write_text(text)
  self.assertIn(native.native.MARKER,(self.root/scroll.FILES['EdgeToEdgeBaseLayout.java']).read_text())
  native.apply(self.root)
  for name,relative in scroll.FILES.items():
   self.assertEqual((self.root/relative).read_text(),native.paint.transform(relative,(ROOT/'.circleci/tests/fixtures/status-bar'/name).read_text()))
 def test_late_invalid_anchor_and_verify_never_write(self):
  scroll.apply(self.root)
  before=self.snapshot()
  with self.assertRaises(RuntimeError):native.apply(self.root,True)
  self.assertEqual(before,self.snapshot())
  p=self.root/scroll.FILES['ToolbarPositionController.java']
  p.write_text(p.read_text().replace('consumeTopInset = false;','consumeTopInset = unknown;'))
  before=self.snapshot()
  with self.assertRaises(RuntimeError):native.apply(self.root)
  self.assertEqual(before,self.snapshot())
 def test_late_paint_failure_writes_no_geometry(self):
  scroll.apply(self.root)
  controller=self.root/'chrome/android/java/src/org/chromium/chrome/browser/ui/system/StatusBarColorController.java'
  controller.write_text(controller.read_text().replace('private int calculateBaseStatusBarColor()', 'private int changedCalculateBaseStatusBarColor()'))
  # Break a real reviewed paint anchor, not just a method name it may not match.
  row=next(row for row in native.paint.CHANGES if row[0].endswith('StatusBarColorController.java'))
  controller.write_text(controller.read_text().replace(row[1],'// unknown replacement of paint anchor',1))
  before=self.snapshot()
  with self.assertRaises(RuntimeError):native.apply(self.root)
  self.assertEqual(before,self.snapshot())
 def test_partial_write_resume_and_source_reset_ownership(self):
  scroll.apply(self.root)
  intended=native.plan(self.root)
  for index,(path,text) in enumerate(intended.items()):
   if index%2==0:path.write_text(text)
  native.apply(self.root);native.apply(self.root,True)
  self.assertEqual({p:p.read_text() for p in intended},intended)
  import json
  recipe=json.loads((ROOT/'.circleci/features/removal-recipe.json').read_text())
  for key in ['chromium_restore','ui_only_chromium_restore']:
   for path in native.paint.PAINT_PATHS:self.assertIn(path,recipe[key])
 def test_active_pipeline_never_installs_underlap_or_full_native_profile(self):
  flow.verify_product_wrappers(ROOT)
  text=(ROOT/'.circleci/experimental-steps/product-overlay-29-0.sh').read_text()
  self.assertNotIn('apply-sandium-scroll-status-bar.py',text)
  self.assertIn('apply-sandium-native-insets.py "$SRC" --verify-only',text)
  late=(ROOT/'.circleci/experimental-steps/product-overlay-30-0.sh').read_text()
  self.assertNotIn('trace-sandium-back-geometry.py',late)
  self.assertIn('apply-sandium-native-insets.py "$SRC"\n',late)
  self.assertIn('apply-sandium-native-insets.py "$SRC" --verify-only',late)
  import json
  self.assertFalse(json.loads((ROOT/'experiments/native-navigation/profile.json').read_text())['enabled'])
if __name__=='__main__':unittest.main()
