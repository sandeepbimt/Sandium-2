"""Prevent accidental mixing of the preserved removal experiment and UI-only APK."""
import importlib.util
from pathlib import Path
import subprocess
import os
import tempfile
import sys
import unittest
import yaml
ROOT=Path(__file__).resolve().parents[1]
BASE='104df3fefd98f22123296d05a2e6540518eb0b6e'
SCOPE='sandium-exp-single-v1-bridge-ui1088'
class UIOnly(unittest.TestCase):
 def test_original_product_sources_unchanged(self):
  # Local git history is available in review; GitHub's shallow checkout may omit
  # BASE, so source hashes in the accompanying product manifest are authoritative.
  import hashlib,json
  manifest=json.loads((ROOT/'.circleci/ui-only-product.json').read_text())
  self.assertEqual(manifest['baseline'],BASE)
  for path,digest in manifest['preserved_files'].items():
   self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),digest,path)
 def test_source_and_apk_contract_are_not_stripped(self):
  prep=(ROOT/'.circleci/scripts/prepare-brave-source.sh').read_text()
  self.assertIn('verify-sandium-vanilla-brave.py',prep)
  self.assertNotIn('sandium-removal-recipe.py',prep)
  export=(ROOT/'.circleci/experimental-steps/export-apk.sh').read_text()
  self.assertNotIn('audit-sandium-stripped-apk',export)
  for gate in ('ARCHIVE_VALID','SIGNATURE_VALID','PACKAGE_VALID','BRANDING_VALID'):
   self.assertIn('"$'+gate+'" = true',export)
  restored=(ROOT/'.circleci/experimental-steps/restored-apk-validation.sh').read_text()
  self.assertIn('REFERENCE_REVISION',restored)
  self.assertIn('CURRENT_REVISION',restored)
 def test_no_removal_execution_and_scoped_gate_first(self):
  cfg=yaml.safe_load((ROOT/'.circleci/config.yml').read_text())
  self.assertEqual(cfg['parameters']['checkpoint_namespace']['default'],SCOPE)
  self.assertFalse(cfg['parameters']['allow_seed_import']['default'])
  for name,job in cfg['jobs'].items():
   runs=[x['run']['command'] for x in job['steps'] if isinstance(x,dict) and isinstance(x.get('run'),dict)]
   self.assertIn('verify-ui-only-scope.py',runs[0],name)
   self.assertNotIn('product-overlay-30', '\n'.join(runs),name)
  for n in range(1,6):
   self.assertIn('test_ui_only_product.py', str(cfg['jobs'][f'full-stage-{n}']),n)
 def test_real_driver_accepts_ui_seed_scope(self):
  with tempfile.TemporaryDirectory() as tmp:
   env=dict(os.environ,CIRCLE_WORKING_DIRECTORY=tmp,CIRCLE_PROJECT_REPONAME='Sandium-2',
    SANDIUM_EXPERIMENT_REVIEWED='true',SANDIUM_EXPERIMENT_SCOPE=SCOPE,
    SANDIUM_ALLOW_SEED_IMPORT='true',CIRCLE_BRANCH='experiment/sandium-ui-only')
   subprocess.run([sys.executable,str(ROOT/'.circleci/bridge/full_driver.py'),'seed-select'],env=env,check=True,capture_output=True)
   self.assertEqual((Path(tmp)/'.checkpoint-state/scope-key').read_text(),SCOPE)
 def test_candidate_contract_matches_ui_export(self):
  driver=(ROOT/'.circleci/bridge/driver.py').read_text()
  self.assertNotIn('APK_REMOVALS_VALID',driver)
  for gate in ('BUILD_FINISHED=true','APK_ARCHIVE_VALID=true','APK_SIGNATURE_VALID=true','APK_PACKAGE_ID_VALID=true','APK_BRANDING_VALID=true'):
   self.assertIn(gate,driver)
 def test_scope_rejects_other_branch_and_namespace(self):
  spec=importlib.util.spec_from_file_location('ui_scope',ROOT/'.circleci/scripts/verify-ui-only-scope.py')
  m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  env={'CIRCLE_BRANCH':'experiment/sandium-ui-only','SANDIUM_EXPERIMENT_SCOPE':SCOPE}
  m.verify(env)
  for k,v in [('CIRCLE_BRANCH','experiment/sandium-overnight-removal'),('SANDIUM_EXPERIMENT_SCOPE','sandium-exp-single-v1-bridge-crash01')]:
   with self.assertRaises(ValueError):m.verify(dict(env,**{k:v}))
if __name__=='__main__':unittest.main()
