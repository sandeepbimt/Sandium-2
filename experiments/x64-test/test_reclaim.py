import tempfile,unittest
from pathlib import Path
from reclaim_bootstrap import reclaim,require_archive_space,BRANCH,DISPOSABLE
class Reclaim(unittest.TestCase):
 def fixture(self,root):
  out=root/'brave-work/src/out/android_Release';out.mkdir(parents=True)
  (out/'args.gn').write_text('target_os = "android"\ntarget_cpu = "x64"\nenable_android_secondary_abi = false\n')
  (out/'build.ninja').write_text('preserve')
  for rel in DISPOSABLE:
   p=root/rel;p.parent.mkdir(parents=True,exist_ok=True)
   if rel.endswith(('arm64','shards')):p.mkdir();(p/'data').write_text('disposable')
   else:p.write_text('disposable')
  (root/'brave-work/src/source.cc').write_text('preserve')
 def test_reclaim_preserves_source_and_native_graph(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.fixture(r);reclaim(r,BRANCH)
   self.assertTrue((r/'brave-work/src/source.cc').exists())
   self.assertTrue((r/'brave-work/src/out/android_Release/build.ninja').exists())
   for rel in DISPOSABLE:self.assertFalse((r/rel).exists())
 def test_rejects_wrong_branch_before_deleting(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.fixture(r)
   with self.assertRaises(ValueError):reclaim(r,'main')
   self.assertTrue((r/DISPOSABLE[0]).exists())
 def test_rejects_symlink_before_any_deletion(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.fixture(r)
   p=r/DISPOSABLE[-1];p.unlink();p.symlink_to(r/'brave-work/src/source.cc')
   with self.assertRaises(ValueError):reclaim(r,BRANCH)
   self.assertTrue((r/DISPOSABLE[0]).exists())
 def test_rejects_invalid_graph(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.fixture(r)
   (r/'brave-work/src/out/android_Release/args.gn').write_text('target_cpu = "arm64"')
   with self.assertRaises(ValueError):reclaim(r,BRANCH)
   self.assertTrue((r/DISPOSABLE[0]).exists())

 def test_archive_space_fails_before_pack(self):
  from unittest.mock import patch
  from collections import namedtuple
  usage=namedtuple('usage','total used free')
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.fixture(r)
   with patch('reclaim_bootstrap.shutil.disk_usage',return_value=usage(100,100,0)):
    with self.assertRaises(ValueError):require_archive_space(r)
   with patch('reclaim_bootstrap.shutil.disk_usage',return_value=usage(10**12,0,10**12)):
    require_archive_space(r)
