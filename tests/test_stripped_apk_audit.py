import importlib.util,struct,unittest,tempfile,zipfile
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'.circleci/scripts/audit-sandium-stripped-apk.py'
spec=importlib.util.spec_from_file_location('apk_audit',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def dex(names,defined):
 n=len(names);d=bytearray(112+8*n+32*len(defined));d[:8]=b'dex\n035\0';struct.pack_into('<II',d,56,n,112);struct.pack_into('<II',d,64,n,112+4*n);struct.pack_into('<II',d,96,len(defined),112+8*n)
 for i,s in enumerate(names):
  struct.pack_into('<I',d,112+4*i,len(d));struct.pack_into('<I',d,112+4*n+4*i,i);d.extend(bytes([len(s)])+s.encode()+b'\0')
 for i,t in enumerate(defined):struct.pack_into('<I',d,112+8*n+32*i,t)
 struct.pack_into('<III',d,32,len(d),112,0x12345678);return bytes(d)
class Audit(unittest.TestCase):
 def test_definitions_not_unused_references(self):
  d=dex(['Lretained/Core;','Lorg/chromium/chrome/browser/vpn/Impl;'],[0]);self.assertEqual(m.dex_classes(d),['Lretained/Core;'])
 def test_absent_dex_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'a.apk'
   with zipfile.ZipFile(p,'w') as z:z.writestr('resource','x')
   with self.assertRaisesRegex(ValueError,'No DEX'):m.audit(p)
 def test_multidex_feature_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'a.apk'
   with zipfile.ZipFile(p,'w') as z:
    z.writestr('classes.dex',dex(['Lretained/Core;'],[0]));z.writestr('classes2.dex',dex(['Lorg/chromium/chrome/browser/vpn/Impl;'],[0]))
   with self.assertRaisesRegex(ValueError,'implementations remain'):m.audit(p)
 def test_actual_leo_package_rejected(self):
  for name in ['Lorg/chromium/chrome/browser/brave_leo/BraveLeoUtils;', 'Lorg/chromium/chrome/browser/settings/BraveLeoPreferences;', 'Lorg/chromium/chrome/browser/ntp/SponsoredRichMediaWebView;', 'Lorg/chromium/chrome/browser/ntp/NewTabTakeoverSafeAreaReporter;']:
   with self.subTest(name=name), tempfile.TemporaryDirectory() as td:
    p=Path(td)/'a.apk'
    with zipfile.ZipFile(p,'w') as z:z.writestr('classes.dex',dex([name],[0]))
    with self.assertRaisesRegex(ValueError,'implementations remain'):m.audit(p)
 def test_truncated_fails(self):
  with self.assertRaises(ValueError):m.dex_classes(dex(['Lretained/Core;'],[0])[:-1])
 def test_malformed_tables_fail_closed(self):
  for offset,value in [(60,0xffffffff),(68,0xffffffff),(100,0xffffffff),(40,0x78563412),(36,0)]:
   d=bytearray(dex(['Lretained/Core;'],[0]));struct.pack_into('<I',d,offset,value)
   with self.subTest(offset=offset),self.assertRaises(ValueError):m.dex_classes(bytes(d))
 def test_bad_string_offset(self):
  d=bytearray(dex(['Lretained/Core;'],[0]));struct.pack_into('<I',d,112,len(d)+1)
  with self.assertRaisesRegex(ValueError,'string offset'):m.dex_classes(bytes(d))
 def test_report_scope_and_binding(self):
  import json,hashlib
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'a.apk';recipe=Path(td)/'recipe.json'
   with zipfile.ZipFile(p,'w') as z:z.writestr('classes.dex',dex(['Lretained/Core;'],[0]))
   with zipfile.ZipFile(p,'a') as z:z.writestr('AndroidManifest.xml','\0'.join(m.REQUIRED_ACTIVITIES))
   recipe.write_text(json.dumps({'schema':1,'groups':['group'+str(i) for i in range(13)],'brave_pin':'a'*40,'chromium_pin':'b'*40}))
   r=m.audit(p,recipe)
   self.assertEqual(r['apk_sha256'],hashlib.sha256(p.read_bytes()).hexdigest())
   self.assertEqual(len(r['checked_java_prefix_groups']),6)
   self.assertEqual(len(r['groups_without_java_prefix_proof']),7)
   self.assertFalse(r['all_13_removed_verified']);self.assertFalse(r['recipe_binding']['graph_verified'])
   self.assertFalse(r['mapping_checked'])
 def test_obfuscated_feature_rejected_using_mapping(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'a.apk';mapping=Path(td)/'mapping.txt'
   with zipfile.ZipFile(p,'w') as z:z.writestr('classes.dex',dex(['La/b;'],[0]))
   mapping.write_text('org.chromium.chrome.browser.vpn.Impl -> a.b:\n    void foo() -> x\n')
   with self.assertRaisesRegex(ValueError,'implementations remain'):m.audit(p,mapping=mapping)
 def test_mapping_only_unused_feature_not_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'a.apk';mapping=Path(td)/'mapping.txt'
   with zipfile.ZipFile(p,'w') as z:z.writestr('classes.dex',dex(['Lretained/Core;'],[0]))
   mapping.write_text('org.chromium.chrome.browser.vpn.Impl -> a.b:\n')
   self.assertTrue(m.audit(p,mapping=mapping)['mapping_checked'])
 def test_empty_and_duplicate_classes_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   for values in [[],['Lretained/Core;','Lretained/Core;']]:
    p=Path(td)/'a.apk'
    with zipfile.ZipFile(p,'w') as z:z.writestr('classes.dex',dex(values,list(range(len(values)))))
    with self.assertRaises(ValueError):m.audit(p)
 def test_duplicate_zip_entries_rejected(self):
  import warnings
  with tempfile.TemporaryDirectory() as td,warnings.catch_warnings():
   warnings.simplefilter('ignore');p=Path(td)/'a.apk'
   with zipfile.ZipFile(p,'w') as z:
    z.writestr('classes.dex',dex(['Lretained/Core;'],[0]));z.writestr('classes.dex',dex(['Lretained/Other;'],[0]))
   with self.assertRaisesRegex(ValueError,'Duplicate APK'):m.audit(p)
 def test_unknown_dex_version_rejected(self):
  d=bytearray(dex(['Lretained/Core;'],[0]));d[4:7]=b'041'
  with self.assertRaisesRegex(ValueError,'unsupported'):m.dex_classes(bytes(d))
if __name__=='__main__':unittest.main()
