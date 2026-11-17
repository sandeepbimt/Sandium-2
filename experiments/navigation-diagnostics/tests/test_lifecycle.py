import importlib.util,pathlib,re,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('life',ROOT/'apply-lifecycle.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_real_pinned_calls_and_replay(self):
  source=(ROOT/'fixtures/TabWebContentsObserver.java').read_text();out=m.transform(source)
  self.assertEqual(m.transform(out),out)
  for old,new in m.CHANGES:
   self.assertEqual(source.count(old),1);self.assertEqual(out.count(new),1)
   self.assertIn('isRecording() && !mTab.isIncognito()',new)
   self.assertIn('mTab.isIncognito(),',new)
 def test_actual_navigation_api_and_no_content(self):
  api=(ROOT/'fixtures/NavigationHandle.java').read_text()
  for old,new in m.CHANGES:
   added=new[len(old):]
   for method in re.findall(r'navigation\.(\w+)\(',added):
    self.assertRegex(api,r'public\s+[^\n{;]+\b'+method+r'\(')
   self.assertNotRegex(added,r'getUrl|getTitle|getResponseHeaders|getOrigin|toString')
 def test_fail_closed_drift(self):
  with self.assertRaises(ValueError):m.transform('invalid source')
if __name__=='__main__':unittest.main()
