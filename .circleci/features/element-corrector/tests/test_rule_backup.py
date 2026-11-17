"""Backup source contracts plus real store algorithm compiled with narrow API stubs.
These tests are not Chromium integration, JNI or filesystem durability tests.
"""
import pathlib,re,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class Backup(unittest.TestCase):
 def test_backup_contract(self):
  s=(ROOT/'native/element_color_rule_store.cc').read_text()
  body=s.split('ElementColorRuleStore::ImportRules(',1)[1].split('bool ElementColorRuleStore::Reset',1)[0]
  self.assertIn('base::JSONReader::ReadDict(json, base::JSON_PARSE_RFC)',body)
  self.assertIn('private_ || !prefs_',body)
  self.assertEqual(body.count('prefs_->SetDict('),1)
  self.assertEqual(body.count('CommitPendingWrite()'),1)
  self.assertNotIn('Save(',body.replace('// One transaction, never Save() in a loop: failures leave all prefs intact.',''))
  self.assertLess(body.index('if (!encoded'),body.index('prefs_->SetDict('))
  self.assertIn('origin.Serialize() != key',s)
 def test_store_algorithm(self):
  source=(ROOT/'native/element_color_rule_store.cc').read_text()
  header=(ROOT/'native/element_color_rule_store.h').read_text()
  strip=lambda s:re.sub(r'^#.*$','',s,flags=re.M)
  fixture=(ROOT/'tests/fixtures/rule_backup_stubs.cc').read_text()
  setup,tests=fixture.split('// PRODUCTION_STORE_HERE')
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'test.cc';p.write_text(setup+strip(header)+strip(source)+tests)
   result=subprocess.run(['c++','-std=c++20','-Wall','-Wextra','-Werror',str(p),'-o',d+'/test'],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
   result=subprocess.run([d+'/test'],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
if __name__=='__main__':unittest.main()
