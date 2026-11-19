"""Actual158 transition reversal; unrelated settings/geometry separately composed."""
import gzip,hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def load(path):
 sp=importlib.util.spec_from_file_location('x'+str(abs(hash(path))),ROOT/path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
N=load('experiments/native-navigation/apply.py');B=load('experiments/single-handoff/native_blur.py')
class Native158(unittest.TestCase):
 def fixture(self,root):
  data=(ROOT/'tests/fixtures/upgrades158/native-reversal.json.gz').read_bytes()
  self.assertEqual(hashlib.sha256(data).hexdigest(),'931fd3895eb783fcb9cd3c146b581a0afc28559ce1864ad2d0a27d0ee1f3ad8c')
  f=json.loads(gzip.decompress(data))
  for p,t in f['files'].items():
   path=root/p;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(t)
  return f['files']
 def test_transition_journal_and_final_dim(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);before=self.fixture(root)
   with patch.object(N,'geometry_changes',return_value={}),patch.object(N.settings,'plan',return_value={}):
    N.execute(root,True);N.execute(root,True,True);N.execute(root,True)
    for p in (B.CC,B.H):
     text=(root/p).read_text()
     self.assertEqual(N.diag.strip(p,text,N.diag.NATIVE_CHANGES) if 'SANDIUM_TRANSITION_RING_V1' in text else text,B.fixture(p))
    final=B.plan(root)
    for p in (B.CC,B.H):
     expected=(B.dim_cc if p==B.CC else B.dim_h)(B.fixture(p))
     actual=final[root/p]
     self.assertEqual(N.diag.strip(p,actual,N.diag.NATIVE_CHANGES) if 'SANDIUM_TRANSITION_RING_V1' in actual else actual,expected)
    # Final planner replays on the diagnosed dim-only postimage too.
    inner={p:p.read_text() for p in final}
    for p,t in final.items():p.write_text(t)
    self.assertEqual(B.plan(root),final)
    for p,t in inner.items():p.write_text(t)
    N.execute(root,False)
    self.assertEqual(before,{p:(root/p).read_text() for p in before})
 def test_mixed_or_modified_pair_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);self.fixture(root)
   (root/B.H).write_text((root/B.H).read_text()+'\n// unexpected\n')
   with self.assertRaisesRegex(RuntimeError,'Mixed or modified'):N.transform(root)
if __name__=='__main__':unittest.main()
