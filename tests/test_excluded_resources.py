import hashlib, importlib.util, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('excluded',ROOT/'.circleci/scripts/remove-sandium-excluded-resources.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ExcludedResourceTests(unittest.TestCase):
 def fixture(self, root):
  p=root/'android/java/brave-res/layout/unused.xml';p.parent.mkdir(parents=True);p.write_text('resource')
  gn=root/'android/BUILD.gn';gn.write_text('sources = []\n')
  e={'path':p.relative_to(root).as_posix(),'gn':'android/BUILD.gn','sha256':hashlib.sha256(b'resource').hexdigest()}
  return p,gn,e
 def test_exact_removal_replay_and_retained_resource(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p,gn,e=self.fixture(root);keep=p.with_name('retained.xml');keep.write_text('keep');m.apply(root,[e]);m.apply(root,[e]);self.assertFalse(p.exists());self.assertEqual(keep.read_text(),'keep')
 def test_declared_resource_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p,gn,e=self.fixture(root);gn.write_text('sources = [ "java/brave-res/layout/unused.xml" ]')
   with self.assertRaisesRegex(RuntimeError,'still declared'):m.apply(root,[e])
   self.assertTrue(p.exists())
 def test_drift_is_atomic(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p,gn,e=self.fixture(root);q=p.with_name('second.xml');q.write_text('unexpected');f=dict(e,path=q.relative_to(root).as_posix())
   with self.assertRaisesRegex(RuntimeError,'content drift'):m.apply(root,[e,f])
   self.assertTrue(p.exists());self.assertTrue(q.exists())
 def test_symlink_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);p,gn,e=self.fixture(root);p.unlink();p.symlink_to(root/'missing')
   with self.assertRaisesRegex(RuntimeError,'Symlink'):m.apply(root,[e])
 def test_manifest_all_reset_paths(self):
  import json
  es=json.loads(m.MANIFEST.read_text());recipe=json.loads((ROOT/'.circleci/features/removal-recipe.json').read_text())
  self.assertEqual(len(es),193)
  self.assertTrue({e['path'] for e in es}<=set(recipe['core_restore']))
  self.assertEqual(recipe['steps'][-1]['script'],'.circleci/scripts/remove-sandium-excluded-resources.py')
if __name__=='__main__':unittest.main()
