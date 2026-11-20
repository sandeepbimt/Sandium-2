import hashlib,unittest
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
class StablePipeline(unittest.TestCase):
 def test_only_five_branch_gates_change(self):
  original=(ROOT/'.circleci/original-full/candidate.yml').read_text()
  branch='            - work/1402-approved-ui\n'
  self.assertEqual(original.count(branch),5)
  expected=original.replace(branch,branch+'            - experiment/sandium-e1-1430\n')
  actual=(ROOT/'.circleci/config.yml').read_text()
  self.assertEqual(actual,expected)
  after=yaml.safe_load(actual)
  self.assertEqual(yaml.safe_load(original)['jobs'],after['jobs'])
  self.assertFalse(after['parameters']['run_build']['default'])
  self.assertIn('sandium-official-handoff-v1-fix/1394-official-lint-07214cac-daf8-47f1-a9dd-b48d229e934f-stage-2',expected)
 def test_reference_identity_and_completion_invalidation_preserved(self):
  text=(ROOT/'.circleci/scripts/resume-official-1394.py').read_text()
  self.assertIn('d6f47ee140ae7ec0ef36448f767e2fd90b1370da4e9bdae8673bd3fd93f47749',text)
  config=(ROOT/'.circleci/config.yml').read_text()
  self.assertIn('Retire restored 1402 APK and completion state before new build',config)
  e1='            - experiment/sandium-e1-1430\n'
  self.assertEqual(config.count(e1),5)
  config=config.replace(e1,'')
  self.assertEqual(config,(ROOT/'.circleci/original-full/candidate.yml').read_text())
  self.assertEqual(hashlib.sha256(config.encode()).hexdigest(),(ROOT/'.circleci/original-full/config.sha256').read_text().strip())
if __name__=='__main__':unittest.main()
