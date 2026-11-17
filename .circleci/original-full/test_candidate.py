import json,pathlib,unittest,yaml,hashlib
ROOT=pathlib.Path(__file__).resolve().parent
class OriginalFullCandidate(unittest.TestCase):
 def setUp(self):
  self.original=yaml.safe_load((ROOT/'fc220e7f.config.yml').read_text())
  self.candidate=yaml.safe_load((ROOT/'candidate.yml').read_text())
 def test_pinned_original_bytes(self):
  raw=(ROOT/'fc220e7f.config.yml').read_bytes()
  self.assertEqual('9512ffcdfc8ff52a534c9025cfee61abf1d39bc1',hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest())
 def test_unchanged_task_objects(self):
  old=self.original['jobs']['brave-android-staged-build']['steps']; new=self.candidate['jobs']['brave-android-staged-build']['steps']
  for m in json.loads((ROOT/'step-provenance.json').read_text()):
   if m.get('status')=='byte-identical task object':self.assertEqual(old[m['baseline_index']],new[m['candidate_index']])
 def test_five_original_stage_dependencies(self):
  jobs=self.candidate['workflows']['sandium-full-mode']['jobs'];self.assertEqual(5,len(jobs))
  for i,j in enumerate(jobs,1):
   args=j['brave-android-staged-build'];self.assertEqual(i,args['stage_index'])
   self.assertEqual([] if i==1 else [f'SANDIUM-FULL-MODE-stage-{i-1}'],args.get('requires',[]))
 def test_no_current_head_capture_or_reference_promotion(self):
  s=(ROOT/'candidate.yml').read_text();self.assertNotIn('full_driver.py capture',s);self.assertNotIn('promote-brave-reference',s);self.assertEqual(1,s.count('sandium-experimental-head-v1-'))
 def test_product_overlays_preserved(self):
  s=(ROOT/'candidate.yml').read_text()
  for i in range(24,31):self.assertEqual(1,s.count(f'product-overlay-{i}-0.sh'))
 def test_current_product_sequence_precedes_actual_build(self):
  steps=self.candidate['jobs']['brave-android-staged-build']['steps']
  runs=[s['run'] for s in steps if isinstance(s,dict) and isinstance(s.get('run'),dict)]
  commands=[r['command'].strip() for r in runs]
  indices=[commands.index(f'bash .circleci/experimental-steps/product-overlay-{i}-0.sh') for i in range(24,31)]
  self.assertEqual(indices,list(range(indices[0],indices[0]+7)))
  prep=next(i for i,r in enumerate(runs) if r['name']=='Prepare pinned Brave Android source')
  graph=next(i for i,r in enumerate(runs) if r['name']=='Validate build graph and remote-execution settings')
  compile=next(i for i,r in enumerate(runs) if r['name']=='Build bounded Brave Android APK slice')
  self.assertLess(prep,indices[0]);self.assertLess(indices[-1],graph);self.assertLess(graph,compile)
 def test_expiry_only_reference_copy_and_readback(self):
  jobs=self.candidate['jobs'];build=jobs['brave-android-staged-build'];maintenance=jobs['renew-fixed-reference']
  text=str(build);self.assertNotIn('renewal-prepare',text)
  copies=[s['save_cache'] for s in maintenance['steps'] if isinstance(s,dict) and 'save_cache' in s]
  self.assertEqual(2,len(copies));self.assertEqual(['brave-workspace-checkpoint.shards','brave-workspace-checkpoint.manifest.json'],copies[0]['paths'])
  names=[s.get('run',{}).get('name','') for s in maintenance['steps'] if isinstance(s,dict)]
  self.assertLess(names.index('Stop before large download unless saved reference is within expiry margin'),names.index('Verify all fixed-reference archive identities before copying'))
  seq=str(maintenance);self.assertLess(seq.index('renewal-clear'),seq.index('Read back exact newly saved immutable reference'));self.assertLess(seq.index('renewal-accept'),seq.index('Publish renewed fixed identity'))
  self.assertNotIn('archive-brave-workspace.sh archive',seq)
 def test_handoff_has_exact_workflow_keys(self):
  old=self.original['jobs']['brave-android-staged-build']['steps']
  candidate=self.candidate['jobs']['brave-android-staged-build']['steps']
  for index in range(10,14):
   actual=next(s for s in candidate if s==old[index])
   for key in actual['when']['steps'][0]['restore_cache']['keys']:
    self.assertIn('{{ .Environment.CIRCLE_WORKFLOW_ID }}',key)
 def test_cli_has_required_legacy_argument(self):
  def walk(obj):
   if isinstance(obj,dict):
    for key,value in obj.items():
     if key=='command' and isinstance(value,str):
      for line in value.splitlines():
       if 'fixed_reference.py ' in line:self.assertIn('--legacy-script .circleci/scripts/sandium-checkpoint-shards.py',line)
     else:walk(value)
   elif isinstance(obj,list):
    for value in obj:walk(value)
  walk(self.candidate)


class PhoneBranchGate(unittest.TestCase):
 def test_phone_full_only_and_existing_maintenance_gate(self):
  c=yaml.safe_load((ROOT/'candidate.yml').read_text())
  for job in c['workflows']['sandium-full-mode']['jobs']:
   self.assertEqual('release/phone-20261117',next(iter(job.values()))['filters']['branches']['only'])
  maintenance=c['workflows']['fixed-reference-maintenance']['jobs'][0]
  self.assertEqual('experiment/sandium-back-transition',next(iter(maintenance.values()))['filters']['branches']['only'])

if __name__=='__main__':unittest.main()
