from pathlib import Path
import shutil, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/'android/java/org/chromium/chrome/browser/ui/appmenu'
class MenuPreferences(unittest.TestCase):
 @unittest.skipUnless(shutil.which('java'),'Java unavailable')
 def test_actual_store_restart_namespace_migration_and_failure(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory)
   sources={
'android/content/SharedPreferences.java':'''package android.content;
public interface SharedPreferences { boolean contains(String k); String getString(String k,String d); Editor edit(); interface Editor { Editor putString(String k,String v); boolean commit(); } }''',
'android/content/Context.java':'''package android.content;
public abstract class Context { public static final int MODE_PRIVATE=0; public abstract Context getApplicationContext(); public abstract SharedPreferences getSharedPreferences(String n,int m); }''',
'android/os/StrictMode.java':'''package android.os;
public class StrictMode { public static class ThreadPolicy {} public static ThreadPolicy allowThreadDiskWrites(){return new ThreadPolicy();} public static void setThreadPolicy(ThreadPolicy p){} }''',
'Restart.java':'''package org.chromium.chrome.browser.ui.appmenu;
import android.content.*; import java.nio.file.*; import java.util.*;
public class Restart {
 static class Disk implements SharedPreferences {
  Path p; boolean fail; String memory; boolean loaded; Disk(Path p){this.p=p;}
  public boolean contains(String k){return Files.exists(p);}
  public String getString(String k,String d){try{if(!loaded){memory=contains(k)?Files.readString(p):null;loaded=true;}return memory==null?d:memory;}catch(Exception e){throw new RuntimeException(e);}}
  public Editor edit(){return new Editor(){String value; public Editor putString(String k,String v){value=v;return this;} public boolean commit(){memory=value;loaded=true;if(fail)return false;try{Files.createDirectories(p.getParent());Files.writeString(p,value);return true;}catch(Exception e){return false;}}};}
 }
 static class C extends Context {Path root; Context app; Disk disk; C(Path p,Context a){root=p;app=a;}
  public Context getApplicationContext(){return app==null?this:app;}
  public SharedPreferences getSharedPreferences(String n,int m){if(disk==null)disk=new Disk(root.resolve(n));return disk;}
 }
 static void eq(Object a,Object b){if(!a.equals(b))throw new AssertionError(a+" != "+b);}
 static List<String> keys=List.of("one","two","three");
 public static void main(String[] args)throws Exception{
  Path root=Path.of(args[1]); C app=new C(root.resolve("app"),null);C popup=new C(root.resolve("popup"),app);
  if(args[0].equals("legacy")) {popup.getSharedPreferences("sandium.menu.layout.v1",0).edit().putString("layout","legacy").commit();}
  SandiumMenuPreferences store=new SandiumMenuPreferences(popup);
  switch(args[0]){
   case "legacy":eq("legacy",store.load());break;
   case "edit": SandiumMenuState state=SandiumMenuState.load(null,keys,Set.of());state.move("three",0,Set.copyOf(keys));state.hide("two");if(!store.save(state.serialize()))throw new AssertionError();break;
   case "read": SandiumMenuState restored=SandiumMenuState.load(store.load(),keys,Set.of());eq(List.of("three","one"),restored.visibleKeys(Set.copyOf(keys)));eq(List.of("two"),restored.hiddenKeys(Set.copyOf(keys)));break;
   case "isolation":eq("",new SandiumMenuPreferences(new C(root.resolve("separate"),null)).load());break;
   case "stale":popup.getSharedPreferences("sandium.menu.layout.v1",0).edit().putString("layout","stale").commit();if(new SandiumMenuPreferences(popup).load().equals("stale"))throw new AssertionError();break;
   case "fail":String before=store.load();app.disk.fail=true;if(store.save("bad"))throw new AssertionError();eq(before,store.load());break;
  }
 }
}'''}
   paths=[]
   for name,code in sources.items():
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(code);paths.append(str(p))
   subprocess.run(['java','com.sun.tools.javac.Main','-d',str(root),*paths,str(JAVA/'SandiumMenuState.java'),str(JAVA/'SandiumMenuPreferences.java')],capture_output=True,check=True)
   for mode in ['legacy','edit','read','stale','read','isolation','fail','read']:
    subprocess.run(['java','-cp',str(root),'org.chromium.chrome.browser.ui.appmenu.Restart',mode,str(root/'data')],capture_output=True,check=True)
 def test_presenter_reads_and_writes_one_store(self):
  source=(JAVA/'SandiumPagedMenu.java').read_text()
  self.assertIn('mPreferences = new SandiumMenuPreferences(context)',source)
  self.assertIn('SandiumMenuState.load(mPreferences.load()',source)
  self.assertIn('mPreferences.save(value.serialize())',source)
  self.assertNotIn('getSharedPreferences(',source)
 def test_overlay_registers_store(self):
  source=(ROOT/'.circleci/scripts/apply-sandium-paged-menu.py').read_text()
  self.assertIn("'SandiumMenuState', 'SandiumMenuPreferences'",source)
  self.assertEqual(2,source.count("('SandiumMenuPreferences', INTERNAL)"))
if __name__=='__main__': unittest.main()
