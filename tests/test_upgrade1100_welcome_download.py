import gzip,hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def module(name):
 s=importlib.util.spec_from_file_location(name,ROOT/'.circleci/scripts'/('apply-sandium-'+name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
class Replay(unittest.TestCase):
 def fixtures(self,root):
  data=json.loads(gzip.decompress((ROOT/'tests/fixtures/upgrades158/welcome-download.json.gz').read_bytes()))
  for rel,row in data.items():
   b=row['text'].encode();self.assertEqual(hashlib.sha256(b).hexdigest(),row['sha256']);self.assertEqual(hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest(),row['git_blob'])
   p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
  return data
 def test_complete_welcome_actual_target_apply_and_replay(self):
  m=module('welcome-setup')
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.fixtures(r)
   with patch.object(m,'verify_pins'):
    m.apply(r/'core',r/'chromium',ROOT)
    first={str(p.relative_to(r)):p.read_bytes() for p in r.rglob('*') if p.is_file()}
    m.apply(r/'core',r/'chromium',ROOT)
    self.assertEqual(first,{str(p.relative_to(r)):p.read_bytes() for p in r.rglob('*') if p.is_file()})
 def test_download_exact_upstream_and_replay(self):
  m=module('download-concurrency')
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);data=self.fixtures(r);before=data['chromium/'+str(m.CONFIG)]['text'];after=m.patch_config(before)
   self.assertEqual(m.patch_config(after),after)
   for k,v in m.LIMITS.items():self.assertIn(f'const uint32_t {k} = {v};',after)
 def test_welcome_wrong_pin_rejected(self):
  m=module('welcome-setup')
  with patch.object(m.subprocess,'check_output',side_effect=['v1.100.58\n',m.EXPECTED_CORE_SHA+'\n','0'*40+'\n']):
   with self.assertRaisesRegex(RuntimeError,'PIN_GATE'):m.verify_pins(Path('/core'),Path('/src'))
if __name__=='__main__':unittest.main()
