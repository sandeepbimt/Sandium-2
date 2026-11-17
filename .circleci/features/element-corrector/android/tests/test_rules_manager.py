#!/usr/bin/env python3
"""Host Java type/lifecycle wiring checks; Android/Mojo/JSON APIs are stubbed, not APK QA."""
from pathlib import Path
import subprocess,tempfile,unittest,importlib.util
ROOT=Path(__file__).resolve().parents[5]
JAVA=Path(__file__).resolve().parents[1]/'java/org/chromium/chrome/browser/sandium/dark'
STUBS={
'android/content/Context':'public class Context {public android.content.ContentResolver getContentResolver(){return null;}}',
'android/content/ContentResolver':'public class ContentResolver {public java.io.InputStream openInputStream(android.net.Uri u)throws java.io.IOException{return null;}public java.io.OutputStream openOutputStream(android.net.Uri u,String s)throws java.io.IOException{return null;}}',
'android/content/Intent':'public class Intent {public static String ACTION_CREATE_DOCUMENT="create",ACTION_OPEN_DOCUMENT="open",CATEGORY_OPENABLE="openable",EXTRA_TITLE="title";public Intent(String a){}public Intent addCategory(String c){return this;}public Intent setType(String t){return this;}public Intent putExtra(String k,String v){return this;}public android.net.Uri getData(){return null;}}',
'android/content/ActivityNotFoundException':'public class ActivityNotFoundException extends RuntimeException {}',
'android/content/DialogInterface':'public interface DialogInterface {interface OnClickListener {void onClick(DialogInterface d,int w);}}',
'android/app/Activity':'public class Activity extends android.content.Context {public static int RESULT_OK=1;}',
'android/app/AlertDialog':'public class AlertDialog {public void dismiss(){} public static class Builder {public Builder(android.content.Context c){}public Builder setTitle(String s){return this;}public Builder setMessage(String s){return this;}public Builder setView(Object v){return this;}public Builder setPositiveButton(String s,android.content.DialogInterface.OnClickListener l){return this;}public Builder setNegativeButton(String s,android.content.DialogInterface.OnClickListener l){return this;}public AlertDialog show(){return new AlertDialog();}}}',
'android/net/Uri':'public class Uri {public String getScheme(){return "content";}}',
'android/os/Bundle':'public class Bundle {}',
'android/os/Looper':'public class Looper {public static Looper getMainLooper(){return null;}}',
'android/os/Handler':'public class Handler {public Handler(Looper l){}public void post(Runnable r){r.run();}}',
'android/content/res/Resources':'public class Resources {public android.util.DisplayMetrics getDisplayMetrics(){return new android.util.DisplayMetrics();}}',
'android/util/DisplayMetrics':'public class DisplayMetrics {public float density=1;}',
'android/widget/TextView':'public class TextView {public TextView(android.content.Context c){}public void setText(String t){}public void setTextIsSelectable(boolean b){}public void setPadding(int a,int b,int c,int d){}}',
'android/widget/ScrollView':'public class ScrollView {public ScrollView(android.content.Context c){}public void addView(Object o){}}',
'android/widget/Toast':'public class Toast {public static int LENGTH_LONG=1;public static Toast makeText(android.content.Context c,String s,int i){return new Toast();}public void show(){}}',
'androidx/preference/Preference':'public class Preference {public static java.util.List<String> titles=new java.util.ArrayList<>();public Preference(android.content.Context c){}public void setTitle(String s){titles.add(s);}public void setSummary(String s){}public void setSelectable(boolean b){}public interface Listener {boolean click(Preference p);}public void setOnPreferenceClickListener(Listener l){}}',
'androidx/preference/PreferenceGroup':'public class PreferenceGroup extends Preference {public PreferenceGroup(android.content.Context c){super(c);}public void addPreference(Preference p){}}',
'androidx/preference/PreferenceScreen':'public class PreferenceScreen extends PreferenceGroup {public PreferenceScreen(android.content.Context c){super(c);}}',
'androidx/preference/PreferenceCategory':'public class PreferenceCategory extends PreferenceGroup {public PreferenceCategory(android.content.Context c){super(c);}}',
'androidx/preference/PreferenceManager':'public class PreferenceManager {public PreferenceScreen createPreferenceScreen(android.content.Context c){return new PreferenceScreen(c);}}',
'org/chromium/base/supplier/MonotonicObservableSupplier':'public interface MonotonicObservableSupplier<T> {}',
'org/chromium/base/supplier/SettableMonotonicObservableSupplier':'public interface SettableMonotonicObservableSupplier<T> extends MonotonicObservableSupplier<T> {void set(T value);}',
'org/chromium/base/supplier/ObservableSuppliers':'public class ObservableSuppliers {public static <T> SettableMonotonicObservableSupplier<T> createMonotonic(){return v->{};}}',
'org/chromium/chrome/browser/profiles/Profile':'public class Profile {public boolean isNativeInitialized(){return true;}public boolean shutdownStarted(){return false;}public boolean isOffTheRecord(){return false;}}',
'org/chromium/chrome/browser/settings/BravePreferenceFragment':'''public class BravePreferenceFragment {public void onCreatePreferences(android.os.Bundle b,String s){}public org.chromium.base.supplier.MonotonicObservableSupplier<String> getPageTitle(){return null;}public androidx.preference.PreferenceManager getPreferenceManager(){return new androidx.preference.PreferenceManager();}public void setPreferenceScreen(androidx.preference.PreferenceScreen p){}public android.app.Activity getActivity(){return new android.app.Activity();}public android.content.Context requireContext(){return getActivity();}public org.chromium.chrome.browser.profiles.Profile getProfile(){return new org.chromium.chrome.browser.profiles.Profile();}public android.content.res.Resources getResources(){return new android.content.res.Resources();}public void startActivityForResult(android.content.Intent i,int r){}public void onActivityResult(int r,int result,android.content.Intent i){}public void onDestroy(){}}''',
'org/chromium/brave_shields/mojom/FilterListAndroidHandler':'public interface FilterListAndroidHandler {void getCustomFilters(java.util.function.Consumer<String> c);void updateCustomFilters(String s,java.util.function.Consumer<Boolean> c);void close();}',
'org/chromium/chrome/browser/shields/FilterListServiceFactory':'public class FilterListServiceFactory {public static FilterListServiceFactory getInstance(){return new FilterListServiceFactory();}public org.chromium.brave_shields.mojom.FilterListAndroidHandler getFilterListAndroidHandler(org.chromium.chrome.browser.profiles.Profile p,java.util.function.Consumer<Object> c){return null;}}',
'org/chromium/chrome/browser/sandium/dark/SandiumElementColorsUtils':'public class SandiumElementColorsUtils {public static boolean appendAdRules(org.chromium.chrome.browser.profiles.Profile p,String s){return true;}public static String exportRules(org.chromium.chrome.browser.profiles.Profile p){return "{}";}public static String importRules(org.chromium.chrome.browser.profiles.Profile p,String s,boolean b){return "{}";}}',
'org/json/JSONTokener':'public class JSONTokener {public JSONTokener(String s){}public Object nextValue()throws JSONException{return new JSONObject();}public char nextClean()throws JSONException{return 0;}}',
'org/json/JSONException':'public class JSONException extends Exception {public JSONException(String s){super(s);}}',
'org/json/JSONObject':'''public class JSONObject {public JSONObject(){}public JSONObject(String s)throws JSONException{}public JSONObject put(String k,Object v)throws JSONException{return this;}public String toString(int i)throws JSONException{return "{}";}public String toString(){return "{}";}public String optString(String s){return "";}public int optInt(String s){return 0;}public int length(){return 0;}public Object get(String s)throws JSONException{return null;}public int getInt(String s)throws JSONException{return 0;}public String getString(String s)throws JSONException{return "";}public boolean getBoolean(String s)throws JSONException{return false;}public boolean has(String s){return false;}public java.util.Iterator<String> keys(){return java.util.Collections.emptyIterator();}public JSONArray getJSONArray(String s)throws JSONException{return new JSONArray();}public JSONObject getJSONObject(String s)throws JSONException{return this;}}''',
'org/json/JSONArray':'public class JSONArray {public int length(){return 0;}public JSONObject getJSONObject(int i)throws JSONException{return new JSONObject();}}'
}
class Rules(unittest.TestCase):
 def test_java_compile_and_lossless_ad_merge(self):
  with tempfile.TemporaryDirectory() as td:
   out=Path(td); sources=[]
   for name,body in STUBS.items():
    path=out/(name+'.java');path.parent.mkdir(parents=True,exist_ok=True);path.write_text('package '+name.rsplit('/',1)[0].replace('/','.')+';\n'+body);sources.append(str(path))
   test=out/'RulesMergeTest.java';test.write_text('''import org.chromium.chrome.browser.sandium.dark.SandiumRuleBackup;class RulesMergeTest {static void eq(String a,String b){if(!a.equals(b))throw new AssertionError();}public static void main(String[] args)throws Exception {String a="! original\\r\\n||example.com^\\r\\n", b="!#if env_chromium\\nexample.org##.ad\\n!#endif\\n";eq(SandiumRuleBackup.mergeAds(a,b),a+b);eq(SandiumRuleBackup.mergeAds(a+b,b),a+b);eq(SandiumRuleBackup.mergeAds(a,""),a);eq(SandiumRuleBackup.mergeAds("",b),b);eq(SandiumRuleBackup.mergeAds(a,a),a);eq(SandiumRuleBackup.mergeAds("no newline",b),"no newline\\n"+b);try{SandiumRuleBackup.bounded("a".repeat(SandiumRuleBackup.MAX_BYTES+1));throw new AssertionError();}catch(org.json.JSONException expected){}try{SandiumRuleBackup.bounded("é".repeat(SandiumRuleBackup.MAX_BYTES/2+1));throw new AssertionError();}catch(org.json.JSONException expected){}androidx.preference.Preference.titles.clear();var colors=new org.chromium.chrome.browser.sandium.dark.SandiumRulesPreferences();colors.onCreatePreferences(null,null);String colorTitles=String.join("|",androidx.preference.Preference.titles);if(!colorTitles.contains("Download color rules")||colorTitles.contains("blocking")||colorTitles.contains("ad rules"))throw new AssertionError(colorTitles);androidx.preference.Preference.titles.clear();var ads=new org.chromium.chrome.browser.sandium.dark.SandiumBlockingRulesPreferences();ads.onCreatePreferences(null,null);String adTitles=String.join("|",androidx.preference.Preference.titles);if(!adTitles.contains("Download custom blocking rules")||adTitles.contains("color"))throw new AssertionError(adTitles);var owns=colors.getClass().getDeclaredMethod("ownsRequest",int.class);owns.setAccessible(true);if(!(Boolean)owns.invoke(colors,9401)||(Boolean)owns.invoke(colors,9403)||(Boolean)owns.invoke(ads,9401)||!(Boolean)owns.invoke(ads,9403))throw new AssertionError("cross-category file result");System.out.println("8 merge/bounds and 6 actual-screen/scope assertions passed; Android and JSON APIs stubbed");}}''')
   subprocess.run(['java','com.sun.tools.javac.Main','-d',str(out),*sources,str(JAVA/'SandiumRuleBackup.java'),str(JAVA/'SandiumRulesPreferences.java'),str(JAVA/'SandiumBlockingRulesPreferences.java'),str(test)],check=True)
   subprocess.run(['java','-cp',str(out),'RulesMergeTest'],check=True)
 def test_local_and_private_guards(self):
  text=(JAVA/'SandiumRulesPreferences.java').read_text()
  for marker in ('isOffTheRecord()', 'ACTION_CREATE_DOCUMENT', 'ACTION_OPEN_DOCUMENT', 'CATEGORY_OPENABLE', 'MAX_BYTES', 'CodingErrorAction.REPORT','onDestroy()', 'mAdHandler.close()', 'importRules(getProfile(), imported, false)', 'importRules(getProfile(), imported, true)'):
   self.assertIn(marker,text)
  self.assertNotIn('ACTION_SEND',text)
  self.assertNotIn('updateCustomFilters(',text)
  self.assertIn('appendAdRules(getProfile(), imported)',text)
  self.assertNotIn('HttpURLConnection',text)
 def test_duplicate_setting_removed_and_manager_reachable(self):
  spec=importlib.util.spec_from_file_location('dark',ROOT/'.circleci/scripts/apply-sandium-dark-pages.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
  fixture=ROOT/'tests/fixtures/dark-pages/brave'/mod.APPEARANCE
  rendered=mod.appearance(fixture.read_text())
  self.assertNotIn('darkPages.setKey',rendered)
  self.assertIn('savedRules.setFragment(org.chromium.chrome.browser.sandium.dark.SandiumRulesPreferences.class.getName())',rendered)
  self.assertEqual(rendered,mod.appearance(rendered))
  self.assertIn('savedRules.setTitle("Element color corrections")', rendered)
  self.assertNotIn('custom ad rules', rendered)
  spec=importlib.util.spec_from_file_location('element', ROOT/'.circleci/features/element-corrector/android/apply.py');element=importlib.util.module_from_spec(spec);spec.loader.exec_module(element)
  xml=(ROOT/'tests/fixtures/dark-pages/brave'/element.PRIVACY_XML).read_text()
  patched=element.blocking_settings_xml(xml)
  self.assertEqual(patched,element.blocking_settings_xml(patched))
  self.assertIn('SandiumBlockingRulesPreferences',patched)
  self.assertIn('org.chromium.chrome.browser.shields.ContentFilteringFragment',patched)
  self.assertLess(patched.index('android:key="content_filtering"'),patched.index('android:key="sandium_saved_blocking_rules"'))
  privacy=(ROOT/'tests/fixtures/dark-pages/brave'/element.PRIVACY_JAVA).read_text()
  self.assertIn('PREF_CONTENT_FILTERING,\n        "sandium_saved_blocking_rules",',element.blocking_settings_java(privacy))
if __name__=='__main__':unittest.main()
