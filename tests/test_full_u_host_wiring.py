import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.circleci/full-u'))
import adapter,runner,worker
class Host(unittest.TestCase):
 def test_product_host_setup_precedes_prepare_within_same_owned_action(self):
  calls=[]
  with patch.object(adapter,'runtime'),patch.object(adapter.subprocess,'run',side_effect=lambda argv,**kw:calls.append(argv)),patch.object(adapter.os,'execvpe',side_effect=lambda cmd,argv,env:calls.append(argv)):
   adapter.run(Path('/tmp/project'),'product-preparing')
  self.assertTrue(calls[0][1].endswith('host_deps.py'));self.assertEqual(calls[0][2],'prepare')
  self.assertTrue(calls[1][1].endswith('product.py'));self.assertEqual(calls[1][2],'prepare')
 def test_fresh_graph_verifier_has_explicit_host_preparation_before_readonly_check(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);worker.HOST_PREPARED.clear();calls=[]
   with patch.object(worker.runner,'bounded_host',side_effect=lambda *a,**k:(calls.append('host') or {'outcome':'success'})),patch.object(worker.runner,'bounded_verify',side_effect=lambda *a,**k:(calls.append('verify') or {'outcome':'success'})):
    worker.verify_phase(root,'scope','build-ready',0,'fresh-validator')
    worker.verify_phase(root,'scope','build-ready',0,'fresh-validator')
   self.assertEqual(calls,['host','verify','verify'])
 def test_host_setup_cannot_take_archive_reserve(self):
  plan={'remaining_seconds':1900,'archive_seconds':900,'upload_seconds':480,'deadline':3600}
  with patch.object(runner,'current_plan',return_value=plan),patch.object(runner.process,'run') as run:
   result=runner.bounded_host(Path('/tmp'),'scope',['host'],0)
   self.assertEqual(result['outcome'],'host-budget-exhausted');run.assert_not_called()
 def test_compile_uses_actual_upstream_brave_target(self):
  with patch.object(adapter,'runtime'),patch.object(adapter.os,'chdir'),patch.object(adapter.os,'execvpe') as execute:
   adapter.run(Path('/tmp/project'),'build-ready')
  self.assertEqual(execute.call_args.args[1][-1],'brave')
if __name__=='__main__':unittest.main()
