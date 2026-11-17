"""Check production reset owners against the exact upstream Git inventory."""
import json
from pathlib import Path
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[1]
class PinnedResetPaths(unittest.TestCase):
 def test_every_core_owner_and_replay_patch_exists_at_pin(self):
  core=ROOT.parent/'brave-core-audit'
  if not (core/'.git').exists():self.skipTest('Pinned Brave audit checkout unavailable')
  manifest=json.loads((ROOT/'.circleci/features/removal-recipe.json').read_text())
  paths=set(subprocess.check_output(['git','-C',str(core),'ls-tree','-r','--name-only',manifest['brave_pin']],text=True).splitlines())
  required=set(manifest['core_restore'])|set(manifest.get('chromium_restore_patches',{}).values())
  self.assertEqual(set(),required-paths)
  for name in ('backing','paint'):
   for patch in json.loads((ROOT/f'.circleci/features/homepage-surround/{name}.json').read_text()):
    path=patch['path'] if isinstance(patch,dict) else patch[0]
    if path.startswith('brave/'):
     self.assertIn(path[6:],paths)
 def test_feed_owner_is_in_upstream_feed_module(self):
  expected='android/feed/core/java/src/org/chromium/chrome/browser/feed/BraveFeedSurfaceCoordinator.java'
  manifest=json.loads((ROOT/'.circleci/features/removal-recipe.json').read_text())
  self.assertIn(expected,manifest['core_restore'])
  patches=json.loads((ROOT/'.circleci/features/homepage-surround/backing.json').read_text())
  self.assertEqual({'brave/'+expected},{p['path'] for p in patches if p['path'].endswith('/BraveFeedSurfaceCoordinator.java')})

 def test_chromium_feed_owner_uses_pinned_module(self):
  expected='chrome/android/feed/core/java/src/org/chromium/chrome/browser/feed/FeedSurfaceCoordinator.java'
  manifest=json.loads((ROOT/'.circleci/features/removal-recipe.json').read_text())
  self.assertIn(expected,manifest['chromium_restore'])
  patches=json.loads((ROOT/'.circleci/features/homepage-surround/backing.json').read_text())
  self.assertEqual({expected},{p['path'] for p in patches if p['path'].endswith('/FeedSurfaceCoordinator.java')})
