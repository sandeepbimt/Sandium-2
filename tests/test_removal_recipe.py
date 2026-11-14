import importlib.util,tempfile,unittest,json
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'.circleci/scripts/sandium-removal-recipe.py'
spec=importlib.util.spec_from_file_location('removal',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Recipe(unittest.TestCase):
 def test_composition_gate_precedes_actual_apply(self):
  script=(P.parents[1]/'experimental-steps/product-overlay-30-0.sh').read_text()
  self.assertLess(script.index('test-sandium-removal-composition.py'),script.index('sandium-removal-recipe.py'))
  self.assertIn('--source "$CORE"',script)
 def test_gn_preserves_toolchain_and_import(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'args.gn').write_text('import("args_generated.gni")\nuse_siso = true\nenable_brave_wallet = true\n')
   recipe={'gn_args':{'enable_brave_wallet':False,'enable_playlist':False}}
   m.configure_gn(recipe,p);first=(p/'args.gn').read_text();m.configure_gn(recipe,p)
   self.assertEqual(first,(p/'args.gn').read_text());self.assertIn('use_siso = true',first);self.assertIn('import(',first);self.assertEqual(first.count('enable_brave_wallet = false'),1)
 def test_unsafe_manifest_path_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'m.json';p.write_text(json.dumps({'schema':1,'groups':list(range(13)),'core_restore':['../escape'],'chromium_restore':[]}))
   with self.assertRaises(ValueError):m.load(p)
 def test_missing_gn_not_created(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):m.configure_gn({'gn_args':{}},Path(d))
if __name__=='__main__':unittest.main()
