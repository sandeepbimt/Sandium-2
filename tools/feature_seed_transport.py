"""Explicit exact-1396 local transport coordinator. Native cache I/O belongs to CI.

No receipt-supplied commands, feature imports in the baseline interpreter, cache
publication, compatibility overrides, completion shortcuts or cross-device copies.
"""
import argparse,json,math,os,re,signal,subprocess,sys,time
from pathlib import Path
import baseline_seed as seed

MANIFEST='raw-workspace-checkpoint.manifest.json'
SHARDS='raw-workspace-checkpoint.shards'
POST_RESTORE_RESERVE=1620
CLEANUP_GRACE=10
# Fixed reviewed program; argv contains only the isolated root and phase.
BASELINE_PROGRAM='''import sys,signal
def interrupted(signum,frame): raise SystemExit('Owned transport deadline reached')
signal.signal(signal.SIGTERM,interrupted)
from pathlib import Path
root=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(root/'tools'))
import ci_full as c
assert c.ROOT == root and c.D.ROOT == root
assert c.fingerprint() == 'b35abf73bb0a0a5998baeee4261715cbe73c8d55512c3a948cd6940590689843'
assert c.D.c.COMPAT == 'raws-full-v1-'+c.fingerprint()
phase=sys.argv[2]
if phase == 'identity': pass
elif phase == 'select': c.gate(); c.D.select(precheck=True)
else: c.run(phase)
if phase == 'restore-finish': c.f.cli.quiesce(c.D.LEGACY,root/'work/source')
'''

def caller_gate():
 """The feature opt-in is checked before binding the old validation context."""
 expected={'CIRCLE_BRANCH':'raw-sandium/native-ui158','RAWS_NATIVE_FEATURE_SEED':'true',
           'RAWS_STAGE':'1','CIRCLE_PROJECT_REPONAME':'Sandium-2','RAWS_CHECKPOINT_REVIEWED':'true'}
 if any(os.environ.get(k)!=v for k,v in expected.items()):
  raise ValueError('Explicit reviewed native-feature seed caller required')

def write_new(path,value):
 with Path(path).open('x') as f:json.dump(value,f,sort_keys=True);f.flush();os.fsync(f.fileno())

def git(root,*args):
 env={k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
 env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null')
 return subprocess.check_output(['git','-c','core.hooksPath=/dev/null','-C',str(root),*args],env=env,text=True).strip()

def checked(root,relative):
 root=Path(root).resolve();p=root/relative
 for component in [p,*p.parents]:
  if component==root:break
  if component.is_symlink():raise ValueError('Symlink transport path: '+relative)
 if not p.resolve().is_relative_to(root):raise ValueError('Escaping transport path')
 return p

def budget(start):
 if type(start) not in (int,float) or not math.isfinite(start) or start>time.time()+1:raise ValueError('Invalid original job start')
 remaining=3300-(time.time()-start)-POST_RESTORE_RESERVE-CLEANUP_GRACE
 if remaining<30:raise ValueError('Insufficient original job budget')
 return remaining

def identity(root):
 if git(root,'rev-parse','HEAD')!=seed.BASELINE_COMMIT:raise ValueError('Wrong baseline checkout')
 if git(root,'status','--porcelain','--untracked-files=no'):raise ValueError('Modified baseline tracked files')
 # Ignored Python overlays are as dangerous as tracked changes to import code.
 for rel in ('tools','.circleci'):
  if git(root,'ls-files','--others',rel):raise ValueError('Unreviewed baseline import input')
  tracked=set(git(root,'ls-files',rel).splitlines())
  for p in (root/rel).rglob('*.py'):
   if p.is_symlink() or p.relative_to(root).as_posix() not in tracked:raise ValueError('Unreviewed baseline import')
 return git(root,'rev-parse','HEAD^{tree}')

def context(session,phase):
 caller_gate()
 session=Path(session).resolve();c=seed.load(checked(session,'context.json'))
 if c['phase']!=phase:raise ValueError('Partial, repeated or out-of-order transport')
 if c['job']!={k:os.environ.get(k) for k in ('CIRCLE_WORKFLOW_ID','CIRCLE_BUILD_NUM')}:raise ValueError('Transport belongs to another job')
 if seed.restore_plan()!=seed.load(checked(session,'plan.json')):raise ValueError('Expired or changed restore plan')
 budget(c['job_start_epoch'])
 if identity(session/'baseline')!=c['tree']:raise ValueError('Baseline tree changed')
 return session,c

def phase(session,c,status):
 c={**c,'phase':status};tmp=session/'context.tmp'
 write_new(tmp,c);tmp.replace(session/'context.json');return c

def run_owned(argv,*,cwd,env,seconds,deadline_epoch):
 """Bound an owned process group, including descendants after leader exit.

 Both monotonic duration and original wall-clock deadline constrain execution.
 Cleanup grace is withheld separately, preserving the full downstream reserve.
 No unrelated process is signalled; a failed/timeout restore is never admitted.
 """
 if seconds<=0:raise ValueError('No subprocess budget')
 if deadline_epoch<=time.time():raise subprocess.TimeoutExpired(argv,seconds)
 started=time.monotonic()
 process=subprocess.Popen(argv,cwd=cwd,env=env,start_new_session=True)
 known={}
 def descendants():
  # Legacy run_bounded starts a separate session. Track PID birth identities so
  # cleanup also reaches that owned group without signalling recycled PIDs.
  table={}
  for path in Path('/proc').glob('[0-9]*/stat'):
   try:
    fields=path.read_text().rsplit(')',1)[1].split()
    table[int(path.parent.name)]=(int(fields[1]),fields[19])
   except (OSError,ValueError,IndexError):continue
  live={pid for pid,stamp in known.items() if pid in table and table[pid][1]==stamp}
  live.add(process.pid)
  while True:
   added={pid for pid,(parent,stamp) in table.items() if parent in live}-live
   if not added:break
   live.update(added)
  for pid in live:
   if pid in table:known[pid]=table[pid][1]
  return [pid for pid in live if pid in table and known.get(pid)==table[pid][1]]
 def signal_group(sig):
  try:os.killpg(process.pid,sig)
  except ProcessLookupError:pass
  for pid in descendants():
   try:
    if os.getpgid(pid)!=process.pid:os.kill(pid,sig)
   except ProcessLookupError:pass
 try:
  while True:
   descendants()
   remaining=min(seconds-(time.monotonic()-started),deadline_epoch-time.time())
   if remaining<=0:raise subprocess.TimeoutExpired(argv,seconds)
   try:code=process.wait(timeout=min(0.25,remaining));break
   except subprocess.TimeoutExpired:continue
  if code:raise subprocess.CalledProcessError(code,argv)
 except BaseException:
  signal_group(signal.SIGTERM)
  try:process.wait(timeout=CLEANUP_GRACE)
  except subprocess.TimeoutExpired:pass
  raise
 finally:
  # The leader may have exited while a grandchild ignored TERM or kept writing.
  signal_group(signal.SIGKILL)
  process.wait()
 return code

def baseline(session,c,command):
 caller_gate()
 env={k:v for k,v in os.environ.items() if not k.startswith(('PYTHON','GIT_'))}
 # Old harness validates its original branch only in this isolated subprocess.
 # The actual native-feature caller has already passed caller_gate above.
 env.update(CIRCLE_BRANCH='raw-sandium/official158',CIRCLE_WORKING_DIRECTORY=str(session/'baseline'),CIRCLE_SHA1=seed.BASELINE_COMMIT,RAWS_STAGE='1',PYTHONDONTWRITEBYTECODE='1')
 run_owned([sys.executable,'-I','-B','-c',BASELINE_PROGRAM,str(session/'baseline'),command],cwd=session/'baseline',env=env,seconds=budget(c['job_start_epoch']),deadline_epoch=c['job_start_epoch']+3300-POST_RESTORE_RESERVE-CLEANUP_GRACE)

def verified_origin(repository):
 """Accept only the repository identified by current CircleCI job metadata.

 No URL helpers, credentials in URLs, arbitrary hosts, paths or branch discovery.
 The source checkout's origin must match both authenticated CI repository fields.
 """
 def identity(url):
  match=re.fullmatch(r'(?:https://github[.]com/|git@github[.]com:|ssh://git@github[.]com/)([A-Za-z0-9_-]+)/([A-Za-z0-9_.-]+?)(?:[.]git)?',url)
  if not match:raise ValueError('Unsupported baseline origin')
  return tuple(x.lower() for x in match.groups())
 origin=git(repository,'remote','get-url','origin')
 expected=(os.environ.get('CIRCLE_PROJECT_USERNAME','').lower(),'sandium-2')
 if not expected[0] or identity(origin)!=expected or identity(os.environ.get('CIRCLE_REPOSITORY_URL',''))!=expected:
  raise ValueError('Baseline origin does not match current CI repository')
 return origin

def ensure_baseline_object(root,repository,job_start_epoch):
 try:actual=git(root,'rev-parse','--verify',seed.BASELINE_COMMIT+'^{commit}')
 except subprocess.CalledProcessError:actual=None
 if actual is None:
  origin=verified_origin(repository)
  env={k:v for k,v in os.environ.items() if not k.startswith(('GIT_','PYTHON'))}
  env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null',GIT_TERMINAL_PROMPT='0')
  seconds=min(120,budget(job_start_epoch))
  # Fetch only the frozen object into the isolated clone, never a moving branch.
  command=['git','-c','core.hooksPath=/dev/null','-c','protocol.file.allow=never',
           '-c','protocol.ext.allow=never','fetch','--no-tags','--depth=1',origin,seed.BASELINE_COMMIT]
  run_owned(command,cwd=root,env=env,seconds=seconds,
            deadline_epoch=min(time.time()+seconds,job_start_epoch+3300-POST_RESTORE_RESERVE-CLEANUP_GRACE))
  if git(root,'rev-parse','--verify','FETCH_HEAD^{commit}')!=seed.BASELINE_COMMIT:
   raise ValueError('Fetched baseline identity mismatch')
  actual=git(root,'rev-parse','--verify',seed.BASELINE_COMMIT+'^{commit}')
 if actual!=seed.BASELINE_COMMIT:raise ValueError('Baseline object identity mismatch')
 tree=git(root,'rev-parse','--verify',seed.BASELINE_COMMIT+'^{tree}')
 if not re.fullmatch('[0-9a-f]{40}',tree):raise ValueError('Invalid baseline tree identity')
 return tree

def prepare(repository,session,job_start_epoch):
 caller_gate()
 plan=seed.restore_plan();budget(job_start_epoch)
 job={k:os.environ.get(k) for k in ('CIRCLE_WORKFLOW_ID','CIRCLE_BUILD_NUM')}
 if not all(job.values()):raise ValueError('Current job identity required')
 session=Path(session).absolute()
 if session.exists() or session.is_symlink():raise ValueError('Transport session must be fresh')
 session.mkdir();root=session/'baseline'
 # Tiny harness only; this does not clone Chromium or copy the archived workspace.
 git(Path(repository).resolve(),'clone','--no-hardlinks','--no-checkout','--template=',str(Path(repository).resolve()),str(root))
 ensure_baseline_object(root,Path(repository).resolve(),job_start_epoch)
 git(root,'checkout','--detach',seed.BASELINE_COMMIT)
 c=dict(phase='preparing',job=job,job_start_epoch=job_start_epoch,tree=identity(root))
 write_new(session/'plan.json',plan);write_new(session/'context.json',c)
 state=root/'.checkpoint-state';state.mkdir();write_new(state/'job-start.json',{'epoch':job_start_epoch})
 baseline(session,c,'identity');phase(session,c,'prepared')
 return plan

def select(session,receipt):
 session,c=context(session,'prepared');raw=Path(receipt)
 if raw.is_symlink() or not raw.is_file():raise ValueError('Missing exact remote receipt')
 data=raw.read_bytes()
 if data!=(seed.EVIDENCE/'seed-1396-receipt.json').read_bytes():raise ValueError('Remote receipt bytes differ from frozen evidence')
 root=session/'baseline';head=root/'.checkpoint-head'
 if head.exists():raise ValueError('Colliding baseline head')
 phase(session,c,'selecting');head.mkdir();(head/'receipt.json').write_bytes(data)
 baseline(session,c,'select')
 if seed.load(root/'.checkpoint-state/selected.json')!=seed.evidence():raise ValueError('Baseline did not select exact receipt')
 phase(session,c,'selected')

def move_pairs(pairs):
 # Preflight every path before the first rename. No shutil.move copy fallback.
 for src,dst in pairs:
  if src.is_symlink() or not src.exists() or dst.exists() or dst.is_symlink():raise ValueError('Missing/colliding transport path')
  if src.stat().st_dev!=dst.parent.stat().st_dev:raise ValueError('Same-filesystem move required')
 moved=[]
 try:
  for src,dst in pairs:src.rename(dst);moved.append((src,dst))
 except BaseException:
  for src,dst in reversed(moved):dst.rename(src)
  raise

def restore(session,incoming):
 session,c=context(session,'selected');root=session/'baseline';incoming=Path(incoming).resolve()
 manifest=checked(incoming,MANIFEST);shards=checked(incoming,SHARDS)
 if seed.file_sha(manifest)!=seed.restore_plan()['manifest_sha256']:raise ValueError('Wrong frozen manifest')
 m=seed.load(manifest)
 if len(m.get('shards',[]))!=8:raise ValueError('Eight shards required')
 for item in m['shards']:
  name=item['name']
  if Path(name).name!=name:raise ValueError('Unsafe shard name')
  p=checked(shards,name)
  if not p.is_file() or p.stat().st_size!=item['size_bytes']:raise ValueError('Missing/partial shard')
 for rel in ('restored-proof.json','sequential-restore.json'):
  if (root/'.checkpoint-state'/rel).exists():raise ValueError('Colliding restore proof')
 phase(session,c,'restoring')
 move_pairs([(manifest,root/MANIFEST),(shards,root/SHARDS)])
 baseline(session,c,'restore-base');baseline(session,c,'restore-finish')
 proof=seed.load(root/'.checkpoint-state/restored-proof.json')
 if proof!={'receipt':seed.RECEIPT,'head':seed.BASE}:raise ValueError('Incorrect current-job restore proof')
 write_new(session/'current-job-proof.json',dict(job=c['job'],proof=proof,selected=seed.evidence()))
 phase(session,c,'restored')

def adopt(session,feature_root):
 session,c=context(session,'restored');root=session/'baseline';feature=Path(feature_root).resolve()
 if feature==root or not (feature/'.git').exists():raise ValueError('Separate feature checkout required')
 proof=seed.load(session/'current-job-proof.json')
 expected=dict(job=c['job'],proof={'receipt':seed.RECEIPT,'head':seed.BASE},selected=seed.evidence())
 if proof!=expected:raise ValueError('Wrong current-job proof')
 state=root/'.checkpoint-state'
 if seed.load(state/'restored-proof.json')!=proof['proof'] or seed.load(state/'selected.json')!=proof['selected']:raise ValueError('Restored state changed')
 for rel in ('work','.checkpoint-state','.baseline-seed',*seed.STALE[4:]):
  p=checked(feature,rel)
  if p.exists() or p.is_symlink():raise ValueError('Feature destination is not fresh: '+rel)
 phase(session,c,'adopting')
 move_pairs([(checked(root,'work'),feature/'work'),(state,feature/'.checkpoint-state')])
 phase(session,c,'adopted')
 return dict(baseline_checkout=str(root),feature_root=str(feature),proof=proof['proof'],status='awaiting-baseline-seed-transition',apk_verified=False,checkpoint_accepted=False)

def main():
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
 for action in ('prepare','select','restore','adopt'):
  q=sub.add_parser(action);q.add_argument('--session',required=True)
  if action=='prepare':q.add_argument('--repository',required=True);q.add_argument('--job-start-epoch',required=True,type=float)
  if action=='select':q.add_argument('--receipt',required=True)
  if action=='restore':q.add_argument('--incoming',required=True)
  if action=='adopt':q.add_argument('--feature-root',required=True)
 a=vars(p.parse_args());action=a.pop('action');print(json.dumps(globals()[action](**a),sort_keys=True))
if __name__=='__main__':main()
