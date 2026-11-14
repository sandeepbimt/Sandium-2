#!/usr/bin/env python3
import runpy,unittest,tempfile,shutil,re
from pathlib import Path
M=runpy.run_path(str(Path(__file__).with_name('apply-sandium-remove-vpn.py')))
FIX=Path(__file__).resolve().parents[1]/'tests/vpn-fixtures'
class Tests(unittest.TestCase):
 def test_pinned_closure_and_idempotence(self):
  for p in M['FILES']:
   s=(FIX/p).read_text();out=M['transform'](p,s)
   self.assertEqual(M['transform'](p,out),out,p)
   if p.endswith('.java'):
    masked=M['mask'](out)
    self.assertEqual(masked.count('{'),masked.count('}'),p)
    self.assertNotRegex(masked,r'\b(?:BraveVpn\w*|Wireguard\w*|GoBackend|VpnCalloutPreference)\b')
 def test_preserve_critical_shared_behavior(self):
  p=M['JAVA']+'BraveApplicationImplBase.java';out=M['transform'](p,(FIX/p).read_text())
  self.assertIn('SafeBrowsingApiBridge.setSafeBrowsingApiHandler(',out)
  self.assertIn('BraveSearchEngineUtils::initializeOnProfileAdded',out)
  p=M['JAVA']+'app/BraveActivity.java';out=M['transform'](p,(FIX/p).read_text())
  self.assertIn('BraveOriginSubscriptionPrefs.resumeCredentialFetchIfNeeded(profile)',out)
  self.assertIn('openBraveWallet(false, false, false)',out)
  self.assertIn('openBraveLeo()',out)
 def test_manifest_and_build_inputs(self):
  for p in ['android/brave_java_sources.gni','build/android/config.gni','android/java/AndroidManifest.xml']:
   out=M['transform'](p,(FIX/p).read_text())
   self.assertNotIn('/browser/vpn/',out)
   self.assertNotIn('org.chromium.chrome.browser.vpn.',out)
   self.assertNotIn('com_wireguard_android',out)
 def test_drift_fails_before_writes(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);shutil.copytree(FIX,root,dirs_exist_ok=True)
   p=root/M['FILES'][0];p.write_text(p.read_text().replace('public class BraveActivity','// changed\npublic class BraveActivity')+'\nclass NewConsumer { BraveVpnNativeWorker unsafe; }\n')
   before={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
   with self.assertRaises(ValueError):M['apply'](root)
   self.assertEqual(before,{str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()})
if __name__=='__main__':unittest.main()
