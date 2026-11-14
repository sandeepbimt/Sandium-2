import unittest
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
class FullWiring(unittest.TestCase):
 def test_full_only_and_preserved_product(self):
  cfg=yaml.safe_load((ROOT/'.circleci/config.yml').read_text())
  self.assertNotIn('sandium_build_mode',cfg['parameters'])
  self.assertNotIn('run_graph_precheck',cfg['parameters'])
  for n in range(1,6):
   steps=cfg['jobs'][f'full-stage-{n}']['steps']
   commands=[s['run']['command'] for s in steps if isinstance(s,dict) and isinstance(s.get('run'),dict)]
   joined='\n'.join(commands)
   self.assertLess(joined.index('full_driver.py restore'),joined.index('full_driver.py begin'))
   self.assertLess(joined.index('full_driver.py begin'),joined.index('prepare-brave-source.sh'))
   for x in range(24,31):self.assertIn(f'product-overlay-{x}-0.sh',joined)
   self.assertIn('export-apk.sh',joined)
   self.assertIn('full-bounded-build.sh',joined)
   self.assertNotIn('archive-brave-workspace.sh archive',joined)
 def test_shell_state_gate_uses_full_capacity_driver(self):
  script=(ROOT/'.circleci/scripts/verify-flow-state.sh').read_text()
  self.assertIn('"$ROOT/.circleci/bridge/full_driver.py" verify-restored',script)
  self.assertNotIn('"$ROOT/.circleci/bridge/driver.py"',script)
  # Each build stage reaches the same gate, not an obsolete seven-layer verifier.
  cfg=yaml.safe_load((ROOT/'.circleci/config.yml').read_text())
  for n in range(1,6):
   commands='\n'.join(s['run']['command'] for s in cfg['jobs'][f'full-stage-{n}']['steps'] if isinstance(s,dict) and isinstance(s.get('run'),dict))
   self.assertIn('verify-flow-state.sh',commands)
 def test_maintenance_separate_and_capacity(self):
  cfg=yaml.safe_load((ROOT/'.circleci/config.yml').read_text())
  for n in range(1,6):
   j=cfg['jobs'][f'full-stage-{n}']
   saves=[s['save_cache']['key'] for s in j['steps'] if isinstance(s,dict) and 'save_cache' in s]
   self.assertFalse(any(k.startswith('sandium-bridge-base-v1-') for k in saves))
   commands='\n'.join(s['run']['command'] for s in j['steps'] if isinstance(s,dict) and isinstance(s.get('run'),dict))
   for slot in range(16):self.assertIn(f'ingest --slot {slot}',commands)
  m=cfg['jobs']['maintain-full-checkpoint']
  self.assertEqual(m['environment']['SANDIUM_STAGE'],'0')
  cmds='\n'.join(s['run']['command'] for s in m['steps'] if isinstance(s,dict) and isinstance(s.get('run'),dict))
  self.assertIn('maintenance-check',cmds);self.assertIn('maintenance-capture',cmds)
  self.assertNotIn('full-bounded-build.sh',cmds)
  locks=[list(w['jobs'][0].values())[0]['serial-group'] for w in cfg['workflows'].values()]
  self.assertEqual(len(set(locks)),1)
 def test_apk_uploaded_before_validation_and_eligibility_after_publication(self):
  cfg=yaml.safe_load((ROOT/'.circleci/config.yml').read_text())
  for n in range(1,6):
   steps=cfg['jobs'][f'full-stage-{n}']['steps']
   cmds=[s.get('run',{}).get('command','') if isinstance(s,dict) else '' for s in steps]
   find=lambda word:next(i for i,c in enumerate(cmds) if word in c)
   raw=next(i for i,s in enumerate(steps) if isinstance(s,dict) and s.get('store_artifacts',{}).get('path')=='brave-apk-raw')
   self.assertLess(find('export-raw-apk.sh'),raw)
   self.assertLess(raw,find('export-apk.sh'))
   headsave=next(i for i,s in enumerate(steps) if isinstance(s,dict) and s.get('save_cache',{}).get('key','').startswith('sandium-experimental-head-v1-'))
   self.assertLess(headsave,find('post-publish-eligibility'))
   self.assertLess(find('full_driver.py final'),find('post-publish-eligibility'))
  self.assertEqual(cfg['jobs']['optional-post-apk-refresh']['environment']['SANDIUM_STAGE'],'6')
 def test_build_strict_remote_and_budget(self):
  s=(ROOT/'.circleci/experimental-steps/full-bounded-build.sh').read_text()
  self.assertIn('autoninja -strict_remote',s)
  self.assertIn('-j80 brave',s)
  self.assertIn('local=8,remote=80',s)
  self.assertIn('full_job_budget.py',s)
  self.assertNotIn('SANDIUM-FAST-MODE',s)
 def test_full_budget(self):
  import importlib.util
  spec=importlib.util.spec_from_file_location('full_budget',ROOT/'.circleci/checkpoint/full_job_budget.py')
  m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  self.assertLessEqual(m.build_seconds(1000,1000),2100)
  with self.assertRaises(ValueError):m.build_seconds(1000,5000)
if __name__=='__main__':unittest.main()
