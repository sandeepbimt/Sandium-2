"""Keep native experiment reversible before any frozen-product reset/replay."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('native_wire',ROOT/'.circleci/scripts/flow_wiring.py')
w=importlib.util.module_from_spec(s);s.loader.exec_module(w)
class NativeWiring(unittest.TestCase):
 def fixture(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);root=Path(t.name)
  shutil.copytree(ROOT/'.circleci/experimental-steps',root/'.circleci/experimental-steps')
  for names in w.REQUIRED.values():
   for name in names:
    p=root/('.circleci/tests' if name=='test_status_underlap_patch.py' else '.circleci/scripts')/name;p.parent.mkdir(parents=True,exist_ok=True);p.touch()
  return root
 def test_production_wrapper_order(self):w.verify_product_wrappers(ROOT)
 def test_every_wrapper_requires_first_rollback(self):
  for index in range(24,31):
   root=self.fixture();p=root/f'.circleci/experimental-steps/product-overlay-{index}-0.sh'
   text=p.read_text();p.write_text(text.replace('--mode off','--mode on',1))
   with self.assertRaisesRegex(ValueError,'rollback must precede'):w.verify_product_wrappers(root)
 def test_final_profile_requires_readback(self):
  root=self.fixture();p=root/'.circleci/experimental-steps/product-overlay-30-0.sh'
  p.write_text(p.read_text().replace('--mode configured --verify-only','--mode configured'))
  with self.assertRaisesRegex(ValueError,'apply and verify'):w.verify_product_wrappers(root)
 def test_prepare_restores_journal_before_first_reset(self):
  text=(ROOT/'.circleci/scripts/prepare-brave-source.sh').read_text()
  rollback=text.index('apply-sandium-native-navigation.py')
  self.assertLess(rollback,text.index('--phase reset-core'))
  self.assertLess(rollback,text.index('--phase reset\n'))
  self.assertIn('if [ -f "$ROOT/brave-work/src/.sandium-native-navigation-state.json" ]; then',text[:rollback])
if __name__=='__main__':unittest.main()
