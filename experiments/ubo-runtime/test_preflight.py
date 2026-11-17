import importlib.util
import pathlib
import tempfile
import unittest
from unittest.mock import patch

ROOT=pathlib.Path(__file__).parent
spec=importlib.util.spec_from_file_location('preflight',ROOT/'preflight.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class PreflightTest(unittest.TestCase):
 def test_corrupt_payload_rejected_before_git(self):
  with tempfile.TemporaryDirectory() as d, patch.object(m.subprocess,'check_output') as git:
   p=pathlib.Path(d)/'patch';p.write_text('bad')
   with self.assertRaisesRegex(ValueError,'digest'):m.preflight(pathlib.Path(d),p)
   git.assert_not_called()
 def test_wrong_pin_rejected_without_apply(self):
  with patch.object(m.subprocess,'check_output',return_value='other'),patch.object(m.subprocess,'run') as run:
   with self.assertRaisesRegex(ValueError,'exact pinned'):m.preflight(ROOT,ROOT/'brave-android-extensions.patch')
   run.assert_not_called()
 def test_dirty_base_rejected(self):
  with patch.object(m.subprocess,'check_output',side_effect=[m.PIN,' M source']),patch.object(m.subprocess,'run') as run:
   with self.assertRaisesRegex(ValueError,'clean'):m.preflight(ROOT,ROOT/'brave-android-extensions.patch')
   run.assert_not_called()
 def test_gate_and_legacy_engine_preserved(self):
  s=(ROOT/'brave-android-extensions.patch').read_text()
  self.assertIn('+  sandium_ubo_runtime_experiment = false',s)
  self.assertIn('+if (sandium_ubo_runtime_experiment) {',s)
  self.assertNotIn('ad_block_service.cc',s)
  self.assertNotIn('brave_content_settings_observer.cc',s)

if __name__=='__main__': unittest.main()
