"""Pinned full transition sources + compact UI anchors; no Android runtime claim."""
import gzip,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('native',ROOT/'experiments/native-navigation/apply.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
DATA=json.loads(gzip.decompress((ROOT/'tests/fixtures/native-navigation.json.gz').read_bytes()))
class Native(unittest.TestCase):
 def setUp(self):
  self.geometry=patch.object(m,"geometry_changes",return_value={});self.geometry.start();self.addCleanup(self.geometry.stop)
 def seed(self,root):
  for p,s in DATA['frozen'].items():
   f=root/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(s)
 def test_fixture_matches_production_transition_layers(self):
  def load(name):
   spec=importlib.util.spec_from_file_location(name,ROOT/'.circleci/scripts'/(name+'.py'))
   module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
  full=load('apply-sandium-page-transition-full');native=load('sandium-native-blur-source');back=load('apply-sandium-back-transition')
  for path,fn in [(str(full.TRANSITION_CC),lambda t:native.implementation(full.transform_transition_cc(t))),(str(full.TRANSITION_H),lambda t:native.header(full.transform_transition_h(t))),(str(full.FEATURES_CC),full.transform_features_cc),(str(full.FEATURES_H),full.transform_features_h)]:
   self.assertEqual(fn(DATA['native'][path]),DATA['frozen'][path],path)
  current={p:DATA['native'][p] for p,o,n in back.CHANGES}
  for p,o,n in back.CHANGES:current[p]=back.transform(current[p],o,n)
  for p,s in current.items():self.assertEqual(s,DATA['frozen'][p],p)
 def test_exact_pinned_native_transition_parity(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.seed(root)
   for p,s in m.transform(root).items():self.assertEqual(s,DATA['native'][str(p.relative_to(root))])
 def test_on_off_restores_frozen_and_unrelated_edits(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.seed(root)
   p=root/next(iter(DATA['frozen']));p.write_text(p.read_text()+'\n// unrelated frozen customization\n')
   untouched=root/'menu-fix.txt';untouched.write_text('five rows and swipe')
   before={root/p:(root/p).read_text() for p in DATA['frozen']}
   # Engine transaction only; geometry is tested independently before wiring.
   changes,state=m.plan(root,True)
   m.execute(root,True);m.execute(root,True,True)
   m.execute(root,False);m.execute(root,False,True)
   self.assertEqual(before,{p:p.read_text() for p in before})
   self.assertEqual(untouched.read_text(),'five rows and swipe')
   m.execute(root,True);self.assertEqual(changes,{p:p.read_text() for p in changes})
 def test_unknown_post_experiment_edit_blocks_restore_atomically(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.seed(root);m.execute(root,True)
   p=root/list(DATA['frozen'])[-1];p.write_text(p.read_text()+'new unrelated work')
   before={root/p:(root/p).read_text() for p in DATA['frozen']}
   with self.assertRaises(RuntimeError):m.execute(root,False)
   self.assertEqual(before,{p:p.read_text() for p in before})
 def test_late_bad_anchor_writes_nothing(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);self.seed(root);p=root/m.CHANGES[-1]['path'];p.write_text('bad pin')
   before={root/p:(root/p).read_text() for p in DATA['frozen']}
   with self.assertRaises(RuntimeError):m.execute(root,True)
   self.assertEqual(before,{p:p.read_text() for p in before});self.assertFalse((root/m.STATE).exists())
if __name__=='__main__':unittest.main()
