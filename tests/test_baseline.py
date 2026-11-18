import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('raw',ROOT/'tools/raw.py'); raw=importlib.util.module_from_spec(s); s.loader.exec_module(raw)
class Baseline(unittest.TestCase):
    def test_lock(self):
        v=raw.lock(); self.assertEqual(v['chromium']['version'],'156.0.8078.74')
    def test_zero_patches(self):
        self.assertEqual(json.loads((ROOT/'patches/manifest.json').read_text())['patches'],[])
    def test_no_feature_claims(self):
        self.assertEqual(json.loads((ROOT/'sandium/features/manifest.json').read_text())['features'],[])
    def test_refuse_project(self):
        with self.assertRaises(ValueError):raw.workspace(ROOT)
    def test_refuse_ancestor(self):
        with self.assertRaises(ValueError):raw.workspace(ROOT.parent)
    def test_refuse_existing_unowned(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d,'keep').write_text('safe')
            with self.assertRaises(ValueError):raw.workspace(d)
            self.assertEqual(Path(d,'keep').read_text(),'safe')
    def test_owned_workspace(self):
        with tempfile.TemporaryDirectory() as d:
            w=raw.workspace(Path(d)/'new'); self.assertEqual(raw.workspace(w),w)
    def test_low_disk(self):
        with patch.object(raw.shutil,'disk_usage') as use:
            use.return_value.free=56*1024**3
            with self.assertRaisesRegex(ValueError,'100 GiB'):raw.preflight(ROOT)
    def test_setup_requires_pin(self):
        with patch.object(raw,'lock',return_value={'depot_tools':{'revision':None}}):
            with self.assertRaisesRegex(ValueError,'lock first'):raw.setup('/tmp/should-not-be-created')
    def test_build_refuses_unowned(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError,'owned'):raw.build(d)
    def test_arm64(self):
        args=(ROOT/'ci/args.gn').read_text(); self.assertIn('target_cpu = "arm64"',args)
        self.assertNotIn('enable_extensions',args)
if __name__=='__main__':unittest.main()

class CIIsolation(unittest.TestCase):
    def test_ci_opt_in_and_branch_guard(self):
        config=(ROOT/'.circleci/config.yml').read_text()
        self.assertIn('default: false',config)
        self.assertIn('only: raw-sandium/bootstrap',config)
        self.assertIn('test "$CIRCLE_BRANCH" = "raw-sandium/bootstrap"',config)
        self.assertNotIn('restore_cache:',config)
        self.assertNotIn('save_cache:',config)
        self.assertNotIn('context:',config)
        self.assertIn('timeout 120s',config)
    def test_probe_has_no_compile_or_credentials(self):
        probe=(ROOT/'tools/ci_preflight.py').read_text()
        self.assertNotIn('autoninja',probe)
        self.assertNotIn('TOKEN',probe)
        self.assertNotIn('SECRET',probe)
