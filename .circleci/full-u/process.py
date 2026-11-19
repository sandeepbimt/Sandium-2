"""Own one subprocess group; stop descendants before any workspace snapshot."""
import os,signal,subprocess,time

def run(argv,cwd,seconds,guard,grace=30,env=None):
 if seconds<1:raise ValueError('no admitted work budget')
 child=subprocess.Popen(argv,cwd=cwd,start_new_session=True,env=env)
 began=time.monotonic();deadline=began+seconds;status='hard-failure';code=None
 try:
  while True:
   code=child.poll()
   if code is not None:status='success' if code==0 else 'hard-failure';break
   if time.monotonic()>=deadline or not guard():
    status='time-slice'
    try:os.killpg(child.pid,signal.SIGTERM)
    except ProcessLookupError:pass
    try:child.wait(timeout=grace)
    except subprocess.TimeoutExpired:pass
    break
   time.sleep(min(.25,max(0,deadline-time.monotonic())))
 finally:
  try:os.killpg(child.pid,signal.SIGKILL)
  except ProcessLookupError:pass
  code=child.wait()
 return dict(outcome=status,exit_code=code,duration_seconds=time.monotonic()-began)
