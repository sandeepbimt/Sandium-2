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
    self.assertTrue(all((not p.exists()) if b is None else p.read_bytes()==b for p,b in on.items()))
    schema=(src/'extensions/common/api/schema.gni').read_text()
    self.assertEqual(schema.count('"scripts_internal.webidl"'),1)
    self.assertIn('"scripts_internal.webidl"',schema.split('if (enable_guest_view)')[0])
    chrome_schema=(src/'chrome/common/extensions/api/api_sources.gni').read_text()
    for name in ('browser_action.json','page_action.json'):
     self.assertEqual(chrome_schema.count('"'+name+'"'),1)
     self.assertIn('"'+name+'"',chrome_schema.split('if (enable_extensions)')[0])
    enum_build=(src/"extensions/browser/BUILD.gn").read_text()
    self.assertEqual(enum_build.count("if (is_android && enable_extensions_core) {"),2)
    self.assertIn('java_cpp_enum("extension_action_enums")',enum_build)
    self.assertNotIn("if (enable_desktop_android_extensions)",enum_build)
    import runpy
    gate=runpy.run_path(str(ROOT.parents[1]/'.circleci/scripts/verify-sandium-vanilla-brave.py'))['is_exact_ext0_dependency']
    wallet=core/'browser/brave_wallet/BUILD.gn'
    self.assertTrue(gate(core,'browser/brave_wallet/BUILD.gn','brave-core'))
    self.assertFalse(gate(core,'browser/brave_wallet/BUILD.gn','chromium'))
    self.assertFalse(gate(core,'browser/brave_wallet/other.cc','brave-core'))
    good=wallet.read_bytes();wallet.write_bytes(good+b'\n# unreviewed')
    self.assertFalse(gate(core,'browser/brave_wallet/BUILD.gn','brave-core'))
    wallet.write_bytes(good)

    m.execute(core,src,False);m.execute(core,src,False)
    self.assertTrue(all((not p.exists()) if b is None else p.read_bytes()==b for p,b in off.items()))
    new=next(p for p,b in off.items() if b is None);new.parent.mkdir(parents=True,exist_ok=True);new.write_text('user data')
    with self.assertRaisesRegex(ValueError,'collision'):m.plan(core,src,False)
    self.assertEqual(new.read_text(),'user data')
 def test_settings_rename_retired_and_restored(self):
  with tempfile.TemporaryDirectory() as td:
   core=Path(td);p=core/m.RENAMED_SETTINGS;p.parent.mkdir(parents=True)
   original=subprocess.check_output(['git','-C',str(CORE),'show',m.CORE_PIN+':'+m.RENAMED_SETTINGS])
   with patch.object(m,'blob',return_value=original):
    p.write_bytes(original);on={};m.retire_renamed_settings(core,True,on)
    self.assertIsNone(on[p]);p.unlink()
    off={};m.retire_renamed_settings(core,False,off);self.assertEqual(off[p],original)
    p.write_bytes(b'unowned')
    with self.assertRaisesRegex(ValueError,'Unowned'):m.retire_renamed_settings(core,True,{})
 def test_paths(self):
  for p in ('../other','/absolute','foo/../../bar'):
   with self.assertRaises(ValueError):m.safe(p)

if __name__=='__main__':unittest.main()
