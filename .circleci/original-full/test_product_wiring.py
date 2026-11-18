import importlib.util,pathlib,shutil,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('wiring',ROOT/'.circleci/scripts/flow_wiring.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
class ProductWiring(unittest.TestCase):
 def fixture(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);root=pathlib.Path(t.name)
  (root/'.circleci/original-full').mkdir(parents=True)
  shutil.copy2(ROOT/'.circleci/config.yml',root/'.circleci/config.yml')
  shutil.copy2(ROOT/'.circleci/original-full/config.sha256',root/'.circleci/original-full/config.sha256')
  shutil.copytree(ROOT/'.circleci/experimental-steps',root/'.circleci/experimental-steps')
  for names in w.REQUIRED.values():
   for name in names:
    p=root/name if name.startswith('.circleci/features/page-text/') else root/('.circleci/tests' if name=='test_status_underlap_patch.py' else '.circleci/scripts')/name;p.parent.mkdir(parents=True,exist_ok=True);p.touch()
  return root
 def test_active_original_config_and_all_arguments(self):
  self.assertEqual(['brave-android-staged-build','renew-fixed-reference'],w.verify_full_wiring(self.fixture()))
 def test_config_mutation_rejected(self):
  root=self.fixture();p=root/'.circleci/config.yml';p.write_text(p.read_text().replace('product-overlay-29-0.sh','product-overlay-28-0.sh',1))
  with self.assertRaisesRegex(ValueError,'configuration differs'):w.verify_full_wiring(root)
 def test_every_product_wrapper_removal_rejected(self):
  for wrapper in w.REQUIRED:
   with self.subTest(wrapper=wrapper):
    root=self.fixture();p=root/'.circleci/experimental-steps'/wrapper;p.write_text('set -euo pipefail\nexit 0\n')
    with self.assertRaises(ValueError):w.verify_full_wiring(root)
 def test_lint_resource_argument_mutation_rejected(self):
  root=self.fixture();p=root/'.circleci/experimental-steps/product-overlay-30-0.sh';p.write_text(p.read_text().replace('apply-sandium-lint-resources.py --core "$CORE"','apply-sandium-lint-resources.py --core "$SRC"'))
  with self.assertRaisesRegex(ValueError,'lint resources'):w.verify_full_wiring(root)
 def test_actual_tree_readback_removal_rejected(self):
  root=self.fixture();p=root/'.circleci/experimental-steps/product-overlay-30-0.sh';text=p.read_text();self.assertIn('--verify-only',text);p.write_text(text.replace('--verify-only','',1))
  with self.assertRaises(ValueError):w.verify_full_wiring(root)
if __name__=='__main__':unittest.main()
