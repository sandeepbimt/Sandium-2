"""Metadata-fork isolation; no mock result is claimed as a remote cache test."""
import copy
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.circleci/bridge'))
spec=importlib.util.spec_from_file_location('back_seed',ROOT/'.circleci/bridge/fork_back_preview.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class BackPreviewSeed(unittest.TestCase):
 def setUp(self):
  self.env=dict(CIRCLE_SHA1='new-source',CIRCLE_WORKFLOW_ID='new-workflow',SANDIUM_PIPELINE_NUMBER='1200',CIRCLE_BRANCH=m.TARGET_BRANCH,SANDIUM_EXPERIMENT_SCOPE=m.TARGET_SCOPE,SANDIUM_ALLOW_SEED_IMPORT='true',SANDIUM_STAGE='0',SANDIUM_EXPERIMENT_REVIEWED='true',CIRCLE_PROJECT_REPONAME='Sandium-2')
  p=dict(kind=m.d.KIND,scope=m.SOURCE_SCOPE,compatibility=m.d.c.COMPAT,source=m.SOURCE_COMMIT,workflow=m.SOURCE_WORKFLOW,pipeline=1166,stage=6,apk_verified=True,previous_receipt='prior',plan=dict(base=dict(id='base',key=m.SOURCE_SCOPE+'-base-refresh-x',expires_at=10000,archive_bytes=1,manifest_sha256='manifest'),layers=[dict(id='delta',parent='base',key=m.SOURCE_SCOPE+'-delta-refresh-x',expires_at=9999,content_bytes=1)],head='delta'))
  self.receipt=dict(id=m.d.bridge.digest(m.d.bridge.encode(p)),payload=p)
 def candidate(self,r=None,now=1000):
  r=self.receipt if r is None else r
  return m.make_seed(r,self.env,now,expected_id=r['id'])
 def resign(self,r):
  r['id']=m.d.bridge.digest(m.d.bridge.encode(r['payload']));return r
 def test_plan_and_expiry_preserved_no_apk_claim(self):
  before=copy.deepcopy(self.receipt);c=self.candidate();p=c['payload']
  self.assertEqual(self.receipt,before);self.assertEqual(p['plan'],before['payload']['plan'])
  self.assertEqual(p['scope'],m.TARGET_SCOPE);self.assertFalse(p['apk_verified']);self.assertEqual(p['stage'],0)
  self.assertIsNone(p['previous_receipt']);self.assertEqual(p['seed_import']['receipt_id'],before['id'])
  self.assertEqual(c['id'],m.d.bridge.digest(m.d.bridge.encode(p)))
 def test_wrong_frozen_id_and_hash_rejected(self):
  with self.assertRaises(ValueError):m.verify_source(self.receipt,1000,1200)
  r=copy.deepcopy(self.receipt);r['payload']['source']='changed'
  with self.assertRaises(ValueError):self.candidate(r)
 def test_provenance_chain_expiry_and_pipeline_rejected(self):
  edits=[lambda p:p.update(scope=m.TARGET_SCOPE),lambda p:p.update(source='other'),lambda p:p.update(compatibility='other'),lambda p:p['plan'].update(head='wrong'),lambda p:p['plan']['layers'][0].update(parent='wrong'),lambda p:p['plan']['layers'][0].update(expires_at=1),lambda p:p['plan']['base'].update(key='another-scope-key')]
  for edit in edits:
   r=copy.deepcopy(self.receipt);edit(r['payload']);self.resign(r)
   with self.assertRaises(ValueError):self.candidate(r)
  with self.assertRaises(ValueError):m.verify_source(self.receipt,1000,1100,self.receipt['id'])
 def test_runtime_scope_and_stage_fail_closed(self):
  with patch.object(m.d,'gate') as outer:
   m.gate(self.env);outer.assert_called_once()
   for key,value in [('CIRCLE_BRANCH','experiment/sandium-overnight-removal'),('SANDIUM_EXPERIMENT_SCOPE',m.SOURCE_SCOPE),('SANDIUM_ALLOW_SEED_IMPORT','false'),('SANDIUM_STAGE','1')]:
    with self.assertRaises(ValueError):m.gate(dict(self.env,**{key:value}))
 def test_existing_head_and_stale_marker_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   state=Path(td)/'state';state.mkdir();head=Path(td)/'head';head.write_text('existing')
   with patch.object(m.d,'HEAD',head),patch.object(m.d,'STATE',state),patch.object(m,'gate'),patch.dict(os.environ,self.env):
    with self.assertRaises(ValueError):m.prepare()
    self.assertEqual(head.read_text(),'existing');head.unlink();m.prepare()
    with self.assertRaises(ValueError):m.prepare()
    m.d.c.save(state/'back-seed-target-absent.json',{'wrong':'marker'})
    with self.assertRaises(ValueError):m.import_seed()
 def test_successful_local_import_preserves_source_plan(self):
  real=m.make_seed
  with tempfile.TemporaryDirectory() as td:
   state=Path(td)/'state';state.mkdir();head=Path(td)/'head'/'receipt.json';head.parent.mkdir()
   with patch.object(m.d,'HEAD',head),patch.object(m.d,'STATE',state),patch.object(m,'gate'),patch.dict(os.environ,self.env),patch.object(m.time,'time',return_value=1000):
    m.prepare();m.d.c.save(head,self.receipt)
    (head.parent/'previous-receipt.json').write_text('old-source')
    with patch.object(m,'make_seed',side_effect=lambda r,e,n:real(r,e,n,expected_id=self.receipt['id'])):
     m.import_seed()
    candidate=m.d.c.read(state/'candidate.json')
    self.assertEqual(candidate['payload']['plan'],self.receipt['payload']['plan'])
    self.assertEqual(m.d.c.read(state/'back-seed-source-receipt.json'),self.receipt)
    self.assertFalse(head.exists());self.assertFalse((head.parent/'previous-receipt.json').exists())
    self.assertFalse((state/'back-seed-target-absent.json').exists())
    self.assertFalse(m.d.c.read(state/'back-seed-report.json')['payloads_verified_this_job'])
    with self.assertRaises(FileNotFoundError):m.import_seed()
 def test_all_job_gates_and_read_only_seed_yaml(self):
  cfg=yaml.safe_load((ROOT/'.circleci/config.yml').read_text())
  self.assertEqual(cfg['parameters']['checkpoint_namespace']['default'],m.TARGET_SCOPE)
  self.assertFalse(cfg['parameters']['allow_seed_import']['default']);self.assertFalse(cfg['parameters']['run_build']['default'])
  for job in cfg['jobs'].values():
   commands=[s['run']['command'] for s in job['steps'] if isinstance(s,dict) and isinstance(s.get('run'),dict)]
   self.assertIn('verify-back-preview-scope.py',commands[0])
  steps=cfg['jobs']['initialize-full-checkpoint']['steps'];saved=[s['save_cache']['key'] for s in steps if isinstance(s,dict) and 'save_cache' in s]
  self.assertEqual(len(saved),1);self.assertIn('scope-key',saved[0]);self.assertNotIn(m.SOURCE_SCOPE,saved[0])
  restores=[s['restore_cache']['keys'] for s in steps if isinstance(s,dict) and 'restore_cache' in s]
  self.assertEqual(restores[-1],[m.SOURCE_CACHE_KEY])
  self.assertNotIn('seed-capture',str(steps));self.assertNotIn('26 GiB',str(steps))
if __name__=='__main__':unittest.main()
