import gzip,hashlib,importlib.util,json,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name):
 spec=importlib.util.spec_from_file_location(name,ROOT/'.circleci/scripts'/('apply-sandium-'+name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
DATA=json.loads(gzip.decompress((ROOT/'tests/fixtures/upgrades158/navigation.json.gz').read_bytes()))
class Navigation158(unittest.TestCase):
 def test_exact_upstream_patches_and_ordered_plans_replay(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   for rel,item in DATA['raw'].items():
    b=item['text'].encode();self.assertEqual(hashlib.sha256(b).hexdigest(),item['sha256'])
    p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
   for name,item in DATA['patches'].items():
    self.assertEqual(hashlib.sha256(item['text'].encode()).hexdigest(),item['sha256'])
    subprocess.run(['git','apply','-'],cwd=root,input=item['text'],text=True,check=True,capture_output=True)
   for name in ('back-controls','back-transition','capture-coherence'):
    m=load(name);values=m.plan(root)
    for p,v in values.items():p.write_text(v)
    self.assertEqual(m.plan(root),values)
   m=load('address-progress')
   for rel,fn in m.TRANSFORMS.items():
    p=root/rel;out=fn(p.read_text());p.write_text(out);self.assertEqual(fn(out),out)
 def test_native158_capture_policy_preserved(self):
  m=load('capture-coherence');rel=m.BASE+'ToolbarControlContainer.java';text=DATA['raw'][rel]['text']
  self.assertEqual(m.container(text),text)
  self.assertNotIn('shouldCaptureWhileHidden()',text)
  with self.assertRaises(RuntimeError):m.container(text.replace('if (mControlContainerIsVisibleSupplier.getAsBoolean()) {','if (true) {'))
 def test_target_pair_identity_in_fixture(self):
  self.assertEqual(DATA['chromium'],'52bdd21723d5db0c9ab11716d38feac74828cf84')
  self.assertEqual(DATA['brave'],'bd6d26d1bced03c17a98baa86d2cd3425d543d1b')
if __name__=='__main__':unittest.main()
