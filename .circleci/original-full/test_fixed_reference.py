import importlib.util
from pathlib import Path
import tempfile,unittest,json
from unittest import mock
p=Path(__file__).with_name('fixed_reference.py');spec=importlib.util.spec_from_file_location('ref',p);f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
class ReferenceTests(unittest.TestCase):
 def setUp(self):
  patcher=mock.patch.object(f,'CACHE',f.physical_key('logical-key'));patcher.start();self.addCleanup(patcher.stop)
 def receipt(self):
  base=dict(key='logical-key',archive_bytes=f.BYTES,expires_at=f.DEADLINE,id='a'*64,manifest_sha256='b'*64)
  return f.envelope(dict(scope=f.SCOPE,compatibility=f.COMPAT,kind='legacy-bridge-v1',plan=dict(base=base,layers='IGNORED',head='IGNORED')))
 def candidate(self):
  with mock.patch.object(f,'physical_key',return_value=f.CACHE):return f.bootstrap(self.receipt(),f.SCOPE,f.DEADLINE-10*86400)
 def test_bootstrap_ignores_delta_heads_but_requires_exact_base(self):
  rec=self.receipt()
  with mock.patch.object(f,'physical_key',return_value=f.CACHE):
   self.assertEqual(f.bootstrap(rec,f.SCOPE,f.DEADLINE-86400)['payload']['status'],'candidate')
   with self.assertRaises(ValueError):f.bootstrap(rec,'other',f.DEADLINE-86400)
   rec['payload']['plan']['base']['archive_bytes']-=1
   with self.assertRaises(ValueError):f.bootstrap(f.envelope(rec['payload']),f.SCOPE,f.DEADLINE-86400)
  with mock.patch.object(f,'CACHE', 'wrong-cache'):
   with self.assertRaises(ValueError):f.bootstrap(self.receipt(),f.SCOPE,f.DEADLINE-86400)
 def test_digest_and_expiry_fail_closed(self):
  rec=self.receipt();rec['id']='wrong'
  with self.assertRaises(ValueError):f.bootstrap(rec,f.SCOPE,f.DEADLINE-86400)
  with mock.patch.object(f,'physical_key',return_value=f.CACHE):
   with self.assertRaises(ValueError):f.bootstrap(self.receipt(),f.SCOPE,f.DEADLINE)
  with self.assertRaises(ValueError):f.check(self.candidate(),f.DEADLINE-86400)
 def test_physical_key_exact_bytes_not_receipt_literal(self):
  import hashlib,base64
  expected='sandium-bridge-base-v1-'+base64.b64encode(hashlib.sha256(b'logical-key').digest()).decode().replace('/', '_')
  self.assertEqual(f.physical_key('logical-key'),expected)
  self.assertNotEqual(f.physical_key('logical-key\n'),expected)
 def test_bootstrap_requires_archive_and_restored_source_pins(self):
  c=self.candidate();payload=c['payload'];now=f.DEADLINE-86400
  with mock.patch.object(f,'verify_archives',return_value=payload),mock.patch.object(f.subprocess,'check_output',side_effect=[f.CHROMIUM,f.BRAVE]):
   accepted=f.accept_bootstrap(c,'root','legacy',now);self.assertEqual(f.check(accepted,now)['status'],'verified')
  with mock.patch.object(f,'verify_archives',return_value=payload),mock.patch.object(f.subprocess,'check_output',return_value='wrong'):
   with self.assertRaises(ValueError):f.accept_bootstrap(c,'root','legacy',now)
 def test_renewal_only_due_same_content_distinct_key(self):
  p=dict(self.candidate()['payload'],status='verified');old=f.envelope(p)
  with self.assertRaises(ValueError):f.renewal_candidate(old,'sandium-bridge-base-v1-new',f.DEADLINE-3*86400)
  with self.assertRaises(ValueError):f.renewal_candidate(old,'logical-key',f.DEADLINE-86400)
  new=f.renewal_candidate(old,'sandium-bridge-base-v1-new',f.DEADLINE-86400)
  with mock.patch.object(f,'verify_archives',return_value=new['payload']):
   accepted=f.accept_renewal(old,new,'root','legacy',f.DEADLINE-86399)
   self.assertEqual(accepted['payload']['manifest_sha256'],p['manifest_sha256'])
  changed=dict(new['payload'],base_id='c'*64)
  with mock.patch.object(f,'verify_archives',return_value=changed):
   with self.assertRaises(ValueError):f.accept_renewal(old,f.envelope(changed),'root','legacy',f.DEADLINE-86399)
 def test_verified_renewal_selected_next_run_without_changing_content(self):
  old=f.envelope(dict(self.candidate()['payload'],status='verified'))
  created=f.DEADLINE-86400
  new=f.renewal_candidate(old,'new immutable generation',created)
  self.assertNotEqual(new['payload']['cache_key'],old['payload']['cache_key'])
  self.assertEqual(new['payload']['expires_at'],created+14*86400)
  with mock.patch.object(f,'verify_archives',return_value=new['payload']):
   accepted=f.accept_renewal(old,new,'readback','legacy',created+1)
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);f.atomic_json(root/'.fixed-reference/accepted.json',accepted)
   selected=f.select(root,root/'missing-legacy-receipt',created+2)
   self.assertEqual(selected,accepted)
   self.assertEqual((root/'.fixed-reference/cache.key').read_bytes(),new['payload']['logical_cache_key'].encode())
   for key in ['base_id','manifest_sha256','archive_bytes']:
    self.assertEqual(selected['payload'][key],old['payload'][key])
 def test_actual_manifest_and_all_shard_verifier_required(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);raw=f.encode({'shards':[dict(name=str(i),size_bytes=1) for i in range(8)]})
   (root/'brave-workspace-checkpoint.manifest.json').write_bytes(raw)
   p=dict(self.candidate()['payload'],manifest_sha256=f.digest(raw),base_id=f.digest(b'legacy-base-v1\0'+raw),archive_bytes=8)
   legacy=root/'legacy.py';legacy.write_text('def verify(root,zstd_test,workers):\n assert workers == 8\n raise ValueError("corrupt shard")\n')
   with mock.patch.object(f,'BYTES',8):
    with self.assertRaisesRegex(ValueError,'corrupt shard'):f.verify_archives(f.envelope(p),root,legacy,f.DEADLINE-86400)
 def test_selection_preserves_accepted_and_exact_key_bytes(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);state=root/'.fixed-reference';state.mkdir()
   accepted=f.envelope(dict(self.candidate()['payload'],status='verified',verified_at=10))
   f.atomic_json(state/'accepted.json',accepted)
   self.assertEqual(f.select(root,root/'missing',f.DEADLINE-86400),accepted)
   self.assertEqual((state/'cache.key').read_bytes(),b'logical-key')
   with mock.patch.object(f,'verify_archives',return_value=accepted['payload']),mock.patch.object(f,'actual_pins'):
    self.assertEqual(f.postrestore(root,'legacy',f.DEADLINE-86400),accepted)
   self.assertEqual(f.read(state/'accepted.json'),accepted)
 def test_plus_checksum_is_not_urlsafe_dash(self):
  import hashlib,base64
  logical=next(str(i) for i in range(1000) if '+' in base64.b64encode(hashlib.sha256(str(i).encode()).digest()).decode())
  self.assertIn('+',f.physical_key(logical))
 def test_clean_readback_marker_binds_candidate_and_preserves_metadata(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);state=root/'.fixed-reference';state.mkdir();shards=root/'brave-workspace-checkpoint.shards';shards.mkdir()
   old=f.envelope(dict(self.candidate()['payload'],status='verified'))
   new=f.renewal_candidate(old,'newlogical',f.DEADLINE-86400)
   f.atomic_json(state/'accepted.json',old);f.atomic_json(state/'renewal.json',new)
   f.atomic_json(root/'brave-workspace-checkpoint.manifest.json',{'shards':[{'name':str(i)} for i in range(8)]})
   for i in range(8):(shards/str(i)).write_bytes(b'archive')
   with mock.patch.object(f,'accept_renewal',return_value={}):f.clear_readback(root,'legacy',f.DEADLINE-86399)
   self.assertEqual(f.read(state/'readback.json'),dict(candidate=new['id'],ready=True))
   self.assertEqual(f.read(state/'accepted.json'),old)
   self.assertFalse(list(shards.iterdir()));self.assertFalse((root/'brave-workspace-checkpoint.manifest.json').exists())
if __name__=='__main__':unittest.main()
