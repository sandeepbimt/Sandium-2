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
   case "nativeRead":eq(false,store.isVisible("two",true));eq(true,store.isVisible("one",false));eq(false,store.isVisible("unknown",false));break;
   case "nativeAdd":if(!store.setVisible("two",true))throw new AssertionError();break;
   case "readAdded":SandiumMenuState added=SandiumMenuState.load(store.load(),keys,Set.of("two"));eq(List.of("three","one","two"),added.visibleKeys(Set.copyOf(keys)));break;
   case "nativeRemove":if(!store.setVisible("one",false))throw new AssertionError();break;
   case "readRemoved":SandiumMenuState removed=SandiumMenuState.load(store.load(),List.of("two","three"),Set.of());eq(List.of("three","two"),removed.visibleKeys(Set.of("two","three")));eq(List.of("one"),removed.hiddenKeys(Set.copyOf(keys)));break;
   case "nativeReadd":if(!store.setVisible("one",true))throw new AssertionError();break;
   case "upgrade":List<String> upgraded=List.of("two","one","four","three");SandiumMenuState u=SandiumMenuState.load(store.load(),upgraded,Set.of("two","four"));eq(List.of("three","one","two"),u.visibleKeys(Set.copyOf(upgraded)));eq(List.of("four"),u.hiddenKeys(Set.copyOf(upgraded)));if(!store.save(u.serialize()))throw new AssertionError();break;
   case "nativeNew":if(!store.setVisible("five",false))throw new AssertionError();eq(false,store.isVisible("five",true));break;
   case "nativeFail":String old=store.load();app.disk.fail=true;if(store.setVisible("one",false))throw new AssertionError();eq(old,store.load());break;
   case "invalid":String original=store.load();if(store.setVisible("bad key",false))throw new AssertionError();eq(original,store.load());break;
   case "full":StringBuilder full=new StringBuilder("sandium-menu-v1\\n");for(int i=0;i<512;i++)full.append("item"+i+"\\t0\\n");store.save(full.toString());if(store.setVisible("overflow",true))throw new AssertionError();eq(full.toString(),store.load());break;
   case "corrupt":store.save("corrupt-existing-layout");if(store.setVisible("one",false))throw new AssertionError();eq("corrupt-existing-layout",store.load());break;
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
   for mode in ['legacy','edit','read','stale','read','isolation','fail','read','nativeRead','nativeAdd','readAdded','nativeRemove','readRemoved','nativeReadd','readAdded','upgrade','readAdded','nativeNew','readAdded','nativeFail','readAdded','invalid','full','corrupt']:
    subprocess.run(['java','-cp',str(root),'org.chromium.chrome.browser.ui.appmenu.Restart',mode,str(root/'data')],capture_output=True,check=True)
 def test_presenter_reads_and_writes_one_store(self):
  source=(JAVA/'SandiumPagedMenu.java').read_text()
  self.assertIn('mPreferences = new SandiumMenuPreferences(context)',source)
  self.assertIn('String loadedLayout = mPreferences.load();',source)
  self.assertIn('SandiumMenuState.load(loadedLayout,',source)
  self.assertIn('mPreferences.save(value.serialize())',source)
  self.assertNotIn('getSharedPreferences(',source)
 def test_overlay_registers_store(self):
  source=(ROOT/'.circleci/scripts/apply-sandium-paged-menu.py').read_text()
  self.assertIn("'SandiumMenuState', 'SandiumMenuPreferences'",source)
  self.assertEqual(2,source.count("('SandiumMenuPreferences', PUBLIC)"))
 def test_native_settings_share_store_and_do_not_trust_cached_bundle(self):
  import importlib.util
  spec=importlib.util.spec_from_file_location('menu_patch',ROOT/'.circleci/scripts/apply-sandium-paged-menu.py');patch=importlib.util.module_from_spec(spec);spec.loader.exec_module(patch)
  settings=(ROOT/'tests/fixtures/menu-pinned/BraveCustomizeMenuPreferenceFragment.java').read_text()
  actual=patch.customize_settings(settings)
  self.assertEqual(actual,patch.customize_settings(actual))
  self.assertIn('preference.setPersistent(false)',actual)
  self.assertIn('CustomizeBraveMenu.isVisible(getResources(), menuItem.id)',actual)
  self.assertNotIn('preference.setChecked(menuItem.checked)',actual)
  self.assertNotIn('writeBoolean(preference.getKey()',actual)
  self.assertIn('return new org.chromium.chrome.browser.ui.appmenu.SandiumMenuPreferences(',actual)
  self.assertIn('.setVisible(resourceName, (Boolean) newValue)',actual)
 def test_checkpoint_store_class_ownership_and_settings_reset(self):
  import importlib.util,json
  spec=importlib.util.spec_from_file_location('menu_patch',ROOT/'.circleci/scripts/apply-sandium-paged-menu.py');patch=importlib.util.module_from_spec(spec);spec.loader.exec_module(patch)
  old='android_library("java") {\n  sources = [\n'+''.join('    "java/src/'+patch.PACKAGE+n+'.java",\n' for n in ['SandiumPagedMenu','SandiumMenuState','SandiumMenuPreferences'])+'  ]\n}'
  cleaned=patch.remove_internal_store(old)
  self.assertIn('SandiumPagedMenu.java',cleaned)
  self.assertNotIn('SandiumMenuState.java',cleaned)
  self.assertNotIn('SandiumMenuPreferences.java',cleaned)
  public='android_library("java") {\n  sources = [\n    "java/src/'+patch.PACKAGE+'SandiumMenuMetadata.java",\n  ]\n}'
  normalized=patch.register(public,['SandiumMenuMetadata','SandiumMenuState','SandiumMenuPreferences'])
  self.assertEqual(1,normalized.count('SandiumMenuMetadata.java'))
  self.assertEqual(normalized,patch.register(normalized,['SandiumMenuMetadata','SandiumMenuState','SandiumMenuPreferences']))
  self.assertIn(patch.CUSTOMIZE_SETTINGS,json.loads((ROOT/'.circleci/features/removal-recipe.json').read_text())['core_restore'])
if __name__=='__main__': unittest.main()
