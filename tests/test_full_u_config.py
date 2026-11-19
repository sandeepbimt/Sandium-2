import importlib.util,sys,unittest
from pathlib import Path
import yaml,subprocess
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'.circleci/full-u'));import generate
class Config(unittest.TestCase):
 def test_held_dedicated_workflow_and_exact_readback(self):
  normal=(R/'.circleci/config.yml').read_bytes();c=generate.generate(yaml.safe_load(normal))
  self.assertFalse(c['parameters']['run_full_u']['default']);self.assertEqual(len(c['workflows']['Full-Mode-U']['jobs']),10)
  self.assertEqual((R/'.circleci/config.yml').read_bytes(),normal)
  text=str(c)
  self.assertNotIn('fixed-sandium-reference',text);self.assertIn('check-published',text);self.assertIn('check-pending',text)
  self.assertIn('Full-Mode-U-Recovery',c['workflows'])
  for job in c['jobs'].values():
   self.assertIn('Stop explicit completed resume',str(job['steps'][:4]))
  self.assertEqual(c,yaml.safe_load((R/'.circleci/full-u.yml').read_text()))
 def test_main_merge_preserves_every_ordinary_job_and_workflow(self):
  base=yaml.safe_load(subprocess.check_output(['git','show','a672821:.circleci/config.yml'],cwd=R,text=True))
  current=yaml.safe_load((R/'.circleci/config.yml').read_text())
  for section in ('jobs','workflows','parameters'):
   for name,value in base[section].items():self.assertEqual(current[section][name],value,name)
  self.assertEqual(generate.merge(current),current)
  for name in ('Full-Mode-U','Full-Mode-U-Recovery'):
   self.assertIn({'not':'<< pipeline.parameters.run_build >>'},current['workflows'][name]['when']['and'])
if __name__=='__main__':unittest.main()
