import sys, tempfile, unittest, json, os
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import ci_completion as c
class Completion(unittest.TestCase):
 def test_foreign_or_unverified_marker_cannot_halt(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'CIRCLE_WORKFLOW_ID':'wf','CIRCLE_SHA1':'sha','RAWS_PIPELINE_NUMBER':'1','RAWS_STAGE':'2'}),patch.object(c,'PATH',Path(d)/'marker'),patch.object(c.subprocess,'run') as run:
   c.PATH.write_text(json.dumps(dict(c.binding(),stage=1,done=False)))
   c.halt_complete();run.assert_not_called()
   c.PATH.write_text(json.dumps(dict(c.binding(),workflow='other',stage=1,done=True,apk_sha256='a'*64)))
   with self.assertRaises(ValueError):c.halt_complete()
   run.assert_not_called()
 def test_matching_verified_marker_halts(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'CIRCLE_WORKFLOW_ID':'wf','CIRCLE_SHA1':'sha','RAWS_PIPELINE_NUMBER':'1','RAWS_STAGE':'2'}),patch.object(c,'PATH',Path(d)/'marker'),patch.object(c.subprocess,'run') as run:
   c.PATH.write_text(json.dumps(dict(c.binding(),stage=1,done=True,apk_sha256='a'*64)))
   c.halt_complete();run.assert_called_once_with(['circleci-agent','step','halt'],check=True)
