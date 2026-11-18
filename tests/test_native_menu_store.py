"""Android-store API test doubles, not device/SharedPreferences implementation validation."""
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/'sandium/menu/java/org/chromium/chrome/browser/ui/appmenu'
class NativeMenuStoreTest(unittest.TestCase):
    def test_application_scope_background_commit_failure(self):
        sources={
'android/os/Looper.java':'''package android.os; public class Looper {
 public static boolean main; private static final Looper MAIN=new Looper();
 public static Looper getMainLooper(){return MAIN;} public static Looper myLooper(){return main?MAIN:null;}}
''',
'android/content/SharedPreferences.java':'''package android.content; public interface SharedPreferences {
 String getString(String key,String fallback); Editor edit(); interface Editor {
 Editor putString(String key,String value); boolean commit(); }}''',
'android/content/Context.java':'''package android.content; public abstract class Context {
 public static final int MODE_PRIVATE=0; public abstract Context getApplicationContext();
 public abstract SharedPreferences getSharedPreferences(String file,int mode); }''',
'org/chromium/chrome/browser/ui/appmenu/StoreTest.java':'''package org.chromium.chrome.browser.ui.appmenu;
import android.content.*;import android.os.Looper;
public class StoreTest {
 static class Prefs implements SharedPreferences { String value=""; boolean fail;
 public String getString(String k,String f){return value;} public Editor edit(){return new Editor(){
 String pending;public Editor putString(String k,String v){pending=v;return this;}
 public boolean commit(){value=pending;return !fail;}};}}
 static class C extends Context { final Prefs p; final C app; C(Prefs p,C app){this.p=p;this.app=app;}
 public Context getApplicationContext(){return app==null?this:app;}
 public SharedPreferences getSharedPreferences(String f,int mode){
 if(!f.equals("raws.menu.layout.v1"))throw new AssertionError();return p;}}
 static void check(boolean b){if(!b)throw new AssertionError();}
 public static void main(String[] args){Prefs prefs=new Prefs();C app=new C(prefs,null);
 RawSMenuStore one=new RawSMenuStore(new C(new Prefs(),app));
 check(one.write("saved"));check(new RawSMenuStore(app).read().equals("saved"));
 prefs.fail=true;check(!one.write("lost"));check(one.read().equals("saved"));
 Looper.main=true;try{one.write("ui");throw new AssertionError();}catch(IllegalStateException expected){}
 check(one.read().equals("saved"));}
}'''}
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);paths=[]
            for name,content in sources.items():
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content);paths.append(str(p))
            subprocess.run(['java','com.sun.tools.javac.Main','-Xlint:all','-Werror','-d',temp,*paths,
                            str(JAVA/'RawSMenuModel.java'),str(JAVA/'RawSMenuStore.java')],check=True)
            subprocess.run(['java','-cp',temp,'org.chromium.chrome.browser.ui.appmenu.StoreTest'],check=True)
