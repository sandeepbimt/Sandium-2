"""Actual upstream158+Brave patch source replay, not Android runtime proof."""
import gzip,hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name):
 sp=importlib.util.spec_from_file_location(name,ROOT/'experiments/single-handoff'/f'{name}.py')
 m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
class Bridge158(unittest.TestCase):
 def test_complete_home_then_bridge(self):
  data=(ROOT/'tests/fixtures/upgrades158/handoff-bridge.json.gz').read_bytes()
  self.assertEqual(hashlib.sha256(data).hexdigest(),'05a8d43a7bfc69d40fed18abafbb2145a8169f1f7f0dbbffdd1a9feb150e0133')
  fixture=json.loads(gzip.decompress(data));self.assertEqual(fixture['chromium_pin'],'52bdd21723d5db0c9ab11716d38feac74828cf84')
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   def write(out):
    for p,t in out.items():p.parent.mkdir(parents=True,exist_ok=True);p.write_text(t)
   write({root/p:t for p,t in fixture['files'].items()})
   write(load('home').plan(root))
   module=load('bridge');planned=module.plan(root);write(planned)
   self.assertEqual(module.plan(root),planned)
   holder=(root/'chrome/android/java/src/org/chromium/chrome/browser/compositor/CompositorViewHolder.java').read_text()
   self.assertEqual(holder.count('        startSandiumNativeHome();\n    }\n\n    private void updateViewStateListener'),1)
   self.assertIn('private final List<DragAndDropPermissions>',holder)
if __name__=='__main__':unittest.main()
