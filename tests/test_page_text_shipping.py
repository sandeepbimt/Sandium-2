"""Global page-text candidate must retain complete reset and source replay coverage."""
import json
import os
from pathlib import Path
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[1]
FEATURE=ROOT/'.circleci/features/page-text'
class PageTextShipping(unittest.TestCase):
 def test_reset_inventory(self):
  inventory=json.loads((FEATURE/'integration-plan.json').read_text())
  recipe=json.loads((ROOT/'.circleci/features/removal-recipe.json').read_text())
  for key in ('chromium_restore','core_restore','generated_overwrite'):
   self.assertTrue(set(inventory[key]) <= set(recipe[key]),key)
  for key in ('chromium_restore','core_restore'):
   self.assertTrue(set(inventory[key]) <= set(recipe['ui_only_'+key]),key)
 def test_focused_source_and_policy_suites(self):
  cases=[['bash','tests/run-tests.sh']]
  cases += [['python3',x] for x in ('tests/test_ui_transform.py','tests/test_combined.py','renderer/test_native.py','renderer/test_native_api.py','renderer/test_brave_patch_replay.py','renderer/test_oopif.py','renderer/test_css_candidate.py')]
  for command in cases:
   with self.subTest(command=command):
    result=subprocess.run(command,cwd=FEATURE,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    self.assertEqual(result.returncode,0,result.stdout[-15000:])

 def test_profile_disk_adapter_host(self):
  jar=os.environ.get('JSON_JAVA_JAR')
  if not jar or not Path(jar).is_file():
   self.skipTest('Profile host adapter requires external pinned JSON-java jar; full Android compile remains required')
  result=subprocess.run(['bash','tests/run-profile-tests.sh'],cwd=FEATURE,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
  self.assertEqual(result.returncode,0,result.stdout[-15000:])
