"""Dormant staged SOURCE composition, not GN/Android/runtime validation."""
import gzip, hashlib, importlib.util, json, tempfile, unittest
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'experiments/single-handoff'
NAMES=('home','holder','holder_safety','holder_retention','eligibility','java_adapter','native_adapter','ui_gate','content_registration','java_registration')
def module(name):
 spec=importlib.util.spec_from_file_location(name,BASE/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class CompleteSourceComposition(unittest.TestCase):
 def originals(self):
  result={}
  def add(p,s,h=None):
   if h:self.assertEqual(hashlib.sha256(s.encode()).hexdigest(),h)
   if p in result:self.assertEqual(result[p],s,'Conflicting pinned fixture: '+p)
   result[p]=s
  for name in ('native-holder','native-handoff-adapter','static-layout-eligibility','content-registration','java-handoff-registration'):
   d=json.loads(gzip.decompress((BASE/'fixtures'/(name+'.json.gz')).read_bytes()))
   for p,item in d['files'].items():add(p,item.get('source',item.get('text')),item['sha256'])
  for name in ('compositor-view-java','root-ui-handoff-gate'):
   d=json.loads(gzip.decompress((BASE/'fixtures'/(name+'.json.gz')).read_bytes()));add(d['path'],d.get('source',d.get('text')),d['sha256'])
  add(module('home').DELEGATE,(BASE/'fixtures/NtpSmoothTransitionDelegate.java').read_text())
  return result
 def apply_stages(self,root,original):
  for p,s in original.items():f=root/p;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(s)
  outputs={}
  for name in NAMES:
   for p,s in module(name).plan(root).items():
    self.assertTrue(p.is_relative_to(root));p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s);outputs[str(p.relative_to(root))]=s
  return outputs
 def test_exact_all_stage_composition_and_replay(self):
  original=self.originals()
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   first=self.apply_stages(root/'first',original);second=self.apply_stages(root/'second',original)
   self.assertEqual(first,second)
   self.assertGreaterEqual(len(first),20)
   tab=first[module('holder').TAB]
   self.assertIn('if (!retireSandiumHandoff()) return;',tab)
   self.assertIn(module('holder').OFFER_BLOCK,tab)
   holder=first[module('holder_retention').PATH]
   self.assertIn(module('holder_retention').MARKER,holder)
   self.assertIn('installSandiumNativeHandoffSafety',holder)
   self.assertIn('mSandiumRetainedToken',holder)
   self.assertIn('isSandiumNativeHandoffUiClear()',first[module('ui_gate').PATH])
   # Production-shaped staged planner reads the real composed source, not fixtures.
   bridge=module('bridge')
   before={p:p.read_bytes() for p in (root/'first').rglob('*') if p.is_file()}
   planned=bridge.plan(root/'first')
   self.assertEqual(before,{p:p.read_bytes() for p in (root/'first').rglob('*') if p.is_file()})
   for p,text in planned.items():self.assertEqual(p.read_text(),text)
   # Journal all real staged outputs, including new components; restore exact preimages.
   third=root/'transaction'
   for p,s in original.items():
    target=third/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(s)
   with self.assertRaisesRegex(RuntimeError,'home baseline'):bridge.plan(third)
   for p,s in module('home').plan(third).items():p.write_text(s)
   original_bytes={p:p.read_bytes() for p in third.rglob('*') if p.is_file()}
   transaction=module('apply')
   with patch.object(transaction,'proposed',side_effect=bridge.plan):
    transaction.execute(third,True)
    transaction.execute(third,True,verify_only=True)
    transaction.execute(third,True)
   transaction.execute(third,False)
   restored={p:p.read_bytes() for p in third.rglob('*') if p.is_file() and p.name != transaction.STATE+'.restored'}
   self.assertEqual(original_bytes,restored)
   component=root/'first'/'chrome/browser/tab/java/src/org/chromium/chrome/browser/tab/NativePageHandoffOffer.java'
   component.write_text('conflicting external component')
   with self.assertRaises(ValueError):bridge.plan(root/'first')
   self.assertEqual(component.read_text(),'conflicting external component')
   self.assertIs(type(json.loads((BASE/'profile.json').read_text())['enabled']), bool)
if __name__=='__main__':unittest.main()
