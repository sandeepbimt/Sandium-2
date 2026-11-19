import sys,unittest,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.circleci/full-u'))
import budget,protocol
class Contract(unittest.TestCase):
 def test_dynamic_budget_not_stage_cap(self):
  a=budget.plan(1000,1000,10**9,100*1024**3);b=budget.plan(1000,1800,10**9,100*1024**3)
  self.assertEqual(a['work_seconds']-b['work_seconds'],800);self.assertGreater(a['work_seconds'],720)
  self.assertFalse(budget.plan(1000,4500,10**9,100*1024**3)['can_capture'])
 def test_scope_engine_and_recipe(self):
  p={'source':{'wrapper_sha':'a'*40,'core_sha':'b'*40,'chromium_sha':'c'*40,'chromium_version':'158'},'build':{'is_official_build':True,'target_cpu':'arm64'}}
  s=protocol.identity(p,'d'*64);p['source']['chromium_sha']='e'*40
  self.assertNotEqual(s,protocol.identity(p,'d'*64))
 def test_failed_and_expired_never_accepted(self):
  now=int(time.time());p=dict(schema=1,scope='s',phase='source-acquiring',created_epoch=now,manifest_sha256='a'*64,generation='g',pipeline=1,outcome='hard-failure',readback_verified=True,apk_sha256=None)
  p['archive_key']='s-g-'+'a'*64
  with self.assertRaises(protocol.ProtocolError):protocol.verify(protocol.envelope(p),'s',True)
  p['outcome']='time-slice';self.assertTrue(protocol.verify(protocol.envelope(p),'s',True))
  with self.assertRaises(protocol.ProtocolError):protocol.verify(protocol.envelope(p),'s',True,now+15*86400)
if __name__=='__main__':unittest.main()
