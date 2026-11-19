"""Exact-pair admission and inverse journal provenance, independent of GN/runtime."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
def load(path):
 sp=importlib.util.spec_from_file_location('m'+str(abs(hash(path))),ROOT/path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
I=load('.circleci/scripts/sandium-source-identity.py')
class Identity158(unittest.TestCase):
 def test_pair_matrix_and_all_entry_helpers(self):
  helpers=[I.verify]
  for p in ['.circleci/scripts/apply-sandium-dark-pages.py','.circleci/scripts/apply-sandium-dark-combined.py','.circleci/features/page-text/apply.py']:
   helpers.append(load(p).verify_source_identity)
  for p in ['experiments/native-navigation/apply.py','experiments/single-handoff/apply.py']:helpers.append(load(p).source_identity)
  for fn in helpers:
   for pair in I.PAIRS:
    with patch('subprocess.check_output',side_effect=[x+'\n' for x in pair]):self.assertEqual(fn(Path('/fixture')),pair)
   for pair in [(I.PAIRS[0][0],I.PAIRS[1][1]),(I.PAIRS[1][0],I.PAIRS[0][1]),('0'*40,I.PAIRS[1][1])]:
    with patch('subprocess.check_output',side_effect=list(pair)),self.assertRaises(ValueError):fn(Path('/fixture'))
 def test_native_actual_pair_recorded_and_wrong_inverse_rejected(self):
  n=load('experiments/native-navigation/apply.py')
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);p=root/'test';p.write_text('before')
   with patch.object(n,'transform',return_value={p:'after'}),patch.object(n,'geometry_changes',return_value={}),patch.object(n.settings,'plan',return_value={}):
    n.execute(root,True,identity=I.PAIRS[1])
   state=json.loads((root/n.STATE).read_text());self.assertEqual((state['chromium_pin'],state['brave_pin']),I.PAIRS[1])
   with self.assertRaisesRegex(RuntimeError,'identity'):n.execute(root,False,identity=I.PAIRS[0])
   self.assertEqual(p.read_text(),'after');n.execute(root,False,identity=I.PAIRS[1]);self.assertEqual(p.read_text(),'before')
 def test_outer_actual_pair_and_inverse(self):
  h=load('experiments/single-handoff/apply.py')
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);p=root/'test';p.write_text('before')
   with patch.object(h,'proposed',return_value={p:'after'}):h.execute(root,True,identity=I.PAIRS[1])
   self.assertEqual(json.loads((root/h.STATE).read_text())['source_identity'],list(I.PAIRS[1]))
   with self.assertRaisesRegex(RuntimeError,'identity'):h.execute(root,False,identity=I.PAIRS[0])
   h.execute(root,False,identity=I.PAIRS[1]);self.assertEqual(p.read_text(),'before')
if __name__=='__main__':unittest.main()
