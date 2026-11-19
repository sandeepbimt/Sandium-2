import gzip,hashlib,importlib.util,json,subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];FIX=ROOT/'tests/fixtures/upgrade1100'
spec=importlib.util.spec_from_file_location('target_reset',ROOT/'.circleci/scripts/sandium-removal-recipe.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
DATA=json.loads(gzip.decompress((FIX/'reset-patches.json.gz').read_bytes()))
PROOF=json.loads((FIX/'reset-provenance.json').read_text())
class ResetReplay(unittest.TestCase):
 def projection(self):return dict(core_restore=[],chromium_restore=list(DATA['patches']),chromium_restore_patches=DATA['patches'])
 def test_every_declared_input_has_exact_target_identity(self):
  recipe=m.load();self.assertEqual(recipe['brave_pin'],PROOF['brave_sha']);self.assertEqual(recipe['chromium_pin'],PROOF['chromium_sha'])
  required={'core/'+p for p in set(recipe['core_restore'])|set(recipe['chromium_restore_patches'].values())}|{'chromium/'+p for p in recipe['chromium_restore']}
  self.assertEqual(required,set(PROOF['files']))
  self.assertEqual(recipe['chromium_restore_patches'],DATA['patches'])
 def test_all_actual_target_patches_apply(self):
  for kind in ('core','chromium'):
   for path,text in DATA[kind].items():
    raw=text.encode();entry=PROOF['files'][kind+'/'+path]
    self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),entry['git_blob'])
    self.assertEqual(hashlib.sha256(raw).hexdigest(),entry['sha256'])
  payload=m.restore_payload(self.projection(),lambda p:DATA['core'][p].encode(),lambda p:DATA['chromium'][p].encode())
  self.assertEqual(len(payload['chromium']),len(DATA['patches']))
  for path,data in payload['chromium'].items():self.assertNotEqual(data,DATA['chromium'][path].encode(),path)
 def test_wrong_patch_target_rejected_without_source_mutation(self):
  before=json.dumps(DATA,sort_keys=True)
  def malicious(p):return DATA['core'][p].replace('+++ b/','+++ b/unowned/',1).encode()
  with self.assertRaisesRegex(ValueError,'patch target mismatch'):m.restore_payload(self.projection(),malicious,lambda p:DATA['chromium'][p].encode())
  self.assertEqual(before,json.dumps(DATA,sort_keys=True))
if __name__=='__main__':unittest.main()
