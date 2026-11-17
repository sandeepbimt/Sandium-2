import hashlib,re,subprocess,tempfile,unittest
from pathlib import Path
import yaml
from build_config import ROOT,BRANCH,PATHS,arch,derive,scripts,walk
from verify_generated import verify
class Config(unittest.TestCase):
 def setUp(self):self.cfg=derive(yaml.safe_load((ROOT/'.circleci/native-status-test/config.yml').read_text()))
 def test_reproducible(self):verify()
 def test_ci_validator_without_site_packages(self):
  subprocess.run(['python3','-S',str(ROOT/'experiments/x64-test/verify_generated.py')],check=True)
 def test_ci_validator_rejects_drift(self):
  import shutil
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   manifest=__import__('json').loads((ROOT/'.circleci/x64-test/manifest.json').read_text())
   for p in set(manifest['inputs']) | set(manifest['outputs']) | {'.circleci/x64-test/manifest.json','.circleci/config.yml'}:
    (root/p).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/p,root/p)
   (root/'.circleci/x64-test/config.yml').write_text('tampered')
   with self.assertRaises(ValueError):verify(root,full=False)
 def test_no_normal_cache_writes(self):
  for s in walk(self.cfg['jobs']['brave-android-staged-build']['steps']):
   if isinstance(s,dict) and 'save_cache' in s:
    key=s['save_cache']['key'];self.assertTrue(key.startswith(('sandium-x64-handoff-v1-','sandium-x64-apk-complete-v1-')));self.assertIn('{{ .Branch }}',key);self.assertIn('{{ .Environment.CIRCLE_WORKFLOW_ID }}',key)
  self.assertEqual(list(self.cfg['workflows']),['sandium-full-mode'])
 def test_branch_and_no_translation_patch(self):
  for j in self.cfg['workflows']['sandium-full-mode']['jobs']:
   self.assertEqual(j['brave-android-staged-build']['filters']['branches']['only'],BRANCH)
  self.assertNotIn('Apply isolated ARM translation',yaml.safe_dump(self.cfg))
 def test_bootstrap_and_continuation_separate(self):
  runs={s['run']['name']:s['run']['command'] for s in walk(self.cfg['jobs']['brave-android-staged-build']['steps']) if isinstance(s,dict) and 'run' in s}
  restore=runs['SANDIUM FULL/FAST MODE - Restore checkpoint with up to 8 parallel workers']
  self.assertIn('if [ "<< parameters.stage_index >>" = "1" ]',restore)
  self.assertIn('.circleci/scripts/archive-brave-workspace.sh restore',restore)
  self.assertIn('.circleci/x64-test/archive-brave-workspace.sh restore',restore)
  mode=runs['Select Sandium build mode and validate reference']
  self.assertIn('.circleci/scripts/verify-brave-reference.sh"\n',mode)
  self.assertIn('.circleci/x64-test/verify-brave-reference.sh" --handoff',mode)
  self.assertIn('TARGET=android-x64',runs['Validate Brave checkpoint before saving'])
 def test_all_runtime_paths_use_x64(self):
  outputs=scripts(ROOT)
  for path,text in outputs.items():
   self.assertNotIn('BraveMonoarm64',text,path)
   self.assertNotIn('--target_arch=arm64',text,path)
   if not path.endswith('sandium-checkpoint-shards.py'):self.assertNotIn('android_Release_arm64',text,path)
  self.assertIn('if false &&',outputs[PATHS['.circleci/scripts/prepare-brave-source.sh']])
 def test_no_active_unconverted_output_consumer(self):
  allowed={'Run lightweight Brave continuation self-test','SANDIUM FULL/FAST MODE - Restore checkpoint with up to 8 parallel workers','Select Sandium build mode and validate reference','Diagnose restored Siso checkpoint and compare prior stage'}
  for item in walk(self.cfg['jobs']['brave-android-staged-build']['steps']):
   if not isinstance(item,dict) or 'run' not in item:continue
   run=item['run']
   if run['name'] in allowed or 'fixed-reference' in run['name'].lower():continue
   for path in re.findall(r'\.circleci/(?:scripts|experimental-steps)/[A-Za-z0-9_.-]+\.(?:sh|py)',run['command']):
    text=(ROOT/path).read_text()
    self.assertNotIn('android_Release_arm64',text,(run['name'],path))
 def test_shell_syntax(self):
  for path in scripts(ROOT):
   if path.endswith('.sh'):subprocess.run(['bash','-n',str(ROOT/path)],check=True)
 def test_embedded_commands_shell_syntax(self):
  for item in walk(self.cfg['jobs']['brave-android-staged-build']['steps']):
   if isinstance(item,dict) and 'run' in item:
    subprocess.run(['bash','-n'],input=item['run']['command'],text=True,check=True)
 def test_failfast_unchanged(self):
  text=yaml.safe_dump(self.cfg)
  self.assertIn('ACTION_FAILED',text);self.assertIn('BUILD_BUDGET_ATTESTED',text)
  self.assertIn('Skip large handoff after verified APK publication',text)
if __name__=='__main__':unittest.main()
