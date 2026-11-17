"""Exact isolated config receipt must retain all shipping product wiring gates."""
import pathlib, shutil, sys, tempfile, unittest
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.circleci/scripts'))
from flow_wiring import verify_full_wiring
class Tests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.r=pathlib.Path(self.t.name)
  shutil.copytree(ROOT/'.circleci',self.r/'.circleci')
  (self.r/'experiments/ubo-runtime').mkdir(parents=True)
  shutil.copy(ROOT/'experiments/ubo-runtime/config.sha256',self.r/'experiments/ubo-runtime/config.sha256')
 def tearDown(self):self.t.cleanup()
 def test_exact_experiment(self):self.assertEqual(verify_full_wiring(self.r),['brave-android-staged-build'])
 def test_changed_config_rejected(self):
  p=self.r/'.circleci/config.yml';p.write_text(p.read_text()+'\n# unreviewed\n')
  with self.assertRaises(ValueError):verify_full_wiring(self.r)
 def test_missing_receipt_rejected(self):
  (self.r/'experiments/ubo-runtime/config.sha256').unlink()
  with self.assertRaises(ValueError):verify_full_wiring(self.r)
 def test_invalid_receipt_rejected(self):
  (self.r/'experiments/ubo-runtime/config.sha256').write_text('.*')
  with self.assertRaises(ValueError):verify_full_wiring(self.r)
 def test_symlink_receipt_rejected(self):
  p=self.r/'experiments/ubo-runtime/config.sha256';value=p.read_text();p.unlink()
  target=self.r/'receipt';target.write_text(value);p.symlink_to(target)
  with self.assertRaises(ValueError):verify_full_wiring(self.r)
 def test_shipping_receipt_unchanged(self):
  shutil.copy(ROOT/'.circleci/original-full/candidate.yml',self.r/'.circleci/config.yml')
  self.assertEqual(verify_full_wiring(self.r),['brave-android-staged-build','renew-fixed-reference'])
 def test_wrapper_mutation_rejected(self):
  p=self.r/'.circleci/experimental-steps/product-overlay-29-0.sh'
  p.write_text(p.read_text().replace('apply-sandium-ui-prune.py','missing.py'))
  with self.assertRaises(ValueError):verify_full_wiring(self.r)
if __name__=='__main__':unittest.main()
