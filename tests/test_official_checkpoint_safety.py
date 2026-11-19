import importlib.util,json,hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import yaml
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('safety',ROOT/'.circleci/scripts/official-checkpoint-safety.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Safety(unittest.TestCase):
 def fixture(self,r):
  w=r/'brave-work'
  for n in ['.sandium/workspace-checkpoint-restored','.gclient','src/out/android_Release_arm64/build.ninja']:
   p=w/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('keep')
  d=r/'brave-workspace-checkpoint.shards';d.mkdir();items=[]
  for i in range(1,9):
   name=f'shard-{i:02d}-of-08.tar.zst';(d/name).write_bytes(b'abc');items.append(dict(name=name,size_bytes=3,sha256=hashlib.sha256(b'abc').hexdigest(),root_paths=[f'brave-work/item{i}']))
  (r/'brave-workspace-checkpoint.manifest.json').write_text(json.dumps(dict(schema_version=2,format='independent-tar+zstd-shards',shards=items)))
  return d
 def test_reclaim_only_transport(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);d=self.fixture(r)
   with patch.object(m.shutil,'disk_usage',return_value=type('Disk',(),{'free':60*1024**3})()):m.reclaim(r)
   self.assertFalse(d.exists());self.assertEqual((r/'brave-work/src/out/android_Release_arm64/build.ninja').read_text(),'keep');self.assertTrue((r/'brave-work/.sandium/reclaimed-transport.json').exists())
 def test_symlink_unknown_corruption_fail_before_delete(self):
  for case in ['extra','symlink','corrupt']:
   with self.subTest(case=case),tempfile.TemporaryDirectory() as t:
    r=Path(t);d=self.fixture(r);p=d/'shard-01-of-08.tar.zst'
    if case=='extra':(d/'unexpected').write_text('x')
    elif case=='corrupt':p.write_bytes(b'bad')
    else:p.unlink();p.symlink_to(r/'brave-work/.gclient')
    with self.assertRaises((ValueError,SystemExit)):m.reclaim(r)
    self.assertTrue((d/'shard-02-of-08.tar.zst').exists())
 def test_stage_one_full_budget_and_handoff_reserve(self):
  self.assertEqual(m.budget(100,100+13*60+23,1),1500)
  self.assertEqual(m.budget(100,100+17*60,1),1500)
  # Measured #1416 setup: 18m17s before the compile began.
  self.assertEqual(m.budget(100,100+18*60+17,1),23*60+43)
  self.assertEqual(m.budget(100,100+41*60,1),60)
  with self.assertRaises(ValueError):m.budget(100,100+41*60+1,1)
 def test_later_stage_budgets_unchanged(self):
  self.assertEqual(m.budget(100,100+600,2),1320)
  self.assertEqual(m.budget(100,100,2),1500)
  for stage in range(2,6):
   self.assertEqual(m.budget(100,100+1136,stage),784)
   with self.assertRaises(ValueError):m.budget(100,100+1900,stage)
 def test_space_floor(self):
  with patch.object(m.subprocess,'check_output',return_value=str(70*1024**3)+' workspace'),patch.object(m.shutil,'disk_usage',return_value=type('Disk',(),{'free':30*1024**3})()):
   with self.assertRaises(ValueError):m.space(Path('/tmp'))
  with patch.object(m.subprocess,'check_output',return_value=str(70*1024**3)+' workspace'),patch.object(m.shutil,'disk_usage',return_value=type('Disk',(),{'free':60*1024**3})()):m.space(Path('/tmp'))
 def test_config(self):
  raw=(ROOT/'.circleci/config.yml').read_text();d=yaml.safe_load(raw);steps=d['jobs']['brave-android-staged-build']['steps'];runs={x['run']['name']:x['run'] for x in steps if isinstance(x,dict) and 'run' in x}
  self.assertIn('circleci-agent step halt',runs['Skip large handoff after verified APK publication']['command'])
  self.assertIn('official-checkpoint-safety.py" budget',runs['Build bounded Brave Android APK slice']['command'])
  self.assertEqual((ROOT/'.circleci/original-full/candidate.yml').read_text(),raw)
  self.assertEqual((ROOT/'.circleci/original-full/config.sha256').read_text().strip(),hashlib.sha256(raw.encode()).hexdigest())
  names=[x.get('run',{}).get('name') for x in steps if isinstance(x,dict)]
  self.assertLess(names.index('Select Sandium build mode and validate reference'),names.index('Reclaim verified restored transport before official build'))
if __name__=='__main__':unittest.main()
