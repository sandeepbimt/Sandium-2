"""Full-U writer/validator CLI. Native config supplies immutable cache transport."""
import argparse,json,os,sys,time,re,shutil
from pathlib import Path
import protocol,recipe,runner,process,archive,adapter
PROFILE='docs/upgrades/1.100.58/candidate-profile.json'
def context(root):
 root=Path(root);profile=json.loads((root/PROFILE).read_text())
 if profile.get('ready') is not True:raise protocol.ProtocolError('Full-U target not admitted')
 if os.environ.get('CIRCLE_BRANCH')!=profile['branch']:raise protocol.ProtocolError('wrong upgrade branch')
 scope=protocol.identity(profile,recipe.fingerprint(root));meta=root/'.full-u';meta.mkdir(exist_ok=True)
 return scope,meta

def init(root):
 scope,meta=context(root)
 (meta/'job-start').write_text(Path('/tmp/full-u-job-start').read_text())
 resume=os.environ.get('FULL_U_RESUME','none');recover=os.environ.get('FULL_U_RECOVER','none')
 for value in (resume,recover):
  if value!='none' and not re.fullmatch('[0-9a-f]{64}',value):raise protocol.ProtocolError('invalid explicit receipt digest')
 if resume!='none' and recover!='none':raise protocol.ProtocolError('choose resume or recovery, not both')
 for name,value in [('scope',scope),('expected',os.environ.get('FULL_U_RESUME','none')),('recover',os.environ.get('FULL_U_RECOVER','none'))]:(meta/name).write_text(value)

def predecessor(root,stage):
 scope,meta=context(root);f=meta/'receipt.json'
 expected=os.environ.get('FULL_U_RESUME','none') if stage==1 else 'none'
 if not f.exists():
  if stage!=1 or expected!='none':raise protocol.ProtocolError('missing exact compatible predecessor')
  (meta/'archive-key').write_text('fresh-no-archive');return None
 receipt=json.loads(f.read_text());p=protocol.verify(receipt,scope,True)
 if expected!='none' and receipt['id']!=expected:raise protocol.ProtocolError('wrong explicit receipt')
 if p['pipeline']>int(os.environ['CIRCLE_PIPELINE_NUMBER']):raise protocol.ProtocolError('future receipt on old rerun')
 if stage>1 and (p.get('workflow'),p.get('stage'))!=(os.environ['CIRCLE_WORKFLOW_ID'],stage-1):raise protocol.ProtocolError('wrong prior stage')
 (meta/'archive-key').write_text(p['archive_key']);return receipt

HOST_PREPARED=set()
def ensure_host(root,scope,start,stage):
 key=(str(root.resolve()),scope)
 if key in HOST_PREPARED:return
 result=runner.bounded_host(root,scope,adapter.action(root,'prepare-host'),start,stage)
 if result['outcome']!='success':raise protocol.ProtocolError('bounded host preparation failed: '+result['outcome'])
 HOST_PREPARED.add(key)

def verify_phase(root,scope,phase,start,stage='before-archive'):
 if phase=='source-acquiring':return
 if phase=='build-ready':ensure_host(root,scope,start,stage)
 result=runner.bounded_verify(root,scope,adapter.commands(root)[phase],start,stage=stage)
 if result['outcome']!='success':raise protocol.ProtocolError('bounded target verifier failed: '+result['outcome'])

def write(root,stage):
 scope,meta=context(root);work=root/'brave-work';start=int((meta/'job-start').read_text())
 receipt=predecessor(root,stage)
 if receipt:
  data=archive.restore_candidate(root,receipt,scope,lambda phase,w:verify_phase(root,scope,phase,start))
  phase=data['phase']
  if data.get('history_sample'):
   hp=work/'.sandium/full-u-history.json';history=json.loads(hp.read_text()) if hp.is_file() else [];history.append(data['history_sample']);protocol.atomic(hp,history[-10:])
  # Remove only verified archive transport after complete extraction, never source.
  manifest,shards=archive.native.load_manifest(root)
  for item in manifest['shards']:
   f=shards/item['name']
   if f.is_symlink() or not f.is_file():raise protocol.ProtocolError('unsafe transport cleanup')
  for item in manifest['shards']:(shards/item['name']).unlink()
  (root/archive.native.MANIFEST_NAME).unlink()
 else:protocol.owned(work,scope);phase='source-acquiring'
 if phase=='source-synced':phase='product-preparing'
 events=[]
 while True:
  result=runner.execute(root,scope,phase,adapter.action(root,phase),adapter.commands(root),start)
  events.append(result)
  if phase=='build-ready' and result['status']['outcome']=='success':
   apk=runner.bounded_verify(root,scope,adapter.action(root,'verify-apk'),start)
   if apk['outcome']=='success':
    result['apk_sha256']=json.loads((root/'brave-apk/full-u-apk.json').read_text())['apk_sha256']
   else:result['status']=apk
  if result['status']['outcome']!='success' or phase=='build-ready':break
  phase='product-preparing' if result['phase_after']=='source-synced' else result['phase_after']
 # Invalid build verification is not reusable compiled state. Do not silently
 # label it build-ready. Until a verified source-only fallback is constructed,
 # preserve as quarantine and retain the previous accepted reference.
 protocol.atomic(meta/'phase-timeline.json',events)
 protocol.atomic(meta/'result.json',result)
 metrics=work/'src/out/android_Release_arm64/full-u-siso.jsonl'
 if metrics.is_file():shutil.copyfile(metrics,meta/'siso-metrics.jsonl')


def capture(root,stage):
 scope,meta=context(root);start=int((meta/'job-start').read_text());result=json.loads((meta/'result.json').read_text())
 phase=result['phase_after'];outcome=result['status']['outcome'];source_only=False
 if phase=='build-ready' and outcome in ('success','time-slice','reserve-exhausted'):
  try:verify_phase(root,scope,'build-ready',start)
  except Exception:outcome='verification-timeout'
 if outcome in ('hard-failure','verification-timeout') and phase!='source-acquiring':
  verify_phase(root,scope,'source-synced',start)
  phase='source-synced';outcome='recovered-source';source_only=True
 elif outcome=='verification-timeout':outcome='time-slice'
 elif phase!='source-acquiring':verify_phase(root,scope,phase,start)
 plan=dict(scope=scope,phase=phase,outcome=outcome,source_only=source_only,apk_sha256=result.get('apk_sha256') if outcome=='success' else None)
 protocol.atomic(meta/'capture-plan.json',plan)
 admission=runner.current_plan(root,start)
 if not admission['can_capture']:raise protocol.ProtocolError('insufficient archive time/disk; prior reference retained')
 # Pack has no nested process-group verifier. Tar/zstd remain in this owned group.
 seconds=admission['archive_seconds']+240
 began=time.monotonic()
 status=process.run([sys.executable,str(Path(__file__).resolve()),'pack','--root',str(root),'--stage',str(stage)],root,seconds,lambda:time.time()<admission['deadline']-admission['upload_seconds']-300,env=os.environ.copy())
 if status['outcome']!='success':raise protocol.ProtocolError('archive did not complete; no publication')
 verify_phase(root,scope,phase,start,'after-archive')
 manifest=archive.native.load_manifest(root)[0]
 protocol.atomic(meta/'archive-stats.json',{'source_bytes':manifest['source_bytes'],'archive_bytes':manifest['archive_bytes'],'archive_seconds':time.monotonic()-began})


def pack(root,stage):
 scope,meta=context(root);plan=json.loads((meta/'capture-plan.json').read_text())
 if plan['scope']!=scope:raise protocol.ProtocolError('wrong preverified capture plan')
 def proof(phase,work):
  if phase!=plan['phase']:raise protocol.ProtocolError('capture phase changed')
 candidate=archive.capture(root,scope,plan['phase'],plan['outcome'],int(os.environ['CIRCLE_PIPELINE_NUMBER']),os.environ['CIRCLE_SHA1'],proof,apk_sha256=plan['apk_sha256'],source_only=plan['source_only'])
 candidate['payload'].update(workflow=os.environ['CIRCLE_WORKFLOW_ID'],stage=stage)
 candidate=protocol.envelope(candidate['payload']);protocol.atomic(meta/'candidate.json',candidate)
 (meta/'candidate-id').write_text(candidate['id']);(meta/'archive-key').write_text(candidate['payload']['archive_key']);(meta/'expected-pending').write_text(candidate['id'])

def accept(root,stage):
 scope,meta=context(root);candidate=json.loads((meta/'candidate.json').read_text());data=protocol.verify(candidate,scope)
 expected=os.environ.get('FULL_U_RECOVER','none')
 if expected!='none':
  if candidate['id']!=expected:raise protocol.ProtocolError('wrong explicit pending recovery')
 elif (data['pipeline'],data.get('workflow'),data.get('stage'))!=(int(os.environ['CIRCLE_PIPELINE_NUMBER']),os.environ['CIRCLE_WORKFLOW_ID'],stage):raise protocol.ProtocolError('wrong pending producer')
 start=int((meta/'job-start').read_text())
 def apk_verify(work):
  result=runner.bounded_verify(root,scope,adapter.action(root,'verify-apk'),start,stage='fresh-validator')
  if result['outcome']!='success':raise protocol.ProtocolError('fresh restored APK verification failed')
  return json.loads((root/'brave-apk/full-u-apk.json').read_text())['apk_sha256']
 archive.restore_candidate(root,candidate,scope,lambda phase,w:verify_phase(root,scope,phase,start,'fresh-validator'),apk_verify)
 receipt=archive.accept_after_fresh_restore(candidate,scope,root,meta/'accepted.json')
 (meta/'receipt.json').write_bytes((meta/'accepted.json').read_bytes());(meta/'accepted-id').write_text(receipt['id']);(meta/'expected-published').write_text(receipt['id'])
 print('FULL_U_ACCEPTED_RECEIPT='+receipt['id'])

def check(root,kind):
 scope,meta=context(root);name='candidate.json' if kind=='pending' else 'receipt.json'
 r=json.loads((meta/name).read_text());protocol.verify(r,scope,kind!='pending')
 if r['id']!=(meta/('expected-'+kind)).read_text():raise protocol.ProtocolError('native immutable reference readback collision')

def upload_start(root,stage):
 scope,meta=context(root);(meta/'upload-start').write_text(str(time.monotonic()))
def upload_end(root,stage):
 scope,meta=context(root);elapsed=time.monotonic()-float((meta/'upload-start').read_text())
 stats=json.loads((meta/'archive-stats.json').read_text());stats.update(upload_seconds=max(.001,elapsed),provenance='native cache save elapsed workflow '+os.environ['CIRCLE_WORKFLOW_ID']+' stage '+str(stage))
 candidate=json.loads((meta/'candidate.json').read_text());candidate['payload']['history_sample']=stats
 candidate=protocol.envelope(candidate['payload']);protocol.atomic(meta/'candidate.json',candidate)
 (meta/'candidate-id').write_text(candidate['id']);(meta/'expected-pending').write_text(candidate['id'])
 protocol.atomic(meta/'save-timing.json',stats)

def completed(root,stage):
 scope,meta=context(root)
 if not (meta/'receipt.json').is_file():return False
 receipt=json.loads((meta/'receipt.json').read_text());data=protocol.verify(receipt,scope,True)
 if stage==1:
  expected=os.environ.get('FULL_U_RESUME','none')
  if expected=='none' or receipt['id']!=expected:raise protocol.ProtocolError('wrong explicit completion receipt')
  return data.get('apk_sha256') is not None
 if data['pipeline']!=int(os.environ['CIRCLE_PIPELINE_NUMBER']) or data.get('workflow')!=os.environ['CIRCLE_WORKFLOW_ID'] or data.get('stage') not in range(1,stage):raise protocol.ProtocolError('wrong completion producer')
 return data.get('apk_sha256') is not None

def finish(root,stage):
 scope,meta=context(root);data=protocol.verify(json.loads((meta/'receipt.json').read_text()),scope,True)
 if data['outcome']=='recovered-source':raise SystemExit('FULL_U_SOURCE_RECOVERED: output quarantined; manual repair required before next run')
 if data['outcome']=='reserve-exhausted':raise SystemExit('FULL_U_RESOURCE_HOLD: verified source saved; resource decision required')
 if stage==5 and data.get('apk_sha256') is None:raise SystemExit('FULL_U_INCOMPLETE: verified receipt saved for explicit continuation')

def main():
 p=argparse.ArgumentParser();p.add_argument('command',choices=['init','predecessor','write','capture','pack','accept','check-pending','check-published','finish','completed','upload_start','upload_end']);p.add_argument('--root',type=Path,required=True);p.add_argument('--stage',type=int,default=1);a=p.parse_args();root=a.root.resolve()
 if a.stage not in range(1,6):raise protocol.ProtocolError('invalid stage')
 if a.command in ('init',):init(root)
 elif a.command=='completed':raise SystemExit(0 if completed(root,a.stage) else 1)
 elif a.command.startswith('check-'):check(root,a.command[6:])
 else:globals()[a.command](root,a.stage)
if __name__=='__main__':
 try:main()
 except Exception as error:
  # Preserve a readable failure artifact even if no phase result was produced.
  try:
   index=sys.argv.index('--root');root=Path(sys.argv[index+1]);protocol.atomic(root/'.full-u/error.json',{'error_type':type(error).__name__,'prior_reference_preserved':True})
  except Exception:pass
  raise

