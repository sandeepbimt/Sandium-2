import sys,os,tempfile,unittest,json,copy
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import ci_final_archive as a
from generate_final_archive_config import generate_archive
class FinalArchiveTests(unittest.TestCase):
 def test_explicit_only(self):
  with patch.dict(os.environ,{},clear=True):
   with self.assertRaisesRegex(ValueError,'opt-in'):a.require_done()
 def test_does_not_accept_partial(self):
  with patch.dict(os.environ,RAWS_FINAL_ARCHIVE='true'),patch.object(a,'state',return_value={'status':'slice_expired'}):
   with self.assertRaisesRegex(ValueError,'Whole target'):a.require_done()
 def test_digest_must_match(self):
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,RAWS_FINAL_ARCHIVE='true'),patch.object(a,'ROOT',Path(d)),patch.object(a,'state',return_value=dict(status='done',apk_verified=True,apk_signature_verified=True,apk_zip_verified=True,apk_sha256='wrong')):
   apk=Path(d)/'work/source/src/out/RawSandium/apks/ChromePublic.apk';apk.parent.mkdir(parents=True);apk.write_bytes(b'apk')
   with self.assertRaisesRegex(ValueError,'digest'):a.require_done()
 def test_independent_default_off_split_serialized(self):
  cfg=generate_archive();self.assertFalse(cfg['parameters']['run_raw_final_archive']['default'])
  self.assertEqual(set(cfg['jobs']),{'raws-final-compile','raws-final-pack','raws-final-probe'})
  self.assertEqual(cfg['job-groups']['raws-final-chain']['jobs'][1]['raws-final-pack']['requires'],['raws-final-compile'])
  self.assertIn('serial-group',cfg['workflows']['RawS one-off final archive']['jobs'][0]['raws-final-chain'])
  for job in cfg['jobs'].values():
   self.assertEqual(job['environment']['RAWS_ALLOW_FRESH_SEED'],'false')
   names=[s.get('run',{}).get('name') for s in job['steps'] if isinstance(s,dict)]
   self.assertNotIn('RawS Full halt-complete',names);self.assertNotIn('RawS Full publish',names)
   self.assertEqual(names[0],'Start one-off job budget before setup')
   keys=[s['save_cache']['key'] for s in job['steps'] if isinstance(s,dict) and 'save_cache' in s]
   self.assertFalse(any(k.startswith(('raws-full-head','raws-full-base','raws-full-delta')) for k in keys))
 def test_pack_worker_never_compiles_or_regenerates(self):
  steps=generate_archive()['jobs']['raws-final-pack']['steps']
  commands='\n'.join(s.get('run',{}).get('command','') for s in steps if isinstance(s,dict))
  for forbidden in ('ci_compile.py','ci_source.py','runhooks','gn gen'):self.assertNotIn(forbidden,commands)
  self.assertIn('prepare-archive',commands)
 def test_missing_readback_rejected(self):
  with tempfile.TemporaryDirectory() as d,patch.object(a,'FINAL',Path(d)),patch.object(a.c.D,'valid',return_value={}):
   (Path(d)/'candidate.json').write_text(json.dumps({'id':'new'}));(Path(d)/'readback-required.json').write_text(json.dumps({'candidate':'old'}))
   with self.assertRaisesRegex(ValueError,'readback'):a.verify_publish()
   self.assertFalse((Path(d)/'receipt.json').exists())
 def test_progress_preferred_without_normal_head_overwrite(self):
  with tempfile.TemporaryDirectory() as d:
   progress=Path(d);(progress/'receipt.json').write_text('{"id":"progress"}');original=a.c.D.HEAD;seen=[]
   with patch.object(a,'PROGRESS',progress),patch.object(a.c.D,'valid'),patch.object(a.c.D,'select',side_effect=lambda **kw:seen.append((a.c.D.HEAD,kw))):a.prepare()
   self.assertEqual(seen,[(progress/'receipt.json',{'precheck':True})]);self.assertEqual(a.c.D.HEAD,original)
 def test_invalid_progress_never_silently_falls_back(self):
  with tempfile.TemporaryDirectory() as d:
   progress=Path(d);(progress/'receipt.json').write_text('{"id":"bad"}')
   with patch.object(a,'PROGRESS',progress),patch.object(a.c.D,'valid',side_effect=ValueError('expired')),patch.object(a.c,'prepare') as fallback:
    with self.assertRaisesRegex(ValueError,'expired'):a.prepare()
    fallback.assert_not_called()
 def test_progress_fallback_when_absent(self):
  with tempfile.TemporaryDirectory() as d,patch.object(a,'PROGRESS',Path(d)),patch.object(a.c,'prepare') as fallback:
   a.prepare();fallback.assert_called_once()
   with self.assertRaisesRegex(ValueError,'Missing exact'):a.prepare(True)
 def test_pack_rejects_wrong_workflow_source_pipeline_or_partial(self):
  payload=dict(workflow='ours',source='commit',pipeline=1,apk_verified=True)
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,CIRCLE_WORKFLOW_ID='ours',CIRCLE_SHA1='commit',RAWS_PIPELINE_NUMBER='1'):
   progress=Path(d);(progress/'receipt.json').write_text('{}')
   for key,bad in [('workflow','other'),('source','other'),('pipeline',2),('apk_verified',False)]:
    p=dict(payload);p[key]=bad
    with patch.object(a,'PROGRESS',progress),patch.object(a.c.D,'valid',return_value=p),patch.object(a.c.D,'select') as select:
     with self.assertRaisesRegex(ValueError,'same-workflow'):a.prepare(True)
     select.assert_not_called()
 def test_progress_publishes_only_after_exact_proof(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);state=r/'state';progress=r/'progress';state.mkdir()
   (state/'candidate.json').write_text('{"id":"new"}');(state/'readback-proof.json').write_text('{"candidate":"wrong"}')
   with patch.object(a,'PROGRESS',progress),patch.object(a.c.D,'STATE',state),patch.object(a.c.D,'valid'),patch.object(a.c,'readback'):
    with self.assertRaisesRegex(ValueError,'proof'):a.progress_publish()
    self.assertFalse(progress.exists())
    (state/'readback-proof.json').write_text('{"candidate":"new"}');a.progress_publish()
    self.assertEqual(json.loads((progress/'receipt.json').read_text()),{'id':'new'})
 def test_expiry_persists_before_failure_and_does_not_enable_pack(self):
  steps=generate_archive()['jobs']['raws-final-compile']['steps']
  published=next(i for i,s in enumerate(steps) if isinstance(s,dict) and s.get('save_cache',{}).get('name')=='Publish independent verified continuation')
  final=next(i for i,s in enumerate(steps) if isinstance(s,dict) and s.get('run',{}).get('name')=='Final archive progress-final')
  handoff=next(i for i,s in enumerate(steps) if isinstance(s,dict) and s.get('save_cache',{}).get('name')=='Publish same-workflow completed handoff')
  self.assertLess(published,final);self.assertLess(final,handoff)
  with patch.object(a,'state',return_value={'status':'slice_expired'}):
   with self.assertRaisesRegex(ValueError,'retained independently'):a.progress_final()
 def test_success_also_captures_delta_and_proof_without_head_update(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);state=root/'state';state.mkdir();final=root/'final'
   (state/'selected.json').write_text('{"id":"old"}')
   build=dict(status='done',apk_sha256='abc')
   candidate=dict(id='new',payload=dict(apk_verified=False,previous_receipt='old'))
   def capture():
    self.assertEqual(json.loads((root/'work/source/.sandium/final-build-state.json').read_text()),build)
    (state/'candidate.json').write_text(json.dumps(candidate))
   with patch.object(a,'ROOT',root),patch.object(a,'FINAL',final),patch.object(a,'state',return_value=build),patch.object(a,'require_done'),patch.object(a.c.D,'STATE',state),patch.object(a.c.D,'valid'),patch.object(a.c.f,'capture',side_effect=capture):a.progress_capture()
   result=json.loads((state/'candidate.json').read_text());self.assertTrue(result['payload']['apk_verified']);self.assertEqual(result['payload']['apk_sha256'],'abc')
   self.assertFalse((root/'.checkpoint-head').exists())

 def test_probe_fresh_worker_has_only_exact_full_base(self):
  cfg=generate_archive();job=cfg['jobs']['raws-final-probe'];steps=job['steps']
  self.assertEqual(cfg['job-groups']['raws-final-chain']['jobs'][2]['raws-final-probe']['requires'],['raws-final-pack'])
  saves=[s for s in steps if isinstance(s,dict) and 'save_cache' in s];self.assertEqual(saves,[])
  restores=[s['restore_cache']['keys'] for s in steps if isinstance(s,dict) and 'restore_cache' in s]
  self.assertEqual(restores,[['raws-final-verified-v1-<< pipeline.id >>'],['raws-final-base-v1-{{ checksum ".checkpoint-state/base.key" }}']])
  commands='\n'.join(s.get('run',{}).get('command','') for s in steps if isinstance(s,dict))
  self.assertIn('ci_restore_probe.py',commands)
  for forbidden in ('ci_source.py','ci_compile.py','restore-layer','progress-capture',' publish'):self.assertNotIn(forbidden,commands)
 def test_probe_binding_and_empty_chain_required(self):
  baseline=dict(apk_verified=True,workflow='wf',source='sha',pipeline=1,apk_sha256='apk',plan=dict(layers=[],head='base',base={'id':'base'}))
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,CIRCLE_WORKFLOW_ID='wf',CIRCLE_SHA1='sha',RAWS_PIPELINE_NUMBER='1'):
   final=Path(d);(final/'receipt.json').write_text('{}');(final/'archived-apk-proof.json').write_text('{"sha256":"apk","bytes":100}')
   variants=[dict(baseline,workflow='other'),dict(baseline,apk_verified=False),dict(baseline,plan=dict(layers=[{}],head='base',base={'id':'base'}))]
   for payload in variants:
    with patch.object(a,'FINAL',final),patch.object(a.c.D,'valid',return_value=payload),patch.object(a.c.D,'select') as select:
     with self.assertRaisesRegex(ValueError,'same-workflow'):a.prepare_probe()
     select.assert_not_called()
   old=a.c.D.HEAD
   with patch.object(a,'FINAL',final),patch.object(a.c.D,'valid',return_value=baseline),patch.object(a.c.D,'select') as select:a.prepare_probe();select.assert_called_once_with(precheck=True)
   self.assertEqual(a.c.D.HEAD,old)
