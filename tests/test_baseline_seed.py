import json,sys,tempfile,unittest,shutil
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import baseline_seed as s
class SeedAdmissionTests(unittest.TestCase):
 def test_real_frozen_receipts_and_exact_keys(self):
  p=s.restore_plan(now=1795020000)
  self.assertEqual(p['receipt_id'],s.RECEIPT);self.assertFalse(p['old_completion_usable'])
  self.assertTrue(p['archive_cache_key'].startswith('raws-final-base-v1-'))
 def test_expiration_and_tampering_fail_closed(self):
  with self.assertRaisesRegex(ValueError,'expired'):s.evidence(now=9999999999)
  with tempfile.TemporaryDirectory() as d:
   shutil.copytree(s.EVIDENCE,d,dirs_exist_ok=True)
   (Path(d)/'seed-1396-probe.json').write_text('{}')
   with self.assertRaisesRegex(ValueError,'Evidence differs'):s.evidence(d,now=1795020000)
 def fixture(self,d):
  root=Path(d);w=root/'work/source';w.mkdir(parents=True);(w/'.raw-sandium-workspace').touch()
  out=w/'src/out/RawSandium';(out/'apks').mkdir(parents=True);(out/'apks/ChromePublic.apk').write_bytes(b'fixture')
  (out/'build.ninja').write_text('old');(out/'retained.o').write_text('incremental')
  c=root/'.checkpoint-state';c.mkdir();(c/'selected.json').write_text(json.dumps(s.evidence(now=1795020000)))
  (c/'restored-proof.json').write_text(json.dumps({'receipt':s.RECEIPT,'head':s.BASE}))
  (root/'.raws-completion').mkdir();(root/'.raws-completion/receipt.json').write_text('{"done":true}')
  return root,out
 def invoke(self,root,**kw):
  args=dict(verify_baseline=lambda r,p:None,apply_features=lambda r:None,
   generate_gn=lambda r:(r/'work/source/src/out/RawSandium/build.ninja').write_text('feature'),verify_features=lambda r,f:None)
  args.update(kw)
  with patch.object(s,'file_sha',return_value=s.APK):return s.transition(root,'f'*64,now=1795020000,**args)
 def test_transition_invalidates_completion_before_features_and_keeps_objects(self):
  with tempfile.TemporaryDirectory() as d:
   root,out=self.fixture(d);calls=[]
   def features(r):
    self.assertFalse((r/'.raws-completion').exists());self.assertFalse((out/'apks/ChromePublic.apk').exists());self.assertFalse((out/'build.ninja').exists());calls.append('features')
   result=self.invoke(root,verify_baseline=lambda r,p:calls.append('baseline'),apply_features=features,verify_features=lambda r,f:calls.append('new'))
   self.assertEqual(calls,['baseline','features','new']);self.assertEqual(result['status'],'feature-inputs-ready')
   self.assertFalse(result['apk_verified']);self.assertFalse(result['checkpoint_accepted']);self.assertEqual((out/'retained.o').read_text(),'incremental')
   with self.assertRaisesRegex(ValueError,'already attempted'):self.invoke(root)
 def test_old_identity_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(ValueError,'Distinct'):s.transition(d,s.BASELINE_FINGERPRINT,verify_baseline=None,apply_features=None,generate_gn=None,verify_features=None,now=1795020000)
 def test_failed_feature_or_gn_cannot_be_ready(self):
  for hook in ('apply_features','generate_gn','verify_features'):
   with tempfile.TemporaryDirectory() as d:
    root,out=self.fixture(d)
    def fail(*args):raise ValueError('fixture failure')
    with self.assertRaisesRegex(ValueError,'fixture failure'):self.invoke(root,**{hook:fail})
    self.assertEqual(s.load(root/'.baseline-seed/admission.json')['status'],'failed')
    self.assertFalse((root/'.raws-completion').exists())
 def test_wrong_restore_and_symlink_rejected_before_mutation(self):
  with tempfile.TemporaryDirectory() as d:
   root,out=self.fixture(d);(root/'.checkpoint-state/restored-proof.json').write_text('{}')
   with self.assertRaisesRegex(ValueError,'Exact current-job'):self.invoke(root)
   self.assertTrue((out/'apks/ChromePublic.apk').exists())
  with tempfile.TemporaryDirectory() as d:
   root,out=self.fixture(d);(root/'handoff').symlink_to('/tmp',target_is_directory=True)
   with self.assertRaisesRegex(ValueError,'Unsafe'):self.invoke(root)
 def test_missing_regenerated_gn_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root,out=self.fixture(d)
   with self.assertRaisesRegex(ValueError,'regenerate'):self.invoke(root,generate_gn=lambda r:None)
