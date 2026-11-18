import sys,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import ci_restore_probe as p
class ProbeTests(unittest.TestCase):
 def test_exact_proof(self):
  value={'plan':{'head':'h'},'apk_verified':True,'apk_sha256':'sha'}
  with patch.object(p.c.D,'valid',return_value=value):
   self.assertEqual(p.validate_restore({'id':'r'},{'receipt':'r','head':'h'}),value)
   with self.assertRaises(ValueError):p.validate_restore({'id':'r'},{'receipt':'wrong','head':'h'})
 def test_missing_metrics_not_noop_claim(self):
  with tempfile.TemporaryDirectory() as d:self.assertIn('inconclusive',p.metrics_summary(Path(d)/'absent')['classification'])
 def test_remote_work_is_reported(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'m';path.write_text(json.dumps({'step_id':'1','is_remote':True,'action':'cxx'})+'\n')
   self.assertEqual(p.metrics_summary(path)['fresh_remote'],1)
 def test_local_compile_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'m';path.write_text(json.dumps({'step_id':'1','is_local':True,'action':'cxx'})+'\n')
   with self.assertRaises(ValueError):p.metrics_summary(path)

 def test_pinned_cache_field(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'m';path.write_text(json.dumps({'step_id':'1','is_remote':True,'action':'cxx','cache':True})+'\n')
   result=p.metrics_summary(path)
   self.assertEqual(result['remote_cache_hits'],1)
   self.assertEqual(result['fresh_remote'],0)
