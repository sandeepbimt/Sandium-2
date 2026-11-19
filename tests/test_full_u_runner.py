import sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.circleci/full-u'))
import runner as r
class Runner(unittest.TestCase):
 def test_no_fabricated_phase_advance(self):
  with tempfile.TemporaryDirectory() as t:
   with patch.object(r,'measure',return_value=1),patch.object(r.shutil,'disk_usage') as disk,patch.object(r.process,'run',side_effect=[{'outcome':'success','exit_code':0},{'outcome':'hard-failure','exit_code':1}]) as run:
    disk.return_value.free=200*1024**3
    value=r.execute(t,'scope','source-acquiring',['trusted'],{'source-synced':['verify']},time.time())
    self.assertEqual(value['phase_after'],'source-acquiring');self.assertEqual(value['status']['outcome'],'hard-failure')
    self.assertLessEqual(run.call_args_list[1].args[2],240)
 def test_verifier_timeout_retains_phase(self):
  with tempfile.TemporaryDirectory() as t:
   with patch.object(r,'measure',return_value=1),patch.object(r.shutil,'disk_usage') as disk,patch.object(r.process,'run',side_effect=[{'outcome':'success','exit_code':0},{'outcome':'time-slice','exit_code':-15}]):
    disk.return_value.free=200*1024**3
    value=r.execute(t,'scope','source-acquiring',['trusted'],{'source-synced':['verify']},time.time())
    self.assertEqual(value['phase_after'],'source-acquiring');self.assertEqual(value['status']['outcome'],'verification-timeout')
 def test_no_time_never_executes(self):
  with tempfile.TemporaryDirectory() as t:
   with patch.object(r.process,'run') as run:
    value=r.execute(t,'scope','source-acquiring',['trusted'],{},time.time()-3500)
    run.assert_not_called();self.assertFalse(value['final_budget']['can_capture'])
if __name__=='__main__':unittest.main()

class VerificationBudget(unittest.TestCase):
 def test_post_archive_does_not_charge_archive_twice(self):
  with tempfile.TemporaryDirectory() as t:
   plan={'remaining_seconds':1100,'archive_seconds':900,'upload_seconds':480,'deadline':3600}
   with patch.object(r,'current_plan',return_value=plan),patch.object(r.process,'run',return_value={'outcome':'success','exit_code':0}) as run:
    self.assertEqual(r.bounded_verify(t,'scope',['verify'],0,clock=lambda:2500)['outcome'],'verification-timeout');run.assert_not_called()
    self.assertEqual(r.bounded_verify(t,'scope',['verify'],0,clock=lambda:2500,stage='after-archive')['outcome'],'success')
    self.assertEqual(run.call_args.args[2],240)
