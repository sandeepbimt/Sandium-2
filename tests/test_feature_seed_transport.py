import json,os,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import feature_seed_transport as t

class Transport(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.base=Path(self.temp.name);self.session=self.base/'session';self.root=self.session/'baseline'
  self.root.mkdir(parents=True);(self.root/'.checkpoint-state').mkdir()
  self.env=patch.dict(os.environ,{'CIRCLE_WORKFLOW_ID':'test-job','CIRCLE_BUILD_NUM':'1','CIRCLE_BRANCH':'raw-sandium/native-ui158','RAWS_NATIVE_FEATURE_SEED':'true','RAWS_STAGE':'1','CIRCLE_PROJECT_REPONAME':'Sandium-2','CIRCLE_PROJECT_USERNAME':'Fixture CircleCI Organization','RAWS_CI_REPOSITORY_URL':'https://github.com/sandeepbimt/Sandium-2.git','RAWS_CHECKPOINT_REVIEWED':'true','RAWS_PIPELINE_NUMBER':str(t.seed.evidence()['payload']['pipeline']+1)});self.env.start();self.addCleanup(self.env.stop)
  self.c=dict(phase='prepared',job={'CIRCLE_WORKFLOW_ID':'test-job','CIRCLE_BUILD_NUM':'1'},job_start_epoch=time.time(),tree='tree')
  t.write_new(self.session/'context.json',self.c);t.write_new(self.session/'plan.json',t.seed.restore_plan())
  t.write_new(self.root/'.checkpoint-state/job-start.json',{'epoch':self.c['job_start_epoch']})
  self.ident=patch.object(t,'identity',return_value='tree');self.ident.start();self.addCleanup(self.ident.stop)
 def advance(self,phase):
  self.c=t.phase(self.session,self.c,phase)
 def selected(self):
  self.advance('selected');t.write_new(self.root/'.checkpoint-state/selected.json',t.seed.evidence())
 def restored(self):
  self.selected();self.advance('restored')
  proof={'receipt':t.seed.RECEIPT,'head':t.seed.BASE}
  t.write_new(self.root/'.checkpoint-state/restored-proof.json',proof)
  t.write_new(self.session/'current-job-proof.json',dict(job=self.c['job'],proof=proof,selected=t.seed.evidence()))
  (self.root/'work/source').mkdir(parents=True);(self.root/'work/source/retained.o').write_bytes(b'object')
 def feature(self):
  root=self.base/'feature';root.mkdir();(root/'.git').mkdir();return root
 def test_select_exact_remote_bytes_and_precheck(self):
  def select(session,c,command):
   self.assertEqual(command,'select');self.assertIn('precheck=True',t.BASELINE_PROGRAM)
   t.write_new(self.root/'.checkpoint-state/selected.json',t.seed.evidence())
  with patch.object(t,'baseline',side_effect=select):t.select(self.session,t.seed.EVIDENCE/'seed-1396-receipt.json')
  self.assertEqual(t.seed.load(self.session/'context.json')['phase'],'selected')
  with self.assertRaises(ValueError):t.select(self.session,t.seed.EVIDENCE/'seed-1396-receipt.json')
 def test_semantically_identical_different_receipt_bytes_rejected(self):
  path=self.base/'receipt';path.write_text(json.dumps(t.seed.evidence(),indent=1))
  with patch.object(t,'baseline') as run:
   with self.assertRaisesRegex(ValueError,'bytes'):t.select(self.session,path)
   run.assert_not_called()
 def test_adopt_moves_only_work_and_state(self):
  self.restored();feature=self.feature();before=(self.root/'work/source/retained.o').stat().st_ino
  (self.root/'.checkpoint-head').mkdir();(self.root/'.raws-completion').mkdir()
  result=t.adopt(self.session,feature)
  self.assertEqual(before,(feature/'work/source/retained.o').stat().st_ino)
  self.assertFalse((self.root/'work').exists());self.assertTrue((self.root/'.checkpoint-head').exists())
  self.assertFalse((feature/'.checkpoint-head').exists());self.assertFalse((feature/'.raws-completion').exists())
  self.assertFalse(result['apk_verified']);self.assertEqual(result['baseline_checkout'],str(self.root))
  with self.assertRaises(ValueError):t.adopt(self.session,feature)
 def test_existing_destination_and_forged_proof_fail_closed(self):
  self.restored();feature=self.feature();(feature/'work').mkdir()
  with self.assertRaisesRegex(ValueError,'fresh'):t.adopt(self.session,feature)
  (feature/'work').rmdir();(self.root/'.checkpoint-state/restored-proof.json').write_text('{}')
  with self.assertRaisesRegex(ValueError,'changed'):t.adopt(self.session,feature)
  self.assertTrue((self.root/'work/source/retained.o').exists())
 def test_job_identity_expiry_and_budget(self):
  with patch.dict(os.environ,{'CIRCLE_BUILD_NUM':'2'}):
   with self.assertRaisesRegex(ValueError,'another job'):t.context(self.session,'prepared')
  with patch.object(t.seed,'restore_plan',side_effect=ValueError('expired')):
   with self.assertRaisesRegex(ValueError,'expired'):t.context(self.session,'prepared')
  with self.assertRaisesRegex(ValueError,'budget'):t.budget(time.time()-3300)
 def test_move_failure_rolls_back_without_copy(self):
  a=self.base/'a';b=self.base/'b';a.write_text('a');b.write_text('b')
  original=Path.rename
  def rename(src,dst):
   if src==b:raise OSError('failed')
   return original(src,dst)
  with patch.object(Path,'rename',rename):
   with self.assertRaises(OSError):t.move_pairs([(a,self.base/'c'),(b,self.base/'d')])
  self.assertEqual(a.read_text(),'a');self.assertTrue(b.exists());self.assertFalse((self.base/'c').exists())
 def test_cross_filesystem_rejected_before_rename(self):
  a=self.base/'a';a.write_text('a');original=Path.stat
  def stat(p,*args,**kwargs):
   result=original(p,*args,**kwargs)
   if p==a:return type('Stat',(),{'st_dev':-1})()
   return result
  # Mock just the device preflight, retaining normal exists/is_symlink behavior.
  with patch.object(Path,'stat',stat),patch.object(Path,'exists',lambda p:p==a),patch.object(Path,'is_symlink',return_value=False):
   with self.assertRaisesRegex(ValueError,'filesystem'):t.move_pairs([(a,self.base/'b')])
  self.assertEqual(a.read_text(),'a')
 def test_restore_fixed_sequence_and_partial_failure(self):
  self.selected();incoming=self.base/'incoming';incoming.mkdir();shards=incoming/t.SHARDS;shards.mkdir()
  m={'shards':[{'name':str(i)+'.zst','size_bytes':1} for i in range(8)]}
  for item in m['shards']:(shards/item['name']).write_bytes(b'x')
  t.write_new(incoming/t.MANIFEST,m);calls=[]
  def run(session,c,command):
   calls.append(command)
   if command=='restore-finish':t.write_new(self.root/'.checkpoint-state/restored-proof.json',{'receipt':t.seed.RECEIPT,'head':t.seed.BASE})
  with patch.object(t.seed,'file_sha',return_value=t.seed.restore_plan()['manifest_sha256']),patch.object(t,'baseline',side_effect=run):t.restore(self.session,incoming)
  self.assertEqual(calls,['restore-base','restore-finish']);self.assertFalse((incoming/t.SHARDS).exists())
  self.assertEqual(t.seed.load(self.session/'context.json')['phase'],'restored')
 def test_restore_failure_never_records_proof_or_allows_retry(self):
  self.selected();incoming=self.base/'incoming';incoming.mkdir();shards=incoming/t.SHARDS;shards.mkdir()
  m={'shards':[{'name':str(i)+'.zst','size_bytes':1} for i in range(8)]}
  for item in m['shards']:(shards/item['name']).write_bytes(b'x')
  t.write_new(incoming/t.MANIFEST,m)
  with patch.object(t.seed,'file_sha',return_value=t.seed.restore_plan()['manifest_sha256']),patch.object(t,'baseline',side_effect=RuntimeError('restore failed')):
   with self.assertRaises(RuntimeError):t.restore(self.session,incoming)
  self.assertFalse((self.session/'current-job-proof.json').exists())
  with self.assertRaisesRegex(ValueError,'Partial'):t.restore(self.session,incoming)
 def test_original_budget_preserves_downstream_reserve(self):
  with patch.object(t.time,'time',return_value=10000):
   self.assertEqual(t.budget(10000),3300-1620-t.CLEANUP_GRACE)
   self.assertEqual(t.budget(9500),3300-500-1620-t.CLEANUP_GRACE)
   with self.assertRaisesRegex(ValueError,'budget'):t.budget(10000-1660)
 def test_owned_group_stops_grandchild_on_timeout_and_leader_exit(self):
  child="import signal,time; from pathlib import Path; signal.signal(signal.SIGTERM,signal.SIG_IGN); p=Path(__import__('sys').argv[1]); f=p.open('ab',buffering=0); exec('while True: f.write(b.x.); time.sleep(0.02)'.replace('b.x.',repr(b'x')))"
  # Child ignores TERM; it must still stop when its leader exits or times out.
  for timeout in (True,False):
   output=self.base/('timeout' if timeout else 'success')
   parent="import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',"+repr(child)+","+repr(str(output))+"],start_new_session=True); time.sleep("+('30' if timeout else '0.25')+")"
   args=[sys.executable,'-c',parent]
   if timeout:
    with self.assertRaises(subprocess.TimeoutExpired):t.run_owned(args,cwd=self.base,env=dict(os.environ),seconds=0.4,deadline_epoch=time.time()+5)
   else:t.run_owned(args,cwd=self.base,env=dict(os.environ),seconds=5,deadline_epoch=time.time()+5)
   time.sleep(0.1);size=output.stat().st_size;self.assertGreater(size,0)
   time.sleep(0.15);self.assertEqual(output.stat().st_size,size)
 def test_expired_subprocess_deadline_refuses_continuation(self):
  with self.assertRaises(subprocess.TimeoutExpired):t.run_owned([sys.executable,'-c','import time;time.sleep(10)'],cwd=self.base,env=dict(os.environ),seconds=5,deadline_epoch=time.time()-1)
 def test_actual_baseline_select_gate_uses_only_isolated_old_branch(self):
  self.ident.stop();session=self.base/'real-select'
  t.prepare(Path(__file__).resolve().parents[1],session,time.time())
  # The host lacks archive-sized free space. Only disk admission is stubbed;
  # actual unchanged c.gate, D.select(precheck=True), valid and metadata run.
  program=t.BASELINE_PROGRAM.replace("elif phase == 'select': c.gate();", "elif phase == 'select': c.D.c.disk_guard=lambda *a:None; c.gate();")
  with patch.object(t,'BASELINE_PROGRAM',program):t.select(session,t.seed.EVIDENCE/'seed-1396-receipt.json')
  self.assertEqual(t.seed.load(session/'baseline/.checkpoint-state/selected.json'),t.seed.evidence())
  self.assertEqual(os.environ['CIRCLE_BRANCH'],'raw-sandium/native-ui158')
  self.assertEqual(os.environ['RAWS_NATIVE_FEATURE_SEED'],'true')
 def test_wrong_caller_branch_or_missing_optin_rejected_before_subprocess(self):
  for change in ({'CIRCLE_BRANCH':'raw-sandium/official158'},{'RAWS_NATIVE_FEATURE_SEED':'false'},{'RAWS_STAGE':'2'}):
   with patch.dict(os.environ,change),patch.object(t,'run_owned') as run:
    with self.assertRaisesRegex(ValueError,'caller'):t.baseline(self.session,self.c,'select')
    with self.assertRaisesRegex(ValueError,'caller'):t.context(self.session,'prepared')
    run.assert_not_called()
 def test_shallow_missing_baseline_fetches_only_exact_verified_object(self):
  origin='git@github.com:sandeepbimt/Sandium-2.git';commands=[];calls=[]
  def git(root,*args):
   calls.append(args)
   if args==('remote','get-url','origin'):return origin
   if args==('rev-parse','--verify',t.seed.BASELINE_COMMIT+'^{commit}') and len([x for x in calls if x==args])==1:raise subprocess.CalledProcessError(128,args)
   if args[-1].endswith('^{tree}'):return 'a'*40
   return t.seed.BASELINE_COMMIT
  def run(argv,**kw):commands.append((argv,kw))
  with patch.dict(os.environ,{'CIRCLE_PROJECT_USERNAME':'Fixture CircleCI Organization','RAWS_CI_REPOSITORY_URL':'https://github.com/sandeepbimt/Sandium-2.git'}),patch.object(t,'git',side_effect=git),patch.object(t,'run_owned',side_effect=run):
   self.assertEqual(t.ensure_baseline_object(self.root,self.base,time.time()),'a'*40)
  self.assertEqual(len(commands),1);argv,kw=commands[0]
  self.assertEqual(argv[-2:],[origin,t.seed.BASELINE_COMMIT]);self.assertIn('--no-tags',argv);self.assertIn('--refetch',argv);self.assertIn('--no-filter',argv)
  self.assertLessEqual(kw['seconds'],120);self.assertEqual(kw['cwd'],self.root)
 def test_present_baseline_never_fetches_and_foreign_origin_refused(self):
  with patch.object(t,'git',side_effect=[t.seed.BASELINE_COMMIT,t.seed.BASELINE_COMMIT,t.seed.BASELINE_COMMIT,'b'*40]),patch.object(t,'run_owned') as run:
   self.assertEqual(t.ensure_baseline_object(self.root,self.base,time.time()),'b'*40);run.assert_not_called()
  with patch.dict(os.environ,{'CIRCLE_PROJECT_USERNAME':'Owner','RAWS_CI_REPOSITORY_URL':'https://github.com/Owner/Sandium-2.git'}),patch.object(t,'git',return_value='https://github.com/Other/Sandium-2.git'):
   with self.assertRaisesRegex(ValueError,'match'):t.verified_origin(self.base)
 def test_github_app_display_name_is_not_vcs_owner_and_urls_match_pin(self):
  forms=('https://github.com/sandeepbimt/Sandium-2.git','git@github.com:sandeepbimt/Sandium-2.git','ssh://git@github.com/sandeepbimt/Sandium-2.git')
  for origin in forms:
   for metadata in forms:
    with patch.dict(os.environ,{'CIRCLE_PROJECT_USERNAME':'My CircleCI Organization','RAWS_CI_REPOSITORY_URL':metadata}),patch.object(t,'git',return_value=origin):
     self.assertEqual(t.verified_origin(self.base),origin)
 def test_github_app_uses_pipeline_url_not_legacy_oauth_metadata(self):
  origin='https://github.com/sandeepbimt/Sandium-2.git'
  for legacy in ('','Sandium-2'):
   with patch.dict(os.environ,{'CIRCLE_REPOSITORY_URL':legacy,'RAWS_CI_REPOSITORY_URL':origin}),patch.object(t,'git',return_value=origin):
    self.assertEqual(t.verified_origin(self.base),origin)
  with patch.dict(os.environ,{'CIRCLE_REPOSITORY_URL':origin,'RAWS_CI_REPOSITORY_URL':''}),patch.object(t,'git',return_value=origin):
   with self.assertRaises(ValueError):t.verified_origin(self.base)
 def test_origin_gate_rejects_matching_foreign_urls_and_missing_metadata(self):
  for origin,metadata in (('https://github.com/Other/Sandium-2.git','https://github.com/Other/Sandium-2.git'),('https://github.com/Other/Sandium-2.git','https://github.com/sandeepbimt/Sandium-2.git'),('https://github.com/sandeepbimt/Sandium-2.git','https://github.com/Other/Sandium-2.git'),('https://github.com/sandeepbimt/Other.git','https://github.com/sandeepbimt/Other.git'),('https://github.com/sandeepbimt/Sandium-2.git',''),('file:///tmp/Sandium-2','file:///tmp/Sandium-2'),('https://token@github.com/sandeepbimt/Sandium-2.git','https://github.com/sandeepbimt/Sandium-2.git')):
   with patch.dict(os.environ,{'CIRCLE_PROJECT_USERNAME':'sandeepbimt','RAWS_CI_REPOSITORY_URL':metadata}),patch.object(t,'git',return_value=origin):
    with self.assertRaises(ValueError):t.verified_origin(self.base)
 def test_fetch_wrong_commit_and_timeout_fail_closed(self):
  for failure in ('identity','timeout'):
   def git(root,*args):
    if args[-1]==t.seed.BASELINE_COMMIT+'^{commit}':raise subprocess.CalledProcessError(128,args)
    return 'f'*40
   with patch.object(t,'git',side_effect=git),patch.object(t,'verified_origin',return_value='https://github.com/Owner/Sandium-2.git'),patch.object(t,'run_owned',side_effect=subprocess.TimeoutExpired('fetch',120) if failure=='timeout' else None):
    with self.assertRaises(subprocess.TimeoutExpired if failure=='timeout' else ValueError):t.ensure_baseline_object(self.root,self.base,time.time())
 def partial_object_fixture(self):
  repo=self.base/'partial';repo.mkdir();t.git(repo,'init','--template=')
  t.git(repo,'config','user.name','Fixture');t.git(repo,'config','user.email','fixture@example.invalid')
  (repo/'old.txt').write_text('old baseline blob')
  t.git(repo,'add','old.txt');t.git(repo,'commit','-m','baseline')
  commit=t.git(repo,'rev-parse','HEAD');blob=t.git(repo,'rev-parse','HEAD:old.txt')
  object_path=repo/'.git/objects'/blob[:2]/blob[2:];saved=object_path.read_bytes();object_path.unlink()
  (repo/'old.txt').unlink()
  # Model a fresh --no-checkout clone: no index or working files and no prior
  # failed checkout whose staged deletion an ordinary checkout would preserve.
  (repo/'.git/index').unlink()
  # Commit/tree still resolve while one old checkout blob is physically absent.
  self.assertEqual(t.git(repo,'rev-parse',commit+'^{commit}'),commit)
  self.assertEqual(len(t.git(repo,'rev-parse',commit+'^{tree}')),40)
  return repo,commit,blob,object_path,saved
 def test_real_missing_blob_fixture_refetches_before_checkout(self):
  repo,commit,blob,path,saved=self.partial_object_fixture();calls=[]
  def fetch(argv,**kw):
   calls.append(argv);self.assertEqual(argv[-1],commit)
   self.assertIn('--refetch',argv);self.assertIn('--no-filter',argv)
   path.write_bytes(saved);(repo/'.git/FETCH_HEAD').write_text(commit+'\n')
  with patch.object(t.seed,'BASELINE_COMMIT',commit),patch.object(t,'verified_origin',return_value='https://github.com/Owner/Sandium-2.git'),patch.object(t,'run_owned',side_effect=fetch):
   self.assertFalse(t.baseline_closure_complete(repo))
   t.ensure_baseline_object(repo,self.base,time.time())
   self.assertTrue(t.baseline_closure_complete(repo));self.assertEqual(len(calls),1)
   t.git(repo,'checkout','--detach',commit);self.assertEqual(t.git(repo,'status','--porcelain','--untracked-files=no'),'')
 def test_real_missing_blob_unrepaired_fetch_fails_closed(self):
  repo,commit,blob,path,saved=self.partial_object_fixture()
  (repo/'.git/FETCH_HEAD').write_text(commit+'\n')
  with patch.object(t.seed,'BASELINE_COMMIT',commit),patch.object(t,'verified_origin',return_value='https://github.com/Owner/Sandium-2.git'),patch.object(t,'run_owned'):
   with self.assertRaisesRegex(ValueError,'closure remains incomplete'):t.ensure_baseline_object(repo,self.base,time.time())
 def test_real_local_refetch_recovers_missing_blob_closure(self):
  repo,commit,blob,path,saved=self.partial_object_fixture()
  # Build a complete bare fixture before removing the target's blob again.
  path.write_bytes(saved);remote=self.base/'complete.git'
  t.git(self.base,'clone','--bare','--no-hardlinks',str(repo),str(remote));path.unlink()
  real_run=t.run_owned;commands=[]
  def local_transport(argv,**kw):
   # Test-only local transport seam. Preserve every production fetch/negotiation
   # flag; production still forbids file:// and only accepts verified GitHub.
   self.assertIn('protocol.file.allow=never',argv)
   argv=['protocol.file.allow=always' if x=='protocol.file.allow=never' else x for x in argv]
   commands.append(argv);return real_run(argv,**kw)
  with patch.object(t.seed,'BASELINE_COMMIT',commit),patch.object(t,'verified_origin',return_value=str(remote)),patch.object(t,'run_owned',side_effect=local_transport):
   self.assertFalse(t.baseline_closure_complete(repo))
   t.ensure_baseline_object(repo,self.base,time.time())
   self.assertTrue(t.baseline_closure_complete(repo));self.assertEqual(len(commands),1)
   t.git(repo,'checkout','--detach',commit)
   self.assertEqual((repo/'old.txt').read_text(),'old baseline blob')
   self.assertEqual(t.git(repo,'status','--porcelain','--untracked-files=no'),'')
 def test_unsupported_refetch_capability_fails_before_network(self):
  response=subprocess.CompletedProcess(['git'],129,stdout='usage: git fetch --filter')
  with patch.object(t.subprocess,'run',return_value=response):
   with self.assertRaisesRegex(ValueError,'support'):t.require_full_refetch_support()
 def test_real_isolated_baseline_checkout_and_fingerprint(self):
  self.ident.stop()
  repository=Path(__file__).resolve().parents[1];session=self.base/'real'
  result=t.prepare(repository,session,time.time())
  self.assertEqual(t.git(session/'baseline','rev-parse','HEAD'),t.seed.BASELINE_COMMIT)
  self.assertEqual(result,t.seed.restore_plan())
  (session/'baseline/tools/rogue.py').write_text('raise Exception()')
  with self.assertRaisesRegex(ValueError,'import'):t.identity(session/'baseline')
if __name__=='__main__':unittest.main()
