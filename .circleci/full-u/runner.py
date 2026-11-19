"""Resource-bounded phase execution, including pre/post verification processes."""
import json,shutil,subprocess,time,os
from pathlib import Path
import budget,protocol,process
NEXT={'source-acquiring':'source-synced','product-preparing':'build-ready','build-ready':'build-ready'}
def measure(work):
 return max(1,int(subprocess.check_output(['du','-sb',str(work)],text=True,timeout=20).split()[0]))
def current_plan(root,start,clock=time.time):
 work=Path(root)/'brave-work';hp=work/'.sandium/full-u-history.json'
 history=json.loads(hp.read_text()) if hp.is_file() else []
 return budget.plan(start,clock(),measure(work),shutil.disk_usage(work).free,history)
def bounded_verify(root,scope,argv,start,clock=time.time,stage='before-archive'):
 if not isinstance(argv,list) or not argv or not all(isinstance(x,str) for x in argv):raise protocol.ProtocolError('verifier argv required')
 root=Path(root);p=current_plan(root,start,clock)
 # Use the verification reserve, never the archive/upload/safety budget.
 if stage not in ('before-archive','after-archive','fresh-validator'):raise protocol.ProtocolError('unknown verification budget stage')
 reserve=(p['archive_seconds'] if stage=='before-archive' else 0)+(p['upload_seconds'] if stage!='fresh-validator' else 0)+360
 seconds=min(240,p['remaining_seconds']-reserve)
 if seconds<1:return dict(outcome='verification-timeout',exit_code=None)
 result=process.run(argv,root,seconds,lambda:clock()<p['deadline']-reserve,
                    env=dict(os.environ,FULL_U_SCOPE=scope,CIRCLE_WORKING_DIRECTORY=str(root)))
 if result['outcome']=='time-slice':result['outcome']='verification-timeout'
 return result

def bounded_host(root,scope,argv,start,stage='before-archive',clock=time.time):
 # Explicit mutating OS setup precedes read-only graph/APK validation.
 p=current_plan(root,start,clock)
 reserve=(p['archive_seconds']+p['upload_seconds']+600 if stage=='before-archive' else 600)
 seconds=min(600,p['remaining_seconds']-reserve)
 if seconds<1:return dict(outcome='host-budget-exhausted',exit_code=None)
 return process.run(argv,Path(root),seconds,lambda:clock()<p['deadline']-reserve,
                    env=dict(os.environ,FULL_U_SCOPE=scope,CIRCLE_WORKING_DIRECTORY=str(root)))

def execute(root,scope,phase,argv,verifiers,start,clock=time.time):
 root=Path(root);work=protocol.owned(root/'brave-work',scope)
 if phase not in NEXT:raise protocol.ProtocolError('non-executable phase')
 if not isinstance(verifiers,dict):raise protocol.ProtocolError('verification must be bounded argv mapping, not callback')
 pre=None
 if phase=='build-ready':pre=bounded_verify(root,scope,verifiers[phase],start,clock)
 initial=current_plan(root,start,clock);initial_free=initial['free_bytes'];size=measure(work)
 hp=work/'.sandium/full-u-history.json';history=json.loads(hp.read_text()) if hp.is_file() else []
 def guard():
  free=shutil.disk_usage(work).free
  return budget.plan(start,clock(),size+max(0,initial_free-free),free,history)['can_work']
 outcome={'outcome':'reserve-exhausted','exit_code':None,'duration_seconds':0}
 if pre and pre['outcome']!='success':outcome=pre
 elif initial['can_work']:
  try:outcome=process.run(argv,root,initial['work_seconds'],guard,env=dict(os.environ,FULL_U_SCOPE=scope,CIRCLE_WORKING_DIRECTORY=str(root)))
  except Exception as e:outcome={'outcome':'hard-failure','error_type':type(e).__name__,'exit_code':None}
 after=phase;post=None
 if outcome['outcome']=='success':
  post=bounded_verify(root,scope,verifiers[NEXT[phase]],start,clock)
  if post['outcome']=='success':after=NEXT[phase]
  else:outcome=post
 final=current_plan(root,start,clock)
 result=dict(schema=1,scope=scope,phase_before=phase,phase_after=after,status=outcome,verification_before=pre,verification_after=post,
             initial_budget=initial,final_budget=final,cache_hits=None)
 protocol.atomic(work/'.sandium/full-u-phase-result.json',result)
 return result
