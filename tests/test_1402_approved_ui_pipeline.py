import gzip,hashlib,sys,unittest
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.circleci/original-full'))
from recovery_test_contract import normalize_normal_branch
class StablePipeline(unittest.TestCase):
 def test_only_five_branch_gates_change(self):
  fixture=ROOT/'tests/fixtures/1402-approved-ui'
  raw=gzip.decompress((fixture/'baseline-config.yml.gz').read_bytes())
  self.assertEqual(hashlib.sha256(raw).hexdigest(),(fixture/'baseline-config.sha256').read_text().strip())
  before=yaml.safe_load(raw);after=yaml.safe_load((ROOT/'.circleci/config.yml').read_text())
  expected=raw.decode().replace('            - fix/1394-official-lint\n','            - work/1402-approved-ui\n')
  self.assertEqual(normalize_normal_branch(after,before),yaml.safe_load(expected))
  self.assertEqual(before['jobs'],normalize_normal_branch(after,before)['jobs'])
  self.assertFalse(after['parameters']['run_build']['default'])
  self.assertIn('sandium-official-handoff-v1-fix/1394-official-lint-07214cac-daf8-47f1-a9dd-b48d229e934f-stage-2',expected)
 def test_reference_identity_and_completion_invalidation_preserved(self):
  text=(ROOT/'.circleci/scripts/resume-official-1394.py').read_text()
  self.assertIn('d6f47ee140ae7ec0ef36448f767e2fd90b1370da4e9bdae8673bd3fd93f47749',text)
  config=(ROOT/'.circleci/config.yml').read_text()
  self.assertIn('Retire restored 1402 APK and completion state before new build',config)
  self.assertEqual(config,(ROOT/'.circleci/original-full/candidate.yml').read_text())
  self.assertEqual(hashlib.sha256(config.encode()).hexdigest(),(ROOT/'.circleci/original-full/config.sha256').read_text().strip())
if __name__=='__main__':unittest.main()
