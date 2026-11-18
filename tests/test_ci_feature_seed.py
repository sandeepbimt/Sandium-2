from pathlib import Path
from unittest.mock import patch
import json,os,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import ci_feature_seed as m
class SeedJob(unittest.TestCase):
    def test_explicit_scope_and_deadline_required(self):
        with patch.dict(os.environ,{},clear=True),self.assertRaises(ValueError):m.gate()
        with patch.dict(os.environ,{'RAWS_FEATURE_JOB_STARTED_EPOCH':'1000'}),patch.object(m.time,'time',return_value=4400),self.assertRaises(ValueError):m.original_epoch()
    def test_transition_preserves_clock_without_fake_fresh(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with patch.object(m,'ROOT',root),patch.object(m,'gate'),patch.object(m,'original_epoch',return_value=123),patch.object(m,'fingerprint',return_value='new'),patch.object(m,'SeedCallbacks') as callbacks,patch.object(m,'transition',return_value={'status':'feature-inputs-ready'}):
                m.prepare_transition(root/'old')
            self.assertEqual(json.loads((root/'.checkpoint-state/job-start.json').read_text()),{'epoch':123})
            self.assertFalse((root/'.checkpoint-state/fresh.json').exists())
            self.assertFalse((root/'.checkpoint-head').exists())
            self.assertFalse(json.loads((root/'handoff/stage1/state.json').read_text())['apk_verified'])
if __name__=='__main__':unittest.main()
