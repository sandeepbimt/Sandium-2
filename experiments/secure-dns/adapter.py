"""Pinned Chromium Secure DNS facade/settings; no parallel resolver."""
from pathlib import Path
import gzip,json
HERE=Path(__file__).parent
PACKAGE='chrome/browser/privacy/java/src/org/chromium/chrome/browser/privacy/secure_dns/'
BRIDGE=PACKAGE+'SecureDnsBridge.java'
NATIVE='chrome/browser/privacy/secure_dns_bridge.cc'
GN='chrome/browser/privacy/BUILD.gn'
SETTINGS=PACKAGE+'SecureDnsSettings.java'

def once(s,old,new):
 if new in s:return s
 if s.count(old)!=1:raise ValueError('Secure DNS anchor drift: '+old[:100])
 return s.replace(old,new,1)

def transform(path,s):
 if path==BRIDGE:
  s=once(s,'    @NativeMethods\n    interface Natives {','''    static boolean validateConfig(String config) { return SecureDnsBridgeJni.get().validateConfig(config); }
    static boolean isConfigManaged() { return SecureDnsBridgeJni.get().isConfigManaged(); }

    @NativeMethods
    interface Natives {''')
  return once(s,'        boolean setConfig(@JniType("std::string") String config);','''        boolean setConfig(@JniType("std::string") String config);
        boolean validateConfig(@JniType("std::string") String config);
        boolean isConfigManaged();''')
 if path==NATIVE:
  return once(s,'static int32_t JNI_SecureDnsBridge_GetManagementMode() {','''// Sandium: validate without changing the current resolver or issuing a query.
static bool JNI_SecureDnsBridge_ValidateConfig(const std::string& config) {
  return !config.empty() && net::DnsOverHttpsConfig::FromString(config).has_value();
}

static bool JNI_SecureDnsBridge_IsConfigManaged() {
  return g_browser_process->local_state()->IsManagedPreference(
      prefs::kDnsOverHttpsTemplates);
}

static int32_t JNI_SecureDnsBridge_GetManagementMode() {''')
 if path==GN:
  anchor='      "java/src/org/chromium/chrome/browser/privacy/secure_dns/SecureDnsSettings.java",'
  s=once(s,anchor,anchor+'\n      "java/src/org/chromium/chrome/browser/privacy/secure_dns/SandiumSecureDns.java",\n      "java/src/org/chromium/chrome/browser/privacy/secure_dns/SandiumSecureDnsDropdown.java",')
  anchor='      "java/res/xml/secure_dns_settings.xml",'
  return once(s,anchor,anchor+'\n      "java/res/values/sandium_dns_native_strings.xml",\n      "java/res/values/sandium_secure_dns_ui_strings.xml",')
 raise ValueError(path)

def plan(root):
 root=Path(root); result={root/p:transform(p,(root/p).read_text()) for p in (BRIDGE,NATIVE,GN)}
 original=(root/SETTINGS).read_text()
 expected=json.loads(gzip.decompress((HERE/'fixtures/pinned.json.gz').read_bytes()))['files'][SETTINGS]['source']
 if original not in (expected,(HERE/'java/SecureDnsSettings.java').read_text()):raise ValueError('Secure DNS settings owner drift')
 for name in ('SandiumSecureDns.java','SecureDnsSettings.java'):
  result[root/PACKAGE/name]=(HERE/'java'/name).read_text()
 recipe=HERE.parents[1]
 result[root/PACKAGE/'SandiumSecureDnsDropdown.java']=(recipe/'android/java/org/chromium/chrome/browser/privacy/secure_dns/SandiumSecureDnsDropdown.java').read_text()
 result[root/'chrome/browser/privacy/java/res/values/sandium_dns_native_strings.xml']=(HERE/'res/sandium_dns_native_strings.xml').read_text()
 result[root/'chrome/browser/privacy/java/res/values/sandium_secure_dns_ui_strings.xml']=(recipe/'android/java/res/values/sandium_secure_dns_ui_strings.xml').read_text()
 return result
