import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'.circleci/full-u'))
import worker as w
class Worker(unittest.TestCase):
 def test_activation_never_bypasses_hold_or_branch_gate(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);profile=root/w.PROFILE;profile.parent.mkdir(parents=True)
   profile.write_text(json.dumps({'ready':False,'branch':'work/full-u-1100'}))
   with self.assertRaisesRegex(w.protocol.ProtocolError,'not admitted'):w.context(root)
   profile.write_text(json.dumps({'ready':True,'branch':'work/full-u-1100'}))
   with patch.dict(w.os.environ,{'CIRCLE_BRANCH':'wrong'}):
    with self.assertRaisesRegex(w.protocol.ProtocolError,'wrong upgrade branch'):w.context(root)

 def test_completed_explicit_resume_never_infers_other_reference(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);meta=root/'.full-u';meta.mkdir();(meta/'receipt.json').write_text('{"id":"expected"}')
   with patch.object(w,'context',return_value=('scope',meta)),patch.object(w.protocol,'verify',return_value={'apk_sha256':'apk'}),patch.dict(w.os.environ,{'FULL_U_RESUME':'expected'}):
    self.assertTrue(w.completed(root,1))
    with patch.dict(w.os.environ,{'FULL_U_RESUME':'other'}):
     with self.assertRaises(w.protocol.ProtocolError):w.completed(root,1)
 def test_verification_timeout_salvages_source_without_nested_verifier(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);meta=root/'.full-u';meta.mkdir();(meta/'job-start').write_text('1')
   (meta/'result.json').write_text(json.dumps({'phase_after':'build-ready','status':{'outcome':'verification-timeout'}}))
   admission={'can_capture':True,'archive_seconds':900,'deadline':9999999999,'upload_seconds':480}
   with patch.object(w,'context',return_value=('scope',meta)),patch.object(w,'verify_phase') as verify,patch.object(w.runner,'current_plan',return_value=admission),patch.object(w.process,'run',return_value={'outcome':'success'}) as process,patch.object(w.archive.native,'load_manifest',return_value=({'source_bytes':1,'archive_bytes':1},None)):
    w.capture(root,1)
    plan=json.loads((meta/'capture-plan.json').read_text())
    self.assertEqual(plan['phase'],'source-synced');self.assertEqual(plan['outcome'],'recovered-source');self.assertTrue(plan['source_only']);self.assertIsNone(plan['apk_sha256'])
    self.assertEqual(verify.call_args_list[0].args[2],'source-synced')
    self.assertEqual(verify.call_args_list[-1].args[-1],'after-archive')
    self.assertEqual(process.call_args.args[0][2],'pack')
 def test_pack_callback_is_prevalidated_not_independent_process(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);meta=root/'.full-u';meta.mkdir()
   (meta/'capture-plan.json').write_text(json.dumps(dict(scope='scope',phase='source-synced',outcome='recovered-source',source_only=True,apk_sha256=None)))
   def capture(*args,**kwargs):
    args[6]('source-synced',root/'brave-work')
    return {'payload':{'archive_key':'key'}}
   with patch.object(w,'context',return_value=('scope',meta)),patch.object(w.archive,'capture',side_effect=capture),patch.object(w.runner,'bounded_verify') as verify,patch.dict(w.os.environ,{'CIRCLE_PIPELINE_NUMBER':'1','CIRCLE_SHA1':'sha','CIRCLE_WORKFLOW_ID':'wf'}):
    w.pack(root,1);verify.assert_not_called()
if __name__=='__main__':unittest.main()
