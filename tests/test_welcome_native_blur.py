from pathlib import Path
import re, shutil, subprocess, tempfile, unittest
ROOT = Path(__file__).resolve().parents[1]
class WelcomeNativeBlur(unittest.TestCase):
    def test_two_options_and_new_preference_only(self):
        s=(ROOT/'android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java').read_text()
        picker=s.split('private void showBlurLevelPicker()',1)[1].split('private void applyBlurLevel',1)[0]
        self.assertIn('R.string.sandium_welcome_off',picker)
        self.assertIn('R.string.sandium_welcome_on',picker)
        self.assertNotIn('"Low"',picker)
        self.assertNotIn('"Medium"',picker)
        self.assertNotIn('"High"',picker)
        self.assertNotIn('.putString(PREF_BLUR_LEVEL',s)
        self.assertIn('.putBoolean(PREF_NATIVE_BLUR, enabled)',s)
    def test_legacy_migration_reads_and_new_boolean_wins(self):
        s=(ROOT/'android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java').read_text()
        sig='private boolean isBlurTransitionEnabled()'
        method=sig+s.split(sig,1)[1].split('private boolean isThirdPartyCookiesBlocked()',1)[0]
        code='''public class BlurHarness {
 static final String PREF_NATIVE_BLUR="new", PREF_BLUR_LEVEL="old";
 static class android { static class content { static class SharedPreferences {
 java.util.Map<String,Object> values=new java.util.HashMap<>();
 boolean contains(String k){return values.containsKey(k);}
 boolean getBoolean(String k,boolean d){return (Boolean)values.getOrDefault(k,d);}
 String getString(String k,String d){return (String)values.getOrDefault(k,d);}
 } } }
 static class ContextUtils { static android.content.SharedPreferences prefs=new android.content.SharedPreferences(); static android.content.SharedPreferences getAppSharedPreferences(){return prefs;} }
 '''+method+'''
 static void check(boolean b){if(!b)throw new AssertionError();}
 public static void main(String[]args){
 BlurHarness h=new BlurHarness();check(h.isBlurTransitionEnabled());
 for(String value:new String[]{"default","off","low","medium","high","on","unknown"}){
 ContextUtils.prefs.values.clear();ContextUtils.prefs.values.put("old",value);
 check(h.isBlurTransitionEnabled()==!(value.equals("default")||value.equals("off")));
 ContextUtils.prefs.values.put("new",false);check(!h.isBlurTransitionEnabled());
 ContextUtils.prefs.values.put("new",true);check(h.isBlurTransitionEnabled());
 }
 }
}'''
        if not shutil.which('java'): self.skipTest('Java unavailable')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'BlurHarness.java';p.write_text(code)
            compiler=['javac'] if shutil.which('javac') else ['java','--module','jdk.compiler/com.sun.tools.javac.Main']
            subprocess.run(compiler+[str(p)],check=True,capture_output=True)
            subprocess.run(['java','-cp',d,'BlurHarness'],check=True,capture_output=True)
