"""Native transition probes cannot change engine behavior or break exact rollback."""
import gzip,json,importlib.util,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('native_diag_integration',ROOT/'experiments/native-navigation/apply.py');nav=importlib.util.module_from_spec(s);s.loader.exec_module(nav)
DATA=json.loads(gzip.decompress((ROOT/'tests/fixtures/native-navigation.json.gz').read_bytes()))
class NativeDiagnostics(unittest.TestCase):
 def test_probes_strip_to_exact_pinned_sources(self):
  for path in nav.diag.PATHS:
   source=DATA['native'][path];probed=nav.diag.apply(path,source)
   self.assertEqual(nav.diag.strip(path,probed,nav.diag.NATIVE_CHANGES),source)
   self.assertNotIn('delegate->GetTopControlsHeight()',probed)
   self.assertNotIn('SandiumOrdinaryBlurSource',probed)
 def test_product_probes_rebase_and_roll_back_exactly(self):
  with tempfile.TemporaryDirectory() as d,patch.object(nav,'geometry_changes',return_value={}),patch.object(nav.settings,'plan',return_value={}):
   root=Path(d)
   for path,source in DATA['frozen'].items():
    if path in nav.diag.PATHS:source=nav.diag.m.transform(path,source)
    p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(source)
   before={p:p.read_text() for p in root.rglob('*') if p.is_file()}
   nav.execute(root,True);nav.execute(root,True,True)
   for path in nav.diag.PATHS:
    self.assertEqual(nav.diag.strip(path,(root/path).read_text(),nav.diag.NATIVE_CHANGES),DATA['native'][path])
   nav.execute(root,False)
   self.assertEqual(before,{p:p.read_text() for p in before})
 def test_unknown_probe_blocks_before_write(self):
  with tempfile.TemporaryDirectory() as d,patch.object(nav,'geometry_changes',return_value={}),patch.object(nav.settings,'plan',return_value={}):
   root=Path(d)
   for path,source in DATA['frozen'].items():
    p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(source)
   p=root/nav.diag.m.BLUR;p.write_text(p.read_text()+'\n// SANDIUM_TRANSITION_RING_V1 unknown\n')
   before=p.read_text()
   with self.assertRaises(ValueError):nav.execute(root,True)
   self.assertEqual(p.read_text(),before);self.assertFalse((root/nav.STATE).exists())
if __name__=='__main__':unittest.main()
