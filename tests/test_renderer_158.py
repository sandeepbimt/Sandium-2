"""Exact patched Chromium158 native dark/text composition, not compilation evidence."""
import gzip,hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(path):
 spec=importlib.util.spec_from_file_location('m'+str(abs(hash(path))),ROOT/path)
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class Renderer158(unittest.TestCase):
 def test_exact_ordered_replay(self):
  data=(ROOT/'tests/fixtures/upgrades158/renderer.json.gz').read_bytes()
  self.assertEqual(hashlib.sha256(data).hexdigest(),'b32beb483cf184c8bbd14717bc1f5eea6378a60ce6e5b734376ef4b2cc615b5b')
  fixture=json.loads(gzip.decompress(data))
  self.assertEqual(fixture['chromium_pin'],'52bdd21723d5db0c9ab11716d38feac74828cf84')
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   for p,t in fixture['files'].items():
    f=root/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(t)
   stages=[('.circleci/features/dark-pages/renderer/apply.py','apply')]
   stages += [('.circleci/features/element-corrector/apply-'+k+'-draft.py','compose') for k in ('native','browser','transport')]
   stages += [('.circleci/features/page-text/renderer/'+k+'.py','apply') for k in ('apply','oopif')]
   stages += [('experiments/single-handoff/dark_policy.py','plan')]
   for script,method in stages:
    module=load(script)
    def run():
     result=getattr(module,method)(root)
     if isinstance(result,dict):
      for p,t in result.items():p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t)
    run()
    before={str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}
    run()
    self.assertEqual(before,{str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()})
   text=(root/'third_party/blink/renderer/core/frame/local_frame_view.cc').read_text()
   self.assertIn('Style().ColorSchemeForced()',text)
   self.assertNotIn('StyleRef().ColorSchemeForced()',text)
if __name__=='__main__':unittest.main()
