import importlib.util,json,os,tempfile,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('upgrade_source',ROOT/'.circleci/upgrades/source.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class SourceTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name)/'brave-work';self.scope='full-u-v1-'+'a'*64
  self.env=patch.dict(os.environ,{'FULL_U_SCOPE':self.scope});self.env.start();self.addCleanup(self.env.stop)
 def own(self):
  p=self.root/'.sandium/full-u-owner.json';p.parent.mkdir(parents=True);p.write_text(json.dumps({'schema':1,'scope':self.scope}))
 def test_unowned_and_foreign_source_never_accepted(self):
  with self.assertRaises(ValueError):m.owned(self.root)
  self.own();self.assertEqual(m.owned(self.root),self.root)
  with patch.dict(os.environ,{'FULL_U_SCOPE':'full-u-v1-'+'b'*64}):
   with self.assertRaises(ValueError):m.owned(self.root)
 def test_interrupted_git_lock_preserved_and_explicit_repair_hold(self):
  self.own();lock=self.root/'src/brave/.git/index.lock';lock.parent.mkdir(parents=True);lock.write_text('unfinished index')
  with patch.object(m,'run') as run:
   with self.assertRaisesRegex(ValueError,'SOURCE_REPAIR_REQUIRED'):m.acquire(self.root)
   run.assert_not_called()
  self.assertEqual(lock.read_text(),'unfinished index')
 def test_existing_output_rejected_before_commands(self):
  self.own();(self.root/'src/out').mkdir(parents=True)
  with patch.object(m,'run') as run:
   with self.assertRaisesRegex(ValueError,'compiled output'):m.acquire(self.root)
   run.assert_not_called()
 def test_pin_verification_requires_both_heads_and_package(self):
  self.own();core=self.root/'src/brave';core.mkdir(parents=True)
  (core/'package.json').write_bytes((ROOT/'docs/upgrades/1.100.58/upstream-package.json').read_bytes())
  for rel in ('.gclient','src/DEPS','src/build/install-build-deps.sh'):
   p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('test fixture')
  with patch.object(m,'output',side_effect=[m.CORE,m.CHROMIUM]):
   self.assertEqual(m.verify(self.root,require_receipt=False)['phase'],'source-synced')
  with patch.object(m,'output',side_effect=[m.CORE,'0'*40]):
   with self.assertRaisesRegex(ValueError,'Chromium'):m.verify(self.root,require_receipt=False)
 def test_remote_configuration_preserves_only_existing_unrelated_lines(self):
  core=Path(self.tmp.name)/'core';core.mkdir()
  (core/'.env').write_text('other=value\nrbe_service=old:443\n')
  m.configure_remote(core,{})
  self.assertEqual((core/'.env').read_text(),'other=value\nrbe_service=remote.buildbuddy.io:443\nuse_remoteexec=true\nis_brave_release_build=0\n')
  with self.assertRaises(ValueError):m.configure_remote(core,{'SANDIUM_REAPI_ADDRESS':'host:443\nOTHER=x'})
 def test_success_receipt_required_and_package_cannot_drift(self):
  self.own();core=self.root/'src/brave';core.mkdir(parents=True)
  (core/'package.json').write_bytes((ROOT/'docs/upgrades/1.100.58/upstream-package.json').read_bytes())
  for rel in ('.gclient','src/DEPS','src/build/install-build-deps.sh'):
   p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture')
  with patch.object(m,'output',side_effect=[m.CORE,m.CHROMIUM]):
   with self.assertRaisesRegex(ValueError,'receipt required'):m.verify(self.root)
  with (core/'package.json').open('ab') as f:f.write(b'\n')
  with patch.object(m,'output',return_value=m.CORE):
   with self.assertRaisesRegex(ValueError,'reviewed bytes'):m.verify(self.root,require_receipt=False)
 def test_interrupted_git_init_recovers_only_empty_unborn_repository(self):
  core=Path(self.tmp.name)/'core';core.mkdir()
  subprocess.run(['git','init',str(core)],check=True,capture_output=True)
  m.ensure_origin(core)
  self.assertEqual(m.output(['git','-C',str(core),'remote','get-url','origin']),m.URL)
  m.ensure_origin(core)
  subprocess.run(['git','-C',str(core),'remote','set-url','origin','https://example.invalid/wrong.git'],check=True)
  with self.assertRaisesRegex(ValueError,'Unexpected source origin'):m.ensure_origin(core)
 def test_missing_origin_with_index_content_rejected(self):
  core=Path(self.tmp.name)/'core';core.mkdir()
  subprocess.run(['git','init',str(core)],check=True,capture_output=True)
  (core/'tracked').write_text('not an empty interrupted initialization')
  subprocess.run(['git','-C',str(core),'add','tracked'],check=True)
  with self.assertRaisesRegex(ValueError,'nonempty source'):m.ensure_origin(core)
 def test_symlink_root_rejected(self):
  self.own();link=Path(self.tmp.name)/'link';link.symlink_to(self.root,target_is_directory=True)
  with self.assertRaisesRegex(ValueError,'Symlink'):m.owned(link)
if __name__=='__main__':unittest.main()
