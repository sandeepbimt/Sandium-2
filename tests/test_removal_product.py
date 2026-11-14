"""Combined #1150/removal scope, composition and artifact gates."""
import importlib.util
from pathlib import Path
import unittest
import yaml
ROOT=Path(__file__).resolve().parents[1]
class RemovalProduct(unittest.TestCase):
 def test_1150_ui_inputs_preserved(self):
  import json,hashlib
  manifest=json.loads((ROOT/'.circleci/removal-ui-preservation.json').read_text())
  for path,sha in manifest['files'].items():
   self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),sha,path)
 def test_isolated_scope(self):
  p=ROOT/'.circleci/scripts/verify-removal-scope.py'
  spec=importlib.util.spec_from_file_location('scope',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  env={'CIRCLE_BRANCH':'experiment/sandium-overnight-removal','SANDIUM_EXPERIMENT_SCOPE':'sandium-exp-single-v1-bridge-crash01'}
  m.verify(env)
  for key,value in [('CIRCLE_BRANCH','experiment/sandium-ui-only'),('SANDIUM_EXPERIMENT_SCOPE','sandium-exp-single-v1-bridge-ui1088')]:
   with self.assertRaises(ValueError):m.verify(dict(env,**{key:value}))
 def test_current_ui_then_removal_every_stage(self):
  cfg=yaml.safe_load((ROOT/'.circleci/config.yml').read_text())
  self.assertEqual(cfg['parameters']['checkpoint_namespace']['default'],'sandium-exp-single-v1-bridge-crash01')
  self.assertFalse(cfg['parameters']['allow_seed_import']['default'])
  for name,job in cfg['jobs'].items():
   runs=[x['run']['command'] for x in job['steps'] if isinstance(x,dict) and isinstance(x.get('run'),dict)]
   self.assertIn('verify-removal-scope.py',runs[0],name)
   if name.startswith('full-stage-'):
    commands='\n'.join(runs)
    self.assertLess(commands.index('product-overlay-29-0.sh'),commands.index('product-overlay-30-0.sh'))
    self.assertLess(commands.index('product-overlay-30-0.sh'),commands.index('full-bounded-build.sh'))
 def test_gates_remain_bound(self):
  prep=(ROOT/'.circleci/scripts/prepare-brave-source.sh').read_text()
  self.assertIn('sandium-removal-recipe.py',prep)
  export=(ROOT/'.circleci/experimental-steps/export-apk.sh').read_text()
  self.assertIn('audit-sandium-stripped-apk.py',export)
  for gate in ['ARCHIVE_VALID','SIGNATURE_VALID','PACKAGE_VALID','BRANDING_VALID','REMOVALS_VALID']:
   self.assertIn('"$'+gate+'" = true',export)
  self.assertIn('APK_REMOVALS_VALID=true',(ROOT/'.circleci/bridge/driver.py').read_text())
  restored=(ROOT/'.circleci/experimental-steps/restored-apk-validation.sh').read_text()
  self.assertIn('REFERENCE_REVISION',restored);self.assertIn('CURRENT_REVISION',restored)
if __name__=='__main__':unittest.main()
