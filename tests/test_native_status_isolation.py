import hashlib,importlib.util
from pathlib import Path
import unittest,yaml
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('status_config',ROOT/'.circleci/native-status-test/build_config.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class NativeStatusIsolation(unittest.TestCase):
 def test_exact_reproducible_manual_branch(self):
  raw=(ROOT/'.circleci/native-status-test/config.yml').read_bytes();cfg=yaml.safe_load(raw)
  self.assertEqual(cfg,m.derive(yaml.safe_load((ROOT/'.circleci/original-full/candidate.yml').read_text())))
  self.assertEqual(hashlib.sha256(raw).hexdigest(),(ROOT/'.circleci/native-status-test/config.sha256').read_text().strip())
  self.assertFalse(cfg['parameters']['run_build']['default'])
  for j in cfg['workflows']['sandium-full-mode']['jobs']:self.assertEqual(j['brave-android-staged-build']['filters']['branches']['only'],m.BRANCH)
 def test_no_new_publication_and_correct_replay_order(self):
  normal=yaml.safe_load((ROOT/'.circleci/original-full/candidate.yml').read_text());base=m.base.derive(normal);cfg=m.derive(normal)
  original=base['jobs']['brave-android-staged-build']['steps'];steps=cfg['jobs']['brave-android-staged-build']['steps']
  self.assertEqual([s for s in original if 'save_cache' in s],[s for s in steps if 'save_cache' in s])
  runs=[s['run'] for s in steps if 'run' in s];names=[r['name'] for r in runs]
  self.assertLess(names.index('Diagnose restored Siso checkpoint and compare prior stage'),names.index('Reverse isolated native status candidate before normal overlay replay'))
  self.assertLess(names.index('Reverse isolated native status candidate before normal overlay replay'),names.index('Prepare pinned Brave Android source'))
  self.assertLess(names.index('Compile-exclude and audit all thirteen Sandium removal groups'),names.index('Apply isolated API15 native NTP and Settings status candidate'))
  apply=runs[names.index('Apply isolated API15 native NTP and Settings status candidate')]['command']
  self.assertIn('--test-only-native-screens',apply)
  self.assertIn('--test-only-enable --test-only-native-screens --write',apply)
  for name in ('Build bounded Brave Android APK slice','Export APK status and artifacts','Final five-stage completion gate'):
   self.assertEqual(next(s for s in original if isinstance(s,dict) and s.get('run',{}).get('name')==name),next(s for s in steps if isinstance(s,dict) and s.get('run',{}).get('name')==name))
if __name__=='__main__':unittest.main()
