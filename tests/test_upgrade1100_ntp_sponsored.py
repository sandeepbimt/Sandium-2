import gzip,hashlib,importlib.util,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
DATA=json.loads(gzip.decompress((ROOT/'tests/fixtures/upgrade1100/ntp-sponsored.json.gz').read_bytes()))
PROOF=json.loads((ROOT/'tests/fixtures/upgrade1100/reset-provenance.json').read_text())
class Sponsored(unittest.TestCase):
 def test_exact_source_identity(self):
  for path,text in DATA.items():
   raw=text.encode();entry=PROOF['files']['core/'+path]
   self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),entry['git_blob'])
   self.assertEqual(hashlib.sha256(raw).hexdigest(),entry['sha256'])
 def test_existing_preservation_idempotence_and_atomicity_contracts(self):
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary)
   for path,text in DATA.items():
    target=root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text)
   with patch.dict(os.environ,{'SANDIUM_PINNED_CORE':str(root)}):
    spec=importlib.util.spec_from_file_location('ntp158_contract',ROOT/'.circleci/scripts/test-sandium-ntp-sponsored-removal.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    result=unittest.TestResult();unittest.defaultTestLoader.loadTestsFromModule(module).run(result)
    self.assertEqual(result.testsRun,2);self.assertEqual(result.failures,[]);self.assertEqual(result.errors,[])
if __name__=='__main__':unittest.main()
