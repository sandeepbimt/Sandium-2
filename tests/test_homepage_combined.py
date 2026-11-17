import importlib.util
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('combinedhome',ROOT/'.circleci/scripts/apply-sandium-homepage-combined.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class CombinedHome(unittest.TestCase):
 def fixture(self,root):
  for patch in m.backing.PATCHES:
   p=root/patch['path'];p.parent.mkdir(parents=True,exist_ok=True)
   p.write_text((ROOT/'tests/fixtures/homepage-backing'/p.name).read_text())
  for name,_,_ in m.paint.CHANGES:
   p=root/m.paint.BASE/name;p.parent.mkdir(parents=True,exist_ok=True)
   p.write_text((ROOT/'tests/fixtures/homepage-surround'/name).read_text())
 def test_combined_replay(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);self.fixture(root);planned=m.compose(root)
   for p,s in planned.items():p.write_text(s)
   self.assertEqual(planned,m.compose(root))
 def test_broken_paint_never_partially_writes_owner(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);self.fixture(root)
   (root/m.paint.BASE/'ToolbarPhone.java').write_text('wrong source')
   before={p:p.read_bytes() for p in root.rglob('*.java')}
   with self.assertRaises(RuntimeError):m.compose(root)
   self.assertEqual(before,{p:p.read_bytes() for p in root.rglob('*.java')})
if __name__=='__main__':unittest.main()
