import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess

ROOT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('source',ROOT/'source.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
# Full exact inputs are supplied by a preparatory fetch, not invented stubs.
CORE=Path('/workspace/scratch/40acbbeff193/brave-core-audit')
RAW=Path('/tmp/ubo-patchcheck')
class Tests(unittest.TestCase):
 def test_full_pinned_apply_repeat_reset_and_collision(self):
  if not CORE.is_dir() or not RAW.is_dir(): self.skipTest('Exact pinned source inputs unavailable')
  with tempfile.TemporaryDirectory() as td:
   src=Path(td)/'src';core=src/'brave';core.mkdir(parents=True)
   def git(repo,*args,optional=False):
    if args==('rev-parse','HEAD'): return (m.CORE_PIN if repo==core else m.CHROMIUM_PIN).encode()
    pin,name=args[1].split(':',1)
    if repo==core:
     return m.git_original(CORE,*args,optional=optional)
    f=RAW/name
    return f.read_bytes() if f.exists() else None
   with patch.object(m,'git_original',m.git,create=True),patch.object(m,'git',git):
    on=m.plan(core,src,True);off=m.plan(core,src,False)
    m.execute(core,src,True);m.execute(core,src,True)
    self.assertTrue(all(p.read_bytes()==b for p,b in on.items()))
    m.execute(core,src,False);m.execute(core,src,False)
    self.assertTrue(all((not p.exists()) if b is None else p.read_bytes()==b for p,b in off.items()))
    new=next(p for p,b in off.items() if b is None);new.parent.mkdir(parents=True,exist_ok=True);new.write_text('user data')
    with self.assertRaisesRegex(ValueError,'collision'):m.plan(core,src,False)
    self.assertEqual(new.read_text(),'user data')
 def test_paths(self):
  for p in ('../other','/absolute','foo/../../bar'):
   with self.assertRaises(ValueError):m.safe(p)

if __name__=='__main__':unittest.main()
