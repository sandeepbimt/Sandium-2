"""Explicit experimental launch gates, not a device validation claim."""
import hashlib
import json
from pathlib import Path
import unittest
import yaml
ROOT=Path(__file__).resolve().parents[1]
class Activation(unittest.TestCase):
 def test_exact_full_gates_and_manual_trigger(self):
  profile=json.loads((ROOT/'experiments/single-handoff/profile.json').read_text())
  self.assertIs(type(profile['enabled']),bool)
  config=(ROOT/'.circleci/config.yml').read_bytes()
  self.assertEqual(config,(ROOT/'.circleci/original-full/candidate.yml').read_bytes())
  self.assertEqual(hashlib.sha256(config).hexdigest(),(ROOT/'.circleci/original-full/config.sha256').read_text().strip())
  data=yaml.safe_load(config)
  self.assertFalse(data['parameters']['run_build']['default'])
  self.assertFalse(data['parameters']['run_maintenance']['default'])
  self.assertEqual(['full'],data['parameters']['sandium_build_mode']['enum'])
  jobs=data['workflows']['sandium-full-mode']['jobs'];self.assertEqual(len(jobs),5)
  for i,item in enumerate(jobs,1):
   job=item['brave-android-staged-build'];self.assertEqual(job['stage_index'],i)
   self.assertEqual(job['filters']['branches']['only'],['experimental/navigation-official-reference-20261118'])
   self.assertEqual(job.get('requires',[]),[] if i==1 else [f'SANDIUM-FULL-MODE-stage-{i-1}'])
  self.assertIn('STAGE_BUILD_BUDGET_SECONDS=1500',config.decode())
  maintenance=data['workflows']['fixed-reference-maintenance']['jobs'][0]['renew-fixed-reference']
  self.assertEqual(maintenance['filters']['branches']['only'],'experiment/sandium-back-transition')
if __name__=='__main__':unittest.main()
