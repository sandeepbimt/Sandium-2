import importlib.util,sys,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'.circleci/upgrades'))
s=importlib.util.spec_from_file_location('upgrade_apk',ROOT/'.circleci/upgrades/apk.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Apk(unittest.TestCase):
 def fixture(self,r,abi='arm64-v8a'):
  a=r/'brave-work/src/out/android_Release_arm64/apks/BraveMonoarm64.apk';a.parent.mkdir(parents=True)
  with zipfile.ZipFile(a,'w') as z:z.writestr('lib/'+abi+'/libchrome.so',b'test only, not a signed APK')
  d=r/'brave-apk';d.mkdir();(d/'Sandium-Brave-test.apk').write_bytes(a.read_bytes());(d/'apk-signature.txt').write_text('Signer #1 certificate SHA-256 digest: '+m.BASELINE_CERT+'\n')
  (d/'status.txt').write_text('\n'.join(k+'=true' for k in m.FIELDS)+'\nAPK_PACKAGE_ID=com.brave.browser_default\nAPK_SIZE_BYTES='+str(a.stat().st_size)+'\n');return d
 def test_gate_composition_requires_verified_certificate(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);self.fixture(r);self.assertEqual(m.verify_export(r)['certificate_upgrade_parity'],'verified1402')
 def test_foreign_certificate_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);d=self.fixture(r);(d/'apk-signature.txt').write_text('Signer #1 certificate SHA-256 digest: '+'0'*64+'\n')
   with self.assertRaisesRegex(ValueError,'certificate differs'):m.verify_export(r)
 def test_failed_export_status_not_success(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);d=self.fixture(r);p=d/'status.txt';p.write_text(p.read_text().replace('APK_SIGNATURE_VALID=true','APK_SIGNATURE_VALID=false'))
   with self.assertRaisesRegex(ValueError,'incomplete'):m.verify_export(r)
 def test_wrong_abi_or_mismatched_copy_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);self.fixture(r,'armeabi-v7a')
   with self.assertRaisesRegex(ValueError,'ARM64'):m.verify_export(r)
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);d=self.fixture(r);(d/'Sandium-Brave-test.apk').write_bytes(b'wrong')
   with self.assertRaisesRegex(ValueError,'differs'):m.verify_export(r)
if __name__=='__main__':unittest.main()
