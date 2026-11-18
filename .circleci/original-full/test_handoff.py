import json,pathlib,subprocess,tempfile,unittest,yaml,os
ROOT=pathlib.Path(__file__).resolve().parents[2]
CODE=(ROOT/'.circleci/scripts/verify-brave-reference.sh').read_text().split("<<'PY'\n",1)[1].split('\nPY',1)[0]
class Handoff(unittest.TestCase):
 def run_gate(self,stage=2,ready='false',changes=None,mode=True):
  cp={'CHECKPOINT_VALID':'true','REFERENCE_MODE':'reference','APK_VALIDATED':ready,'REFERENCE_READY':ready,'CHROMIUM_SHA':'d331de35ca8ab1358c7a17e4bd41627d55eaef51','BRAVE_CORE_TAG':'v1.98.62','TARGET':'android-arm64','BUILD_TYPE':'Release','STAGE':'1','WORKFLOW_ID':'workflow','REFERENCE_SOURCE_REVISION':'revision'}
  cp.update(changes or {})
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td)/'manifest.json';p.write_text(json.dumps(dict(schema_version=2,format='independent-tar+zstd-shards',checkpoint_manifest=cp,workers=8,shards=[{}]*8)))
   return subprocess.run(['python','-c',CODE,str(p)]+(['--handoff',str(stage),'workflow','revision'] if mode else []),capture_output=True).returncode
 def test_generated_writer_identity_reaches_consumer(self):
  config=yaml.safe_load((ROOT/'.circleci/original-full/candidate.yml').read_text())
  steps=config['jobs']['brave-android-staged-build']['steps']
  writer=next(n['run']['command'] for s in steps if 'when' in s for n in s['when'].get('steps',[]) if isinstance(n,dict) and isinstance(n.get('run'),dict) and n['run']['name']=='Validate Brave checkpoint before saving')
  lines=[line for line in writer.splitlines() if any(('echo "'+key+'=') in line for key in ('STAGE','WORKFLOW_ID','REFERENCE_SOURCE_REVISION'))]
  self.assertEqual(3,len(lines))
  command='set -eu\n'+'\n'.join(lines).replace('<< parameters.stage_index >>','1')
  env=dict(os.environ,CIRCLE_WORKFLOW_ID='workflow',CIRCLE_SHA1='revision')
  result=subprocess.run(['bash','-c',command],env=env,text=True,capture_output=True,check=True)
  identity=dict(line.split('=',1) for line in result.stdout.splitlines())
  self.assertEqual({'STAGE':'1','WORKFLOW_ID':'workflow','REFERENCE_SOURCE_REVISION':'revision'},identity)
  self.assertEqual(0,self.run_gate(changes=identity))
  identity['REFERENCE_SOURCE_REVISION']='{{ .Revision }}'
  self.assertNotEqual(0,self.run_gate(changes=identity))
 def test_incomplete_and_complete_handoff(self):
  self.assertEqual(0,self.run_gate());self.assertEqual(0,self.run_gate(ready='true'))
 def test_stage_one_strict(self):
  self.assertNotEqual(0,self.run_gate(mode=False));self.assertEqual(0,self.run_gate(mode=False,ready='true'));self.assertNotEqual(0,self.run_gate(stage=1))
 def test_provenance(self):
  for key in ['STAGE','WORKFLOW_ID','REFERENCE_SOURCE_REVISION']:
   for value in [None,'wrong']:
    with self.subTest(key=key,value=value):self.assertNotEqual(0,self.run_gate(changes={key:value}))
 def test_readiness(self):
  for value in [None,'maybe','true']:
   self.assertNotEqual(0,self.run_gate(changes={'REFERENCE_READY':value}))
 def test_pins_and_integrity_fields(self):
  for key in ['CHECKPOINT_VALID','REFERENCE_MODE','CHROMIUM_SHA','BRAVE_CORE_TAG','TARGET','BUILD_TYPE']:
   self.assertNotEqual(0,self.run_gate(changes={key:'wrong'}))

class SnapshotOrdering(unittest.TestCase):
 def test_raw_restore_verified_before_all_mutators(self):
  for rel in ['.circleci/config.yml','.circleci/original-full/candidate.yml']:
   steps=yaml.safe_load((ROOT/rel).read_text())['jobs']['brave-android-staged-build']['steps']
   names=[s.get('run',{}).get('name','') for s in steps if isinstance(s,dict)]
   restore=names.index('SANDIUM FULL/FAST MODE - Restore checkpoint with up to 8 parallel workers')
   compare=names.index('Diagnose restored Siso checkpoint and compare prior stage')
   self.assertEqual(restore+1,compare)
   self.assertLess(compare,names.index('Prepare pinned Brave Android source'))
   for i,s in enumerate(steps):
    command=s.get('run',{}).get('command','') if isinstance(s,dict) else ''
    if 'product-overlay-' in command:self.assertGreater(i,compare)
 def test_actual_snapshot_gate_keeps_corruption_checks(self):
  script=ROOT/'.circleci/scripts/capture-brave-siso-checkpoint.sh'
  with tempfile.TemporaryDirectory() as td:
   root=pathlib.Path(td);out=root/'brave-work/src/out/android_Release_arm64';out.mkdir(parents=True)
   files={'build.ninja':'build example: rule\n','args.gn':'x=true\n','args_generated.gni':'x=1\n','.siso_fs_state':'state','.ninja_log':'log','obj/a.o':'object','gen/a.h':'generated'}
   for name,data in files.items():
    p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data)
   env=dict(os.environ,CIRCLE_WORKING_DIRECTORY=td,CIRCLE_WORKFLOW_ID='same-workflow',CIRCLE_BUILD_NUM='1',BRAVE_STAGE_INDEX='1')
   subprocess.run(['bash',str(script),'checkpoint-ready'],env=env,check=True,capture_output=True)
   env.update(BRAVE_STAGE_INDEX='2',CIRCLE_BUILD_NUM='2')
   passed=subprocess.run(['bash',str(script),'restore'],env=env,capture_output=True,text=True)
   self.assertEqual(0,passed.returncode,passed.stdout+passed.stderr)
   self.assertIn('HANDOFF_COMPARISON=PASS',passed.stdout)
   # These are precisely the graph/generated/output changes seen in stage 2.
   # They remain errors at the raw-restore boundary, not ignored differences.
   for name in ['build.ninja','args_generated.gni','obj/a.o','gen/a.h','.siso_fs_state','.ninja_log']:
    p=out/name;before=p.read_text();p.write_text(before+'changed')
    failed=subprocess.run(['bash',str(script),'restore'],env=env,capture_output=True,text=True)
    self.assertNotEqual(0,failed.returncode,name)
    self.assertIn('HANDOFF_COMPARISON=FAIL',failed.stdout)
    p.write_text(before)

if __name__=='__main__':unittest.main()
