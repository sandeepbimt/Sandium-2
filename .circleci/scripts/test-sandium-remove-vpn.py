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
 def test_private_ntp_promotion_is_removed_not_hidden(self):
  import xml.etree.ElementTree as ET
  p='android/java/res/layout/new_tab_page_incognito.xml'
  out=M['transform'](p,(FIX/p).read_text())
  ET.fromstring(out)
  self.assertNotRegex(out,r'product_vpn_layer_list|brave_new_tab_private_vpn|tv_third|iv_third|tv_try_vpn')
  self.assertIn('brave_new_tab_private_visibility_description',out)
  self.assertIn('layout_constraintBottom_toBottomOf="parent"',out)
  java=M['JAVA']+'ntp/IncognitoNewTabPageView.java'
  output=M['transform'](java,(FIX/java).read_text())
  self.assertNotRegex(M['mask'](output),r'mVpn|iv_third|tv_third|tv_try_vpn')
  self.assertIn('tintLayerListIcon(R.id.iv_second_icon, iconTint)',output)
  with self.assertRaises(ValueError):M['transform'](p,(FIX/p).read_text().replace('@+id/tv_try_vpn','@+id/new_vpn'))
 def test_drift_fails_before_writes(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);shutil.copytree(FIX,root,dirs_exist_ok=True)
   p=root/M['FILES'][0];p.write_text(p.read_text().replace('public class BraveActivity','// changed\npublic class BraveActivity')+'\nclass NewConsumer { BraveVpnNativeWorker unsafe; }\n')
   before={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
   with self.assertRaises(ValueError):M['apply'](root)
   self.assertEqual(before,{str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()})
if __name__=='__main__':unittest.main()
