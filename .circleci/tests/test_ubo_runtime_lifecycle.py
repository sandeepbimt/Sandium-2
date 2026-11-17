"""CI layering contract; no native/runtime-success inference."""
import hashlib
from pathlib import Path
import unittest
import yaml
ROOT=Path(__file__).resolve().parents[2]
class Lifecycle(unittest.TestCase):
 def test_apply_after_baseline_and_before_compile(self):
  raw=(ROOT/'.circleci/config.yml').read_text()
  self.assertEqual(hashlib.sha256(raw.encode()).hexdigest(),(ROOT/'experiments/ubo-runtime/config.sha256').read_text().strip())
  steps=yaml.safe_load(raw)['jobs']['brave-android-staged-build']['steps']
  names=[s['run']['name'] for s in steps if isinstance(s,dict) and 'run' in s]
  gate=names.index('Verify EXT0 runtime-off and phone UI source boundaries after overlays')
  stage=names.index('Stage pinned uBO payload and explicit candidate activation')
  compile_=names.index('Verify exact EXT0 compile inputs and generated extension buildflag')
  self.assertLess(gate,stage);self.assertLess(stage,compile_)
 def test_preflight_scripts_are_separate_shell_commands(self):
  raw=(ROOT/'.circleci/config.yml').read_text()
  command=yaml.safe_load(raw)['jobs']['brave-android-staged-build']['steps'][1]['run']['command']
  lines=command.splitlines()
  self.assertIn('/tmp/sandium-ext0-preflight/bin/python experiments/ubo-runtime/test_ci_isolation.py',lines)
  self.assertIn('/tmp/sandium-ext0-preflight/bin/python .circleci/tests/test_ubo_runtime_lifecycle.py',lines)
  for line in lines:
   self.assertLessEqual(line.count('/bin/python'),1)
 def test_reset_reverse_before_existing_resets(self):
  s=(ROOT/'.circleci/scripts/prepare-brave-source.sh').read_text()
  bridge=s.index('ubo-runtime/shields_bridge/apply.py')
  loader=s.index('ubo-runtime/loader/apply.py')
  ext=s.index('ubo-runtime/source.py')
  policy=s.index('ubo-runtime/request_policy/apply.py')
  startup=s.index('ubo-runtime/routing/apply_startup.py')
  routing=s.index('ubo-runtime/routing/apply.py')
  activation=s.index('ubo-runtime/activation/apply.py')
  status=s.index('ubo-runtime/status/apply.py')
  policy=s.index('ubo-runtime/request_policy/apply.py')
  offline=s.index('ubo-runtime/offline_lists/apply.py')
  self.assertLess(status,activation);self.assertLess(activation,offline);self.assertLess(offline,policy);self.assertLess(policy,startup)
  self.assertLess(startup,routing);self.assertLess(routing,bridge)
  self.assertLess(bridge,loader);self.assertLess(loader,ext)
  self.assertLess(loader,s.index('apply-sandium-native-navigation.py'))
 def test_stage_pinned_source_and_disabled_runtime(self):
  s=(ROOT/'.circleci/scripts/stage-ubo-runtime.sh').read_text()
  for x in ['--fetch','--cache-dir','--source-artifacts','--integration-details','git -C "$ROOT" archive HEAD','verify_compile_inputs.py']:
   self.assertIn(x,s)
  self.assertLess(s.index('loader/apply.py'),s.index('shields_bridge/apply.py'))
  self.assertLess(s.index('shields_bridge/apply.py'),s.index('routing/apply.py'))
  self.assertLess(s.index('routing/apply.py'),s.index('routing/apply_startup.py'))
  self.assertLess(s.index('routing/apply_startup.py'),s.index('/gn" gen'))
  self.assertIn('--mode verify-off',s)
  self.assertIn('--branch "$CIRCLE_BRANCH" --mode on',s)
  self.assertLess(s.index('routing/apply_startup.py'),s.index('request_policy/apply.py'))
  self.assertLess(s.index('request_policy/apply.py'),s.index('offline_lists/apply.py'))
  self.assertLess(s.index('offline_lists/apply.py'),s.index('activation/apply.py'))
  self.assertIn('coverage=28/30',s)
  self.assertLess(s.index('activation/apply.py'),s.index('status/apply.py'))
  config=yaml.safe_load((ROOT/'.circleci/config.yml').read_text())
  self.assertFalse(config['parameters']['sandium_ubo_activate_candidate']['default'])
  self.assertNotIn('--enable-features=',s)
  self.assertNotIn('rm -rf',s)
if __name__=='__main__':unittest.main()
