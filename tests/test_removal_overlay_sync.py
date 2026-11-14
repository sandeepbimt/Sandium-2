import importlib.util,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('s',ROOT/'.circleci/scripts/sync-sandium-removal-overlays.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
class Sync(unittest.TestCase):
 def fixture(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);root=Path(t.name);core=root/'brave';core.mkdir()
  paths=list(s.MAPPINGS)+sorted(s.UI_OWNED_COPIED)
  for p in paths:
   f=core/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text('<resources>gold</resources>')
  return root,core,{'core_restore':paths,'ui_only_core_restore':sorted(s.UI_OWNED_COPIED)}
 def test_new_ui_palette_and_ntp_both_published(self):
  root,core,m=self.fixture();s.apply(core,root,m)
  for p in s.UI_OWNED_COPIED:self.assertEqual((root/p.replace('android/java/res/','chrome/android/java/res/',1)).read_bytes(),(core/p).read_bytes())
 def test_unknown_ui_exception_rejected(self):
  root,core,m=self.fixture();p='android/java/res/layout/unknown.xml';m['core_restore'].append(p);m['ui_only_core_restore'].append(p)
  with self.assertRaises(ValueError):s.apply(core,root,m)
 def test_new_removal_copied_input_requires_mapping(self):
  root,core,m=self.fixture();m['core_restore'].append('android/java/res/layout/other.xml')
  with self.assertRaises(ValueError):s.apply(core,root,m)
if __name__=='__main__':unittest.main()
