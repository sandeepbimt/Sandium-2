"""Product-specific guard tests complement the real inherited Full replay suite."""
import os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import ci_full as c

class RawFullAdapterTests(unittest.TestCase):
 def test_scope_is_complete_product_fingerprint(self):
  self.assertEqual(c.D.c.COMPAT,'raws-full-v1-'+c.fingerprint())
  self.assertEqual(os.environ['RAWS_CHECKPOINT_SCOPE'],c.D.c.COMPAT)
 def test_missing_head_never_seeds_later_stage(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);state=r/'state';state.mkdir()
   with patch.object(c,'gate'),patch.multiple(c.D,STATE=state,HEAD=r/'head'),patch.dict(os.environ,RAWS_STAGE='2',RAWS_ALLOW_FRESH_SEED='true'):
    with self.assertRaisesRegex(ValueError,'stage1'):c.prepare()
    self.assertFalse((state/'fresh.json').exists())
 def test_fresh_seed_requires_explicit_gate(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);state=r/'state';state.mkdir()
   with patch.object(c,'gate'),patch.multiple(c.D,STATE=state,HEAD=r/'head'),patch.dict(os.environ,RAWS_STAGE='1',RAWS_ALLOW_FRESH_SEED='false'):
    with self.assertRaisesRegex(ValueError,'stage1'):c.prepare()
 def test_wrong_readback_does_not_publish(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);state=r/'state';state.mkdir()
   c.D.c.save(state/'candidate.json',{'id':'new'})
   c.D.c.save(state/'readback-proof.json',{'candidate':'old'})
   with patch.multiple(c.D,STATE=state,HEAD=r/'head'),patch.object(c.f,'publish') as publish:
    with self.assertRaisesRegex(ValueError,'readback'):c.publish()
    publish.assert_not_called()
 def test_increment_readback_does_not_request_base(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);state=r/'state';state.mkdir();incoming=r/'incoming';incoming.mkdir()
   (incoming/'payload.zip').write_bytes(b'x')
   for n,v in [('base.key','accepted-base'),('outgoing.key','new-delta')]: (state/n).write_text(v)
   c.D.c.save(state/'candidate.json',{'id':'new','payload':{}})
   with patch.multiple(c.D,STATE=state,INCOMING=incoming),patch.object(c.D,'valid',return_value={}):c.clear_readback()
   self.assertTrue((state/'readback-base.key').read_text().startswith('unused-'))
   self.assertEqual((state/'readback-delta.key').read_text(),'new-delta')
   self.assertFalse(incoming.exists())
