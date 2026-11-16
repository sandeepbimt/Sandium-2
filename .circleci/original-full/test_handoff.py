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
if __name__=='__main__':unittest.main()
