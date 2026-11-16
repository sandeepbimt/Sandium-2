import json,os,pathlib,subprocess,tempfile,unittest,yaml,time,signal,sys,shlex,re
ROOT=pathlib.Path(__file__).resolve().parents[2]
class FailFast(unittest.TestCase):
 def run_case(self,body, budget=3, audit_delay=0, recovery=None, recovery_return_delay=0):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp);(p/'out').mkdir();(p/'state').mkdir();(p/'bin').mkdir();(p/'.circleci/scripts').mkdir(parents=True);(p/'.circleci/original-full').mkdir(parents=True)
   (p/'.circleci/scripts/capture-brave-siso-checkpoint.sh').write_text('exit 0\n')
   (p/'.circleci/original-full/run_budget.py').write_bytes((ROOT/'.circleci/original-full/run_budget.py').read_bytes())
   (p/'.circleci/scripts/verify-brave-remote-metrics.py').write_text('import time; time.sleep('+str(audit_delay)+')\n')
   if recovery is not None:
    (p/'.circleci/scripts/recover-siso-missing-cas-inputs.sh').write_text(recovery+'\n')
   if recovery_return_delay:
    # Simulate scheduling delay after a successful supervisor return, without
    # altering the generated wrapper or its deadline/classification branches.
    stub=p/'bin/python3'
    stub.write_text('#!/bin/bash\n'+shlex.quote(sys.executable)+' "$@"\nrc=$?\ncase "$*" in *recover-siso-missing-cas-inputs.sh*) sleep '+str(recovery_return_delay)+';; esac\nexit "$rc"\n')
    stub.chmod(0o755)
   tool=p/'bin/autoninja' ;tool.write_text('#!/bin/bash\n'+body+'\n');tool.chmod(0o755)
   cfg=yaml.safe_load((ROOT/'.circleci/config.yml').read_text());steps=cfg['jobs']['brave-android-staged-build']['steps']
   cmd=next(s['run']['command'] for s in steps if isinstance(s,dict) and s.get('run',{}).get('name')=='Build bounded Brave Android APK slice')
   # Execute the generated build/recovery/classification/status body, with only preflight omitted.
   cmd='set -euo pipefail\n'+cmd[cmd.index('BUILD_RC=0\n'):]
   cmd=cmd.replace('<< parameters.stage_index >>','1').replace('<< pipeline.parameters.sandium_build_mode >>','full').replace('STAGE_BUILD_BUDGET_SECONDS=1200','STAGE_BUILD_BUDGET_SECONDS='+str(budget))
   env={**os.environ,'ROOT':str(p),'OUT':str(p/'out'),'STATUS_DIR':str(p/'state'),'BUILD_STATUS':str(p/'state/status'),'PATH':str(p/'bin')+':'+os.environ['PATH']}
   run=subprocess.run(['bash','-c',cmd],env=env,capture_output=True,text=True,timeout=20)
   self.last_output=run.stdout+'\n'+run.stderr
   status=dict(line.split('=',1) for line in (p/'state/status').read_text().splitlines())
   # Model default CircleCI on_success sequencing; failing command must prevent archive action.
   if run.returncode==0:(p/'archive').touch()
   return run.returncode,status,(p/'archive').exists()
 def test_success(self):
  rc,s,saved=self.run_case('exit 0');self.assertEqual(rc,0);self.assertEqual(s['BUILD_REASON'],'BUILD_COMMAND_SUCCESS');self.assertTrue(saved)
 def test_action_failure(self):
  for n in (1,2,124,130,137,143):
   rc,s,saved=self.run_case('exit '+str(n));self.assertEqual(rc,n);self.assertEqual(s['BUILD_HANDOFF_ALLOWED'],'false');self.assertFalse(saved)
 def test_actual_timeout(self):
  rc,s,saved=self.run_case('exec sleep 10',1);self.assertEqual(rc,0);self.assertEqual(s['BUILD_TIME_SLICE_EXPIRED'],'true');self.assertTrue(saved)
 def test_failure_not_reclassified_by_elapsed_time(self):
  rc,s,saved=self.run_case('echo x > \"$OUT/$3\"; exit 1',1,audit_delay=2);self.assertEqual(rc,1);self.assertEqual(s['BUILD_REASON'],'ACTION_FAILED');self.assertFalse(saved)
 def cas_initial(self, resume='exit 0'):
  return """if [ ! -e "$STATUS_DIR/attempted" ]; then
 touch "$STATUS_DIR/attempted"
 echo 'rpc error: code = FailedPrecondition desc = download inputs: could not fetch inputs: Digest hash:123 not found' > "$OUT/siso_output"
 exit 1
fi
rm -f "$OUT/siso_output"
"""+resume
 def test_cas_failure_no_handoff(self):
  for code in (9,124,130,137,143):
   rc,s,saved=self.run_case(self.cas_initial(),recovery='exit '+str(code))
   self.assertEqual(rc,code);self.assertEqual(s['CAS_RECOVERY_ATTEMPTS'],'1');self.assertEqual(s['BUILD_HANDOFF_ALLOWED'],'false');self.assertFalse(saved)
 def test_cas_recovery_timeout_handoff(self):
  rc,s,saved=self.run_case(self.cas_initial(),budget=3,recovery='exec sleep 10')
  self.assertEqual(rc,0,(s,self.last_output));self.assertEqual(s['CAS_RECOVERY_ATTEMPTS'],'1');self.assertEqual(s['BUILD_TIME_SLICE_EXPIRED'],'true');self.assertTrue(saved)
 def test_cas_resume_failure_no_handoff(self):
  rc,s,saved=self.run_case(self.cas_initial('exit 7'),recovery='exit 0')
  self.assertEqual(rc,7);self.assertEqual(s['CAS_RECOVERY_ATTEMPTS'],'1');self.assertEqual(s['BUILD_HANDOFF_ALLOWED'],'false');self.assertFalse(saved)
 def test_cas_successful_recovery_budget_exhausted(self):
  rc,s,saved=self.run_case(self.cas_initial('exit 77'),budget=3,recovery='exit 0',recovery_return_delay=4)
  self.assertEqual(rc,0,(s,self.last_output));self.assertEqual(s['CAS_RECOVERY_ATTEMPTS'],'1');self.assertEqual(s['BUILD_TIME_SLICE_EXPIRED'],'true');self.assertTrue(saved)
 def test_supervisor_stale_marker_and_signal(self):
  with tempfile.TemporaryDirectory() as tmp:
   marker=pathlib.Path(tmp)/'result';marker.write_text('{"budget_expired":true,"exit_code":124}')
   command=['python3',str(ROOT/'.circleci/original-full/run_budget.py'),'--seconds','5','--marker',str(marker),'--','bash','-c','exit 124']
   p=subprocess.run(command);self.assertEqual(p.returncode,124);self.assertFalse(json.loads(marker.read_text())['budget_expired'])
   ready=pathlib.Path(tmp)/'ready';command[-1]='touch '+str(ready)+'; exec sleep 20'
   p=subprocess.Popen(command)
   deadline=time.monotonic()+5
   while not ready.exists() and time.monotonic()<deadline:time.sleep(.01)
   self.assertTrue(ready.exists());p.send_signal(signal.SIGTERM);self.assertEqual(p.wait(timeout=3),143);self.assertFalse(marker.exists())
 def test_timeout_kills_descendant_after_leader_exits(self):
  for cancellation in (False,True):
   with tempfile.TemporaryDirectory() as tmp:
    root=pathlib.Path(tmp); marker=root/'result';pidfile=root/'child'
    child=root/'child.py'
    child.write_text("import os,signal,time,pathlib\nsignal.signal(signal.SIGINT,signal.SIG_IGN)\nsignal.signal(signal.SIGTERM,signal.SIG_IGN)\npathlib.Path("+repr(str(pidfile))+").write_text(str(os.getpid()))\nwhile True: time.sleep(.05)\n")
    leader=root/'leader.sh';leader.write_text("trap 'exit 0' INT TERM\n"+shlex.quote(sys.executable)+' '+shlex.quote(str(child))+" &\nwait\n")
    command=[sys.executable,str(ROOT/'.circleci/original-full/run_budget.py'),'--seconds', '10' if cancellation else '1','--marker',str(marker),'--','bash',str(leader)]
    proc=subprocess.Popen(command)
    deadline=time.monotonic()+5
    while not pidfile.exists() and time.monotonic()<deadline:time.sleep(.01)
    self.assertTrue(pidfile.exists());pid=int(pidfile.read_text())
    if cancellation:proc.send_signal(signal.SIGTERM)
    self.assertEqual(proc.wait(timeout=5),143 if cancellation else 124)
    # A killed grandchild can briefly remain a zombie awaiting host reaping.
    deadline=time.monotonic()+2
    while time.monotonic()<deadline:
     stat=pathlib.Path('/proc')/str(pid)/'stat'
     if not stat.exists() or stat.read_text().split()[2]=='Z':break
     time.sleep(.01)
    else:self.fail('descendant still running after supervisor returned')
    self.assertEqual(marker.exists(),not cancellation)
 def test_serialized_circleci_expression_tokens(self):
  allowed={'parameters.stage_index','pipeline.git.branch','pipeline.parameters.run_build','pipeline.parameters.run_maintenance','pipeline.parameters.sandium_build_mode'}
  for name in ('config.yml','original-full/candidate.yml'):
   serialized=(ROOT/'.circleci'/name).read_text()
   matches=list(re.finditer(r'<<([\s\S]*?)>>',serialized))
   self.assertEqual(serialized.count('<<'),len(matches))
   for match in matches:
    self.assertLess(len(match.group(1)),2048)
    self.assertIn(re.sub(r'\\\n[ ]*\\?', '', match.group(1)).strip(),allowed)
   self.assertNotIn("<<'PYATTEST'",serialized)
   def scalars(value):
    if isinstance(value,str):yield value
    elif isinstance(value,dict):
     for k,v in value.items():yield from scalars(k);yield from scalars(v)
    elif isinstance(value,list):
     for item in value:yield from scalars(item)
   for scalar in scalars(yaml.safe_load(serialized)):
    tokens=list(re.finditer(r'<<([\s\S]*?)>>',scalar))
    self.assertEqual(scalar.count('<<'),len(tokens),scalar[:200])
    for token in tokens:
     self.assertLess(len(token.group(1)),2048)
     self.assertIn(token.group(1).strip(),allowed)

 def test_external_marker_check(self):
  with tempfile.TemporaryDirectory() as tmp:
   marker=pathlib.Path(tmp)/'marker'
   command=[sys.executable,str(ROOT/'.circleci/original-full/run_budget.py'),'--check-expired','--marker',str(marker)]
   self.assertNotEqual(subprocess.run(command).returncode,0)
   for text,expected in [('not json',1),('{}',1),('{"budget_expired":false,"exit_code":124}',1),('{"budget_expired":true,"exit_code":1}',1),('{"budget_expired":true,"exit_code":124}',0)]:
    marker.write_text(text);self.assertEqual(subprocess.run(command).returncode,expected)
 def test_post_build_no_always_save(self):
  cfg=yaml.safe_load((ROOT/'.circleci/config.yml').read_text())
  def walk(steps):
   for s in steps:
    if not isinstance(s,dict):continue
    for key,v in s.items():
     if key in ('run','save_cache'):self.assertNotEqual(v.get('when'),'always')
     elif key=='when':walk(v['steps'])
  walk(cfg['jobs']['brave-android-staged-build']['steps'])
  export=next(s['run'] for s in cfg['jobs']['brave-android-staged-build']['steps'] if isinstance(s,dict) and s.get('run',{}).get('name')=='Export APK status and artifacts')
  product=json.loads((ROOT/'.circleci/original-full/product-steps.json').read_text())
  self.assertEqual(export['command'],product['export']['run']['command'])
if __name__=='__main__':unittest.main()
