import importlib.util,struct,unittest,tempfile,zipfile
from pathlib import Path
P=Path(__file__).resolve().parents[1]/'.circleci/scripts/audit-sandium-stripped-apk.py'
spec=importlib.util.spec_from_file_location('apk_audit',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def dex(names,defined):
 n=len(names);d=bytearray(112+8*n+32*len(defined));d[:8]=b'dex\n035\0';struct.pack_into('<II',d,56,n,112);struct.pack_into('<II',d,64,n,112+4*n);struct.pack_into('<II',d,96,len(defined),112+8*n)
 for i,s in enumerate(names):
  struct.pack_into('<I',d,112+4*i,len(d));struct.pack_into('<I',d,112+4*n+4*i,i);d.extend(bytes([len(s)])+s.encode()+b'\0')
 for i,t in enumerate(defined):struct.pack_into('<I',d,112+8*n+32*i,t)
 struct.pack_into('<I',d,32,len(d));return bytes(d)
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
if __name__=='__main__':unittest.main()
