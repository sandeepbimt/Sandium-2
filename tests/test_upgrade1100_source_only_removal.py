import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('source_removal',ROOT/'.circleci/scripts/sandium-removal-recipe.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class SourceOnly(unittest.TestCase):
 def test_source_transform_does_not_generate_or_configure_graph(self):
  recipe=m.load()
  with patch.object(m.subprocess,'run') as run,patch.object(m,'configure_gn') as configure:
   m.apply_sources(recipe,Path('/src/brave'),Path('/src'),Path('/src/out/android_Release_arm64'))
   self.assertEqual(run.call_count,len(recipe['steps']));configure.assert_not_called()
   self.assertTrue(all(str(call.args[0][1]).endswith('.py') for call in run.call_args_list))
 def test_checked_entry_rejects_wrong_source_before_any_step(self):
  module=Mock();module.verify.side_effect=ValueError('wrong source')
  with patch.object(m,'apply_sources') as apply,patch('importlib.util.module_from_spec',return_value=module),patch('importlib.util.spec_from_file_location'):
   with self.assertRaisesRegex(ValueError,'wrong source'):m.apply_source_checked(m.load(),Path('/src/brave'),Path('/src'),Path('/out'))
   apply.assert_not_called()
 def test_legacy_phase_still_generates_and_target_hook_defers(self):
  import inspect
  self.assertIn('configure_gn(m,out)',inspect.getsource(m.apply))
  script=(ROOT/'.circleci/experimental-steps/product-overlay-30-0.sh').read_text()
  self.assertIn('--phase apply-source',script);self.assertIn('--phase apply\n',script)
  self.assertIn('FULL_U_GRAPH_AUDITS=DEFERRED',script)
if __name__=='__main__':unittest.main()
