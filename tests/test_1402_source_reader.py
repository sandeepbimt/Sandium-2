import importlib.util
from pathlib import Path
import subprocess,tempfile,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('same_pin_reader',ROOT/'.circleci/scripts/replay-1402-source.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class SourceReader(unittest.TestCase):
 def repository(self,path):
  path.mkdir();subprocess.run(['git','init','-q',str(path)],check=True)
  (path/'actual.txt').write_bytes(b'exact upstream fixture\n')
  subprocess.run(['git','-C',str(path),'add','.'],check=True)
  subprocess.run(['git','-C',str(path),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','fixture'],check=True)
  return subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
 def test_real_git_identity_blob_and_cache(self):
  with tempfile.TemporaryDirectory() as d:
   repo=Path(d)/'repo';pin=self.repository(repo)
   with patch.object(m,'PINS',{'core':pin,'chromium':pin}):
    reader=m.PinnedBlobs({'core':repo,'chromium':repo})
    self.assertEqual(reader.read('core',pin,'actual.txt'),b'exact upstream fixture\n')
    self.assertEqual(reader.check_output(['git','-C','exact156-core','show',pin+':actual.txt']),b'exact upstream fixture\n')
    self.assertEqual(len(reader.cache),1);self.assertEqual(reader.environment['GIT_NO_LAZY_FETCH'],'1')
    with self.assertRaisesRegex(ValueError,'different source pin'):reader.read('core','wrong','actual.txt')
 def test_wrong_head_and_blob_corruption_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   repo=Path(d)/'repo';pin=self.repository(repo)
   with self.assertRaisesRegex(ValueError,'Wrong156'):m.PinnedBlobs({'core':repo})
   with patch.object(m,'PINS',{'core':pin}):
    reader=m.PinnedBlobs({'core':repo})
    with patch.object(reader,'original',return_value=b'tampered'):
     with self.assertRaisesRegex(ValueError,'Git blob differs'):reader.read('core',pin,'actual.txt')
if __name__=='__main__':unittest.main()
