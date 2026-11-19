import pathlib,tempfile,subprocess,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class Tests(unittest.TestCase):
 def test_actual_facade_native_authority_and_selection(self):
  files={
'android/content/Context.java':'package android.content; public class Context {}',
'android/net/Uri.java':'''package android.net; public class Uri {java.net.URI u; public static Uri parse(String s){Uri r=new Uri();try{r.u=new java.net.URI(s);}catch(Exception e){r.u=java.net.URI.create("");}return r;}public String getScheme(){return u.getScheme();}public String getHost(){return u.getHost();}public String getUserInfo(){return u.getUserInfo();}public String getFragment(){return u.getFragment();}}''',
'org/chromium/base/ThreadUtils.java':'package org.chromium.base; public class ThreadUtils {public static void assertOnUiThread(){}}',
'org/chromium/base/ContextUtils.java':'''package org.chromium.base; public class ContextUtils {static Pref p=new Pref();public static Pref getAppSharedPreferences(){return p;}public static class Pref {java.util.Map<String,String> m=new java.util.HashMap<>();public String getString(String k,String d){return m.getOrDefault(k,d);}public Pref edit(){return this;}public Pref putString(String k,String v){m.put(k,v);return this;}public void apply(){}}}''',
'org/chromium/base/library_loader/LibraryLoader.java':'package org.chromium.base.library_loader; public class LibraryLoader {public static boolean ready=true;public static LibraryLoader getInstance(){return new LibraryLoader();}public boolean isInitialized(){return ready;}}',
'org/chromium/chrome/browser/net/SecureDnsManagementMode.java':'package org.chromium.chrome.browser.net; public class SecureDnsManagementMode {public static final int NO_OVERRIDE=0;}',
'org/chromium/net/SecureDnsMode.java':'package org.chromium.net; public class SecureDnsMode {public static final int OFF=0,AUTOMATIC=1,SECURE=2;}',
'org/chromium/chrome/browser/settings/SettingsNavigationFactory.java':'package org.chromium.chrome.browser.settings; public class SettingsNavigationFactory {public static SettingsNavigationFactory createSettingsNavigation(){return new SettingsNavigationFactory();} public void startSettings(android.content.Context c,Class<?> t){}}',
'org/json/JSONException.java':'package org.json; public class JSONException extends Exception {}',
'org/json/JSONObject.java':'package org.json; public class JSONObject {java.util.Map<String,String> m=new java.util.HashMap<>();public JSONObject put(String k,String v)throws JSONException{m.put(k,v);return this;}public String getString(String k)throws JSONException{return m.get(k);}}',
'org/json/JSONArray.java':'''package org.json; public class JSONArray {static java.util.Map<String,java.util.List<JSONObject>> saved=new java.util.HashMap<>();java.util.List<JSONObject> items=new java.util.ArrayList<>();public JSONArray(){}public JSONArray(String s)throws JSONException {items=new java.util.ArrayList<>(saved.getOrDefault(s,items));}public int length(){return items.size();}public JSONObject getJSONObject(int i)throws JSONException{return items.get(i);}public JSONArray put(JSONObject x){items.add(x);return this;}public String toString(){String key="saved:"+saved.size();saved.put(key,new java.util.ArrayList<>(items));return key;}}''',
'org/chromium/chrome/browser/privacy/secure_dns/SecureDnsSettings.java':'package org.chromium.chrome.browser.privacy.secure_dns; public class SecureDnsSettings {}',
'org/chromium/chrome/browser/privacy/secure_dns/SecureDnsBridge.java':'''package org.chromium.chrome.browser.privacy.secure_dns; class SecureDnsBridge {static int mode=0,writes=0,management=0;static String config="";static boolean managed=false,configManaged=false;static int getMode(){return mode;}static String getConfig(){return config;}static void setMode(int m){mode=m;writes++;}static boolean setConfig(String c){if(!validateConfig(c))return false;config=c;writes++;return true;}static boolean validateConfig(String c){return c.startsWith("https://");}static boolean isModeManaged(){return managed;}static boolean isConfigManaged(){return configManaged;}static int getManagementMode(){return management;}static boolean probeConfig(String c){throw new AssertionError("No implicit probe allowed");}}''',
'org/chromium/chrome/browser/privacy/secure_dns/Test.java':'''package org.chromium.chrome.browser.privacy.secure_dns; public class Test {static void check(boolean b){if(!b)throw new AssertionError();}public static void main(String[] args){
check(!SandiumSecureDns.getState().enabled);check(SecureDnsBridge.writes==0);
check(!SandiumSecureDns.setEnabled(true));check(SecureDnsBridge.writes==0);
SecureDnsBridge.mode=1;check(SandiumSecureDns.getState().providerId.equals("automatic"));check(SecureDnsBridge.writes==0);
check(SandiumSecureDns.selectProvider("google"));check(SecureDnsBridge.mode==2);check(SecureDnsBridge.config.equals("https://dns.google/dns-query"));
int w=SecureDnsBridge.writes;SandiumSecureDns.getState();SandiumSecureDns.getProviders();check(w==SecureDnsBridge.writes);
check(SandiumSecureDns.setEnabled(false));check(!SandiumSecureDns.getState().enabled);check(!SecureDnsBridge.config.isEmpty());
SecureDnsBridge.configManaged=true;w=SecureDnsBridge.writes;check(!SandiumSecureDns.selectProvider("quad9"));check(!SandiumSecureDns.setEnabled(false));check(w==SecureDnsBridge.writes);SecureDnsBridge.configManaged=false;
check(!SandiumSecureDns.validCustom("http://resolver.example/dns-query"));check(!SandiumSecureDns.validCustom("https://u:p@resolver.example/dns-query"));check(!SandiumSecureDns.validCustom("https://resolver.example/dns-query#fragment"));
check(!SandiumSecureDns.validCustom("https://resolver.example/dns-query"+((char)10)+((char)10)+"https://other.example/dns-query"));
check(SandiumSecureDns.validCustom("https://resolver.example/dns-query{?dns}"));
w=SecureDnsBridge.writes;check(SandiumSecureDns.saveCustom("Example","https://resolver.example/dns-query"));check(w==SecureDnsBridge.writes);
String id="";for(SandiumSecureDns.Provider p:SandiumSecureDns.getProviders())if(p.name.equals("Example"))id=p.id;check(!id.isEmpty());
check(SandiumSecureDns.selectProvider(id));check(SandiumSecureDns.getState().providerName.equals("Example"));
w=SecureDnsBridge.writes;check(SandiumSecureDns.removeCustom(id));check(w==SecureDnsBridge.writes);check(SandiumSecureDns.getState().providerId.equals("custom:current"));
check(!SandiumSecureDns.saveCustom("Duplicate","https://dns.google/dns-query"));
}}'''
}
  files['org/chromium/chrome/browser/privacy/secure_dns/SandiumSecureDns.java']=(ROOT/'experiments/secure-dns/java/SandiumSecureDns.java').read_text()
  with tempfile.TemporaryDirectory() as td:
   paths=[]
   for name,source in files.items():
    p=pathlib.Path(td)/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(source);paths.append(str(p))
   subprocess.run(['java','--module','jdk.compiler/com.sun.tools.javac.Main',*paths],check=True,capture_output=True)
   subprocess.run(['java','-cp',td,'org.chromium.chrome.browser.privacy.secure_dns.Test'],check=True,capture_output=True)
if __name__=='__main__':unittest.main()
