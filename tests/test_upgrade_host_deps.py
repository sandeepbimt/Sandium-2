import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'.circleci/upgrades'))
import host_deps as h

class HostDepsTest(unittest.TestCase):
 def fixture(self, tmp):
  root=Path(tmp);src=root/'brave-work/src';shutil.copytree(h.FIXTURES,src)
  for p in ('DEPS','build/config/android/config.gni'):
   shutil.copy(src/'composed'/p,src/p)
  return root,src
 def test_exact_source_and_reject_drift(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(h.source,'verify'):
   root,src=self.fixture(tmp)
   self.assertEqual(h.authenticated_source(root),src)
   (src/'build/install-build-deps.py').write_text('unexpected')
   with self.assertRaisesRegex(ValueError,'Unreviewed'):h.authenticated_source(root)
 def test_exact_brave_composition_and_versions(self):
  with tempfile.TemporaryDirectory() as tmp:
   dst=Path(tmp)
   for p,patchname in [('DEPS','DEPS.patch'),('build/config/android/config.gni','build-config-android-config.gni.patch')]:
    f=dst/p;f.parent.mkdir(parents=True,exist_ok=True);shutil.copy(h.FIXTURES/p,f)
    subprocess.run(['git','apply','--unsafe-paths','--directory',str(dst),str(h.FIXTURES/'brave/patches'/patchname)],check=True)
    self.assertEqual(f.read_bytes(),(h.FIXTURES/'composed'/p).read_bytes())
   self.assertEqual(h.versions(dst),{'jdk':'25.0.5','sdk_platform':'37.2','sdk_build_tools':'37.0.0'})
 def test_raw_or_arbitrary_composition_rejected(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(h.source,'verify'):
   root,src=self.fixture(tmp)
   shutil.copy(h.FIXTURES/'DEPS',src/'DEPS')
   with self.assertRaisesRegex(ValueError,'Unreviewed'):h.authenticated_source(root)
 def test_upstream_accepts_flags_and_quick_check_is_read_only(self):
  spec=importlib.util.spec_from_file_location('upstream',h.FIXTURES/'build/install-build-deps.py')
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  opts=module.parse_args(h.FLAGS+['--quick-check'])
  self.assertTrue(opts.lib32);self.assertTrue(opts.quick_check)
  self.assertFalse(opts.chromeos_fonts);self.assertFalse(opts.syms)
  with patch.object(module,'missing_packages',return_value=[]),patch.object(module,'package_list',return_value=[]),patch.object(module.subprocess,'run') as run:
   with self.assertRaises(SystemExit) as c:module.quick_check(opts)
   self.assertEqual(c.exception.code,0);run.assert_not_called()
 def test_verify_never_installs(self):
  with patch.object(h,'authenticated_source',return_value=Path('/src')),patch.object(h,'invoke') as invoke,patch.object(h,'capabilities',return_value={}):
   h.verify('/root');command=invoke.call_args.args[0]
   self.assertIn('--quick-check',command);self.assertNotIn('sudo',command)
 def test_prepare_installs_only_after_failed_quick_check(self):
  with patch.object(h,'authenticated_source',return_value=Path('/src')),patch.object(h,'invoke',side_effect=[subprocess.CalledProcessError(1,'check'),None,None]) as invoke,patch.object(h,'capabilities',return_value={}):
   h.prepare('/root');calls=[c.args[0] for c in invoke.call_args_list]
   self.assertEqual(len(calls),3);self.assertEqual(calls[1][:2],['sudo','-n'])
   self.assertNotIn('--quick-check',calls[1]);self.assertNotIn('upgrade',calls[1])
 def test_prepare_reuses_host_but_not_archived_readiness(self):
  with patch.object(h,'authenticated_source',return_value=Path('/src')),patch.object(h,'invoke') as invoke,patch.object(h,'capabilities',side_effect=ValueError('missing JDK')):
   with self.assertRaisesRegex(ValueError,'missing JDK'):h.prepare('/root')
   self.assertTrue(all('--quick-check' in c.args[0] for c in invoke.call_args_list))

if __name__=='__main__':unittest.main()
