import importlib.util,io,json,os,shutil,tarfile,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('full_u_bootstrap',ROOT/'.circleci/upgrades/bootstrap_host.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
class Bootstrap(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)/'runtime'
 def archive(self,name,destination):
  prefix='node-v24.16.0-linux-x64/bin/node' if name=='node' else 'pnpm'
  version=b.NODE_VERSION if name=='node' else b.PNPM_VERSION
  data=('#!/bin/sh\n'+('test -f "$(dirname "$0")/dist/pnpm.mjs" || exit 42\n' if name=='pnpm' else '')+'printf "'+version+'\\n"\n').encode()
  with tarfile.open(destination,'w:gz') as archive:
   entry=tarfile.TarInfo(prefix);entry.size=len(data);entry.mode=0o755;archive.addfile(entry,io.BytesIO(data))
   if name=='pnpm':
    companion=tarfile.TarInfo('dist/pnpm.mjs');companion.size=8;companion.mode=0o644;archive.addfile(companion,io.BytesIO(b'fixture\n'))
 def install_fixture(self):
  with patch.object(b,'download',side_effect=self.archive),patch.object(b.shutil,'disk_usage',return_value=shutil._ntuple_diskusage(10**12,0,10**12)):
   return b.install(self.root)
 def test_owned_install_capability_reuse_no_global_config(self):
  before=dict(os.environ);result=self.install_fixture();self.assertFalse(result['reused'])
  with patch.object(b,'download') as download:
   self.assertTrue(b.install(self.root)['reused']);download.assert_not_called()
  self.assertEqual(dict(os.environ),before)
  self.assertEqual(set(x.name for x in self.root.iterdir()),{'node','bin','pnpm','installed.json'})
 def test_corruption_and_unknown_existing_root_rejected(self):
  self.install_fixture();(self.root/'bin/pnpm').write_text('corrupt')
  with self.assertRaisesRegex(ValueError,'integrity'):b.install(self.root)
  other=self.root.parent/'unknown';other.mkdir();(other/'sentinel').write_text('keep')
  with self.assertRaisesRegex(ValueError,'ownership'):b.install(other)
  self.assertEqual((other/'sentinel').read_text(),'keep')
 def test_checksum_failure_does_not_install(self):
  with patch.object(b.urllib.request,'urlopen',return_value=io.BytesIO(b'not pinned bytes')):
   with self.assertRaisesRegex(ValueError,'checksum'):b.download('node',self.root.parent/'download')
  with patch.object(b,'download',side_effect=ValueError('checksum')),patch.object(b.shutil,'disk_usage',return_value=shutil._ntuple_diskusage(10**12,0,10**12)):
   with self.assertRaisesRegex(ValueError,'checksum'):b.install(self.root)
  self.assertFalse(self.root.exists())
 def test_escape_archive_rejected(self):
  archive=self.root.parent/'unsafe.tar'
  with tarfile.open(archive,'w') as tar:
   entry=tarfile.TarInfo('../escape');entry.size=1;tar.addfile(entry,io.BytesIO(b'x'))
  with self.assertRaises(tarfile.FilterError):b.extract(archive,self.root)
  self.assertFalse((self.root.parent/'escape').exists())
 def test_insufficient_disk_and_wrong_version_rejected(self):
  with patch.object(b.shutil,'disk_usage',return_value=shutil._ntuple_diskusage(1,0,1)):
   with self.assertRaisesRegex(ValueError,'disk'):b.install(self.root)
  self.install_fixture()
  with patch.object(b.subprocess,'check_output',return_value='wrong'):
   with self.assertRaisesRegex(ValueError,'capability'):b.verify(self.root)
if __name__=='__main__':unittest.main()
