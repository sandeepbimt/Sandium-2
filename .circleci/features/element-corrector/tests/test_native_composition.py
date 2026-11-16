import importlib.util,pathlib,tempfile,unittest,shutil
FEATURE=pathlib.Path(__file__).resolve().parents[1]
REPO=FEATURE.parents[2]
spec=importlib.util.spec_from_file_location('draft', FEATURE/'apply-native-draft.py')
draft=importlib.util.module_from_spec(spec);spec.loader.exec_module(draft)
class Composition(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=pathlib.Path(self.tmp.name)
  shutil.copytree(REPO/'native-pinned'/'third_party',self.root/'third_party')
  # A synthetic prerequisite anchor isolates this transform's source behavior.
  # Full palette composition/compilation must run separately in integration.
  path=self.root/'third_party/blink/renderer/core/css/resolver/style_adjuster.cc'
  text=path.read_text().replace('\n}\n\nbool StyleAdjuster::IsCacheCompatible(',
    '\n  ApplySandiumPaintPolicy(builder, element, element_or_pseudo_element, parent_style);\n}\n\nbool StyleAdjuster::IsCacheCompatible(',1)
  path.write_text(text)
 def test_hooks_and_idempotence(self):
  edits=draft.compose(self.root)
  self.assertEqual(len(edits),9)
  for path,data in edits.items():path.write_text(data)
  self.assertEqual(edits,draft.compose(self.root))
  s=(self.root/'third_party/blink/renderer/core/dom/element.cc').read_text()
  self.assertIn('colors->Remove(*this)',s)
  self.assertIn('colors->Apply(element, builder)',(self.root/'third_party/blink/renderer/core/css/resolver/style_adjuster.cc').read_text())
 def test_rejects_missing_palette_prerequisite(self):
  path=self.root/'third_party/blink/renderer/core/css/resolver/style_adjuster.cc'
  path.write_text(path.read_text().replace('  ApplySandiumPaintPolicy(builder, element, element_or_pseudo_element, parent_style);',''))
  with self.assertRaises(ValueError):draft.compose(self.root)
 def test_missing_anchor_changes_nothing(self):
  target=self.root/'third_party/blink/renderer/core/BUILD.gn';target.write_text('unexpected source')
  before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
  with self.assertRaises(ValueError):draft.compose(self.root)
  self.assertEqual(before,{p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
if __name__=='__main__':unittest.main()
