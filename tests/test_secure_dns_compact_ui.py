"""Native facade routing and Android API compilation; not device interaction tests."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/'android/java/org/chromium/chrome/browser/privacy/secure_dns/SandiumSecureDnsDropdown.java'
class CompactDnsUi(unittest.TestCase):
 def test_no_parallel_state_or_per_site_resolver(self):
  s=JAVA.read_text()
  for api in ['SandiumSecureDns.getState()', 'SandiumSecureDns.getProviders()', 'SandiumSecureDns.setEnabled(false)', 'SandiumSecureDns.selectProvider(', 'SandiumSecureDns.isReady()', 'SandiumSecureDns.isManaged()', 'SandiumSecureDns.openSettings(']: self.assertIn(api,s)
  for forbidden in ['SharedPreferences','putBoolean','HttpURLConnection','setDns','mProfile','postDelayed']: self.assertNotIn(forbidden,s)
  self.assertIn('popup.getMenu().setGroupCheckable(0, true, true)',s)
  self.assertIn('mPopup.dismiss()',s)
 def test_shields_migrates_existing_grouped_input(self):
  spec=importlib.util.spec_from_file_location('popup', ROOT/'.circleci/scripts/apply-sandium-shields-popup.py')
  m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  old='        setupAdvancedOptionsListeners();\n        applySandiumPopupVisibility();'
  new=m.dns_ui(old)
  self.assertEqual(new,m.dns_ui(new))
  self.assertEqual(new.count('new org.chromium.chrome.browser.privacy.secure_dns.SandiumSecureDnsDropdown'),1)
  self.assertIn('context, true',new)
 def test_welcome_waits_for_native_initialization(self):
  s=(ROOT/'android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java').read_text()
  init=s.split('void initialize(Profile profile)',1)[1].split('void destroy()',1)[0]
  self.assertIn('mSecureDns.finishNativeStartup()',init)
  self.assertIn('mNativeStartupComplete && SandiumSecureDns.isReady()',JAVA.read_text())
  self.assertIn('mSecureDns.setColors(TEXT, SECONDARY, CARD, PRIMARY)',s)
  self.assertIn('mActivity, false, false',s)
 def test_dns_only_takes_space_in_existing_expanded_options(self):
  s=(ROOT/'android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java').read_text()
  card=s.split('private void buildMainSettingsCard()',1)[1].split('private void buildFilterProgressCard()',1)[0]
  self.assertNotIn('mSecureDns',card.split('card.addView(mAdvancedOptions, matchWrap());',1)[0])
  self.assertIn('mAdvancedOptions.setVisibility(View.GONE);',card)
  self.assertEqual(card.count('mAdvancedOptions.addView(mSecureDns, matchWrap());'),1)
  self.assertIn('mAdvancedOptions.setVisibility(mExpanded ? View.VISIBLE : View.GONE);',card)
  self.assertIn('else mScrollView.post(() -> mScrollView.scrollTo(0, 0));',card)
 def test_android_api_compilation(self):
  jar=Path(os.environ.get('RAWS_ANDROID_API_JAR','/workspace/shared/raws-api/android15.jar'))
  if not jar.exists(): self.skipTest('Android SDK API jar unavailable')
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);pkg=root/'org/chromium/chrome/browser/privacy/secure_dns';pkg.mkdir(parents=True)
   (pkg/JAVA.name).write_text(JAVA.read_text())
   (pkg/'SandiumSecureDns.java').write_text('''package org.chromium.chrome.browser.privacy.secure_dns;
public final class SandiumSecureDns {
 public static class State {public boolean enabled;public String providerId,providerName;}
 public static class Provider {public String id,name,template;}
 public static State getState(){return null;} public static java.util.List<Provider> getProviders(){return null;}
 public static boolean isReady(){return false;} public static boolean isManaged(){return false;}
 public static boolean setEnabled(boolean x){return false;} public static boolean selectProvider(String x){return false;}
 public static void openSettings(android.content.Context c){} }
''')
   names=[x.attrib['name'] for x in ET.parse(ROOT/'android/java/res/values/sandium_secure_dns_ui_strings.xml').getroot()]
   (pkg/'R.java').write_text('package org.chromium.chrome.browser.privacy.secure_dns;public class R {public static class string {'+''.join('public static final int '+n+'='+str(i+1)+';' for i,n in enumerate(names))+'}}')
   mat=root/'com/google/android/material';mat.mkdir(parents=True)
   (mat/'R.java').write_text('package com.google.android.material;public class R {public static class attr {public static final int colorOnSurface=1,colorOnSurfaceVariant=2,colorPrimary=3,colorSurfaceContainer=4;}}')
   result=subprocess.run(['javac','-cp',str(jar),'-d',str(root/'classes')]+[str(p) for p in root.rglob('*.java')],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stderr)
if __name__=='__main__': unittest.main()
