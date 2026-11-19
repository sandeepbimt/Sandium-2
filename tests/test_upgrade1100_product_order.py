import importlib.util,json,os,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ordered_product',ROOT/'.circleci/upgrades/product.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ProductOrder(unittest.TestCase):
 def scenario(self,root,run):
  from contextlib import ExitStack
  stack=ExitStack();stack.enter_context(patch.dict(os.environ,{'FULL_U_SCOPE':'full-u-v1-'+'a'*64}))
  for name,value in [('admit',Mock()),('persist_graph',Mock()),('retire_reader',Mock()),('source_module',Mock(return_value=Mock(verify=Mock(return_value={'phase':'source-synced'})))),('graph_hashes',Mock(return_value={'args.gn':'a','build.ninja':'b'})),('graph_receipt',Mock(return_value='c')),('run',run)]:stack.enter_context(patch.object(m,name,value))
  (root/'brave-work/.sandium').mkdir(parents=True)
  return stack
 def test_final_gn_after_all_overlays_then_audits_then_proof(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);run=Mock()
   with self.scenario(root,run):
    result=m.prepare(root);self.assertEqual(result['phase'],'build-ready')
    commands=[call.args[1] for call in run.call_args_list]
    last_hook=next(i for i,c in enumerate(commands) if str(c[1]).endswith('product-overlay-30-0.sh'))
    gn=next(i for i,c in enumerate(commands) if str(c[1]).endswith('toolchain.py') and c[2]=='gn')
    audit=next(i for i,c in enumerate(commands) if str(c[1]).endswith('precheck-graph.py'))
    self.assertLess(last_hook,gn);self.assertLess(gn,audit)
    self.assertEqual(json.loads(m.proof_path(root).read_text()),result)
    run.reset_mock();self.assertEqual(m.verify(root),result)
    self.assertEqual(run.call_count,1);self.assertEqual(run.call_args.args[1][2],'verify')
 def test_failed_gn_clears_old_ready_claim_but_retains_source_receipt(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory)
   def run(root,argv):
    if str(argv[1]).endswith('toolchain.py') and argv[2]=='gn':raise subprocess.CalledProcessError(1,argv)
   with self.scenario(root,run):
    m.proof_path(root).write_text('old-ready')
    source=root/'brave-work/.sandium-source-synced.json';source.write_text('original-source-proof')
    with self.assertRaises(subprocess.CalledProcessError):m.prepare(root)
    self.assertFalse(m.proof_path(root).exists());self.assertEqual(source.read_text(),'original-source-proof')
 def test_stale_graph_rejected_without_repair(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);run=Mock()
   with self.scenario(root,run):
    m.prepare(root);run.reset_mock()
    with patch.object(m,'graph_hashes',return_value={'args.gn':'changed','build.ninja':'b'}):
     with self.assertRaisesRegex(ValueError,'Stale product'):m.verify(root)
    run.assert_not_called()
 def test_no_legacy_prepare_or_hidden_host_install(self):
  import inspect
  for function in (m.prepare,m.verify):
   source=inspect.getsource(function)
   for token in ('prepare-brave-source.sh','install-build-deps','apt-get','npm install'):self.assertNotIn(token,source)
if __name__=='__main__':unittest.main()
