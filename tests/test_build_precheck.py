import importlib.util
import tempfile
import unittest
from pathlib import Path

P=Path(__file__).resolve().parents[1]/'.circleci/scripts/precheck-sandium-build.py'
spec=importlib.util.spec_from_file_location('build_precheck',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class BuildPrecheckTests(unittest.TestCase):
 def test_outputs_strict(self):
  self.assertEqual(m.target_outputs('obj/brave/a.stamp\nobj/brave/a.stamp\nobj/brave/x.a\n'),['obj/brave/a.stamp','obj/brave/x.a'])
  for value in ['../outside','/tmp/x','--flag','x:foo','out/test.apk','obj/libchrome.so','', 'No targets match.']:
   with self.assertRaises(ValueError):m.target_outputs(value)
 def test_sources_reject_missing_and_escape(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'brave').mkdir();(root/'brave/test.cc').write_text('')
   manifest={'core_restore':['test.cc','BUILD.gn'],'chromium_restore':[]}
   self.assertEqual(m.source_inputs(manifest,root),['//brave/test.cc'])
   for bad in ['../bad.cc','missing.cc']:
    with self.assertRaises(ValueError):m.source_inputs({'core_restore':[bad],'chromium_restore':[]},root)
 def test_timeout_is_not_pass(self):
  import os,sys
  with tempfile.TemporaryDirectory() as d:
   result=m.bounded_run([sys.executable,'-c','import time; time.sleep(60)'],d,dict(os.environ),0.05,Path(d)/'log')
   self.assertEqual(result['status'],'INCOMPLETE_TIMEOUT');self.assertEqual(result['exit_code'],124)
 def test_real_selected_command_result(self):
  import os,sys
  with tempfile.TemporaryDirectory() as d:
   for code,status in [(0,'PASS_SELECTED_TARGETS'),(3,'FAILED')]:
    result=m.bounded_run([sys.executable,'-c',f'raise SystemExit({code})'],d,dict(os.environ),5,Path(d)/'log')
    self.assertEqual(result['status'],status)
 def test_deadline_cap_and_no_time(self):
  self.assertEqual(m.compile_budget(2400,1000,1000),2400)
  self.assertEqual(m.compile_budget(2400,1000,3000),1090)
  self.assertEqual(m.compile_budget(2400,1000,4031),59)
  self.assertEqual(m.compile_budget(2400,1000,5000),0)
  self.assertEqual(m.compile_budget(60,1000,1000),60)
  for start in [float('nan'),float('inf'),True,0,-1,'1000',2001]:
   with self.assertRaises(ValueError):m.compile_budget(60,start,2000)
 def test_no_time_does_not_compile_or_claim_pass(self):
  import json,os
  from unittest.mock import patch,Mock
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);src=root/'src';out=src/'out';out.mkdir(parents=True)
   (out/'build.ninja').write_text('graph')
   gn=src/'buildtools/linux64/gn';gn.parent.mkdir(parents=True);gn.write_text('tool');gn.chmod(0o755)
   (src/'brave').mkdir();(src/'brave/test.cc').write_text('code')
   manifest=root/'manifest.json';manifest.write_text(json.dumps({'core_restore':['test.cc'],'chromium_restore':[]}))
   receipt=root/'start.json';receipt.write_text('{"epoch":1000}')
   report=root/'report'
   with patch.object(m,'package_readiness',return_value={}),patch.object(m.subprocess,'run',return_value=Mock(stdout='obj/test.stamp\n')),patch.object(m.time,'time',return_value=5000),patch.object(m,'bounded_run') as run:
    rc=m.main(['--src',str(src),'--out',str(out),'--manifest',str(manifest),'--report-dir',str(report),'--job-start',str(receipt),'--compile-seconds','1200'])
    self.assertEqual(rc,124);run.assert_not_called()
   result=json.loads((report/'build-precheck.json').read_text())
   self.assertEqual(result['status'],'INCOMPLETE_NO_TIME');self.assertFalse(result['full_build_verified']);self.assertFalse(result['apk_verified'])
 def test_actual_config_cli_matches_parser(self):
  import yaml,shlex
  root=P.parents[2]
  cfg=yaml.safe_load((root/'.circleci/config.yml').read_text())
  found=0
  for job in cfg['jobs'].values():
   for step in job['steps']:
    run=step.get('run',{}) if isinstance(step,dict) else {}
    command=run.get('command','') if isinstance(run,dict) else ''
    if 'python3 .circleci/scripts/precheck-sandium-build.py' not in command:continue
    command=command.replace('$CIRCLE_WORKING_DIRECTORY','/tmp/source').replace('$SANDIUM_PRECHECK_COMPILE_SECONDS','0')
    args=shlex.split(command)
    if args[:2]!=['python3','.circleci/scripts/precheck-sandium-build.py']:continue
    parsed=m.parse_args(args[2:]);found+=1
    self.assertEqual(parsed.job_start,Path('/tmp/source/.checkpoint-state/job-start.json'))
    self.assertEqual(parsed.compile_seconds,0)
  self.assertGreater(found,0)
 def test_packaging_readiness_missing_fails(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):m.package_readiness(Path(d))

if __name__=='__main__':unittest.main()
