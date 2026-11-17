import pathlib
import unittest
import yaml
ROOT=pathlib.Path(__file__).resolve().parents[2]
class Tests(unittest.TestCase):
 def setUp(self):self.c=yaml.safe_load((ROOT/'.circleci/config.yml').read_text())
 def visit(self,x):
  if isinstance(x,dict):
   yield x
   for v in x.values():yield from self.visit(v)
  elif isinstance(x,list):
   for v in x:yield from self.visit(v)
 def test_no_reference_write_or_maintenance(self):
  self.assertFalse(self.c['parameters']['run_build']['default'])
  self.assertNotIn('fixed-reference-maintenance',self.c['workflows'])
  self.assertNotIn('renew-fixed-reference',self.c['jobs'])
  for o in self.visit(self.c):
   if 'save_cache' in o:
    key=o['save_cache']['key'];self.assertFalse(key.startswith(('fixed-sandium','sandium-bridge-base','sandium-brave-handoff','sandium-brave-apk')))
 def test_preflight_dependency_bootstrapped(self):
  s=self.c["jobs"]["brave-android-staged-build"]["steps"][1]["run"]["command"]
  self.assertLess(s.index("pip install --disable-pip-version-check PyYAML==6.0.2"),s.index("/bin/python experiments/ubo-runtime/test_ci_isolation.py"))
 def test_only_experiment_branch(self):
  for wf in self.c['workflows'].values():
   for j in wf['jobs']:
    self.assertEqual(next(iter(j.values()))['filters']['branches']['only'],'experiment/ubo-runtime')
 def test_handoff_and_apk_reads_match_isolated_writes(self):
  text=(ROOT/'.circleci/config.yml').read_text()
  self.assertNotIn('sandium-brave-handoff-v2-',text)
  self.assertNotIn('sandium-brave-apk-complete-v2-',text)
  self.assertIn('sandium-ubo-ext0-handoff-v1-',text)
  self.assertIn('sandium-ubo-ext0-apk-v1-',text)
  self.assertIn('sandium-bridge-base-v1-',text) # immutable read retains useful baseline
 def test_reset_reapply_and_gn_opt_in(self):
  s=(ROOT/'.circleci/scripts/prepare-brave-source.sh').read_text()
  self.assertLess(s.index('ubo-runtime/source.py'),s.index('--phase reset-core'))
  lines=s.splitlines()
  resets=[i for i,l in enumerate(lines) if '--phase reset' in l and '--phase reset-core' not in l]
  self.assertEqual(len(resets),2)
  for i in resets:self.assertIn('ubo-runtime/source.py',lines[i+1])
  self.assertIn('--gn sandium_ubo_runtime_experiment:true --gn enable_extensions_core:true',s)
  self.assertIn('ubo-runtime/verify_gn.py',s)
  self.assertNotIn('--enable-features=BraveAndroidExtensions',s)

if __name__=='__main__':unittest.main()
