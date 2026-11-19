import importlib.util
from pathlib import Path
import tempfile
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('handoff_web', ROOT/'experiments/single-handoff/web.py')
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)

class WebHandoffTest(unittest.TestCase):
    def test_exact_native_startup_transform_and_idempotence(self):
        original = 'before\n'+w.OLD+'\nafter'
        changed = w.transform(original)
        self.assertEqual(changed, 'before\n'+w.NEW+'\nafter')
        self.assertEqual(w.transform(changed), changed)
    def test_fail_closed(self):
        for source in ('', w.OLD+w.OLD, 'SANDIUM_SINGLE_HANDOFF_WEB_V1', w.NEW+w.NEW):
            with self.assertRaises(ValueError): w.transform(source)
    def test_plan_does_not_write(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/w.PATH
            p.parent.mkdir(parents=True)
            p.write_text(w.OLD)
            self.assertEqual(w.plan(Path(d)), {p:w.NEW})
            self.assertEqual(p.read_text(),w.OLD)
    def test_exact_java_startup_behavior(self):
        source = r'''import java.util.*;
class CommandLine {
 static CommandLine c = new CommandLine();
 Map<String,String> values = new HashMap<>();
 static CommandLine getInstance(){return c;}
 String getSwitchValue(String k,String v){return values.getOrDefault(k,v);}
 void appendSwitchWithValue(String k,String v){values.put(k,v);}
}
class ContextUtils {
 static android.content.SharedPreferences p=new android.content.SharedPreferences();
 static android.content.SharedPreferences getAppSharedPreferences(){return p;}
}
public class Harness {
 static String getSandiumFeatureName(String entry){
  int modifier=entry.indexOf('<'),params=entry.indexOf(':');
  if(modifier<0||(params>=0&&params<modifier))modifier=params;
  return modifier<0?entry:entry.substring(0,modifier);
 }
 static void activate(){
''' + w.NEW + r'''
 }
 static void check(String enabled,String disabled,String wantEnabled,String wantDisabled){
  CommandLine.c.values.clear();
  if(enabled!=null)CommandLine.c.values.put("enable-features",enabled);
  if(disabled!=null)CommandLine.c.values.put("disable-features",disabled);
  activate();
  if(!wantEnabled.equals(CommandLine.c.values.get("enable-features")))throw new AssertionError(CommandLine.c.values);
  if(!wantDisabled.equals(CommandLine.c.values.get("disable-features")))throw new AssertionError(CommandLine.c.values);
  Map<String,String> before=new HashMap<>(CommandLine.c.values);
  activate();
  if(!before.equals(CommandLine.c.values))throw new AssertionError("not idempotent");
 }
 public static void main(String[] args){
  String f="AndroidNavigationBlurTransitionAnimation", dim="SandiumNavigationTransitionDim";
  ContextUtils.p.values.clear();
  check(null,null,f,dim);
  if(!ContextUtils.p.getBoolean("sandium_page_transition_blur_enabled",false))throw new AssertionError("fresh default");
  for(String legacy:new String[]{"default","off","low","medium","high","on","unknown"}){
   ContextUtils.p.values.clear();ContextUtils.p.values.put("sandium_page_transition_blur_level",legacy);
   boolean on=!legacy.equals("default")&&!legacy.equals("off");
   check("Other:foo/bar,"+f+":sigma/9", "Disabled<Trial,"+f+", "+dim,
       "Other:foo/bar"+(on?","+f:""), "Disabled<Trial"+(on?"":","+f)+","+dim);
  }
  ContextUtils.p.values.clear();ContextUtils.p.values.put("sandium_page_transition_blur_enabled",true);
  ContextUtils.p.values.put("sandium_page_transition_blur_level","default");
  ContextUtils.p.values.put("sandium_page_transition_darken",true);
  check(f+"<Trial,"+f+":a/b",f+","+dim,f+","+dim,"");
  ContextUtils.p.values.put("sandium_page_transition_blur_enabled",false);
  check(f+","+dim,"", "",f+","+dim);
 }
}
'''
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'Harness.java'
            p.write_text(source)
            stub=Path(d)/'android/content/SharedPreferences.java'
            stub.parent.mkdir(parents=True)
            stub.write_text("""package android.content;
public class SharedPreferences {
 public java.util.Map<String,Object> values=new java.util.HashMap<>();
 public boolean contains(String k){return values.containsKey(k);}
 public boolean getBoolean(String k,boolean d){return (Boolean)values.getOrDefault(k,d);}
 public String getString(String k,String d){return (String)values.getOrDefault(k,d);}
 public SharedPreferences edit(){return this;}
 public SharedPreferences putBoolean(String k,boolean v){values.put(k,v);return this;}
 public void apply(){}
}""")
            subprocess.run(['java','--module','jdk.compiler/com.sun.tools.javac.Main',str(stub),str(p)],check=True,capture_output=True)
            subprocess.run(['java','-cp',d,'Harness'],check=True,capture_output=True)

    def test_old_strength_timing_are_not_reused(self):
        for token in ('nav-animation-blur-sigma/', 'nav-animation-fade-hold-duration-ms/', 'nav-animation-fade-out-duration-ms/'):
            self.assertNotIn(token, w.NEW)
        self.assertIn('sandium_page_transition_blur_enabled',w.NEW)
        self.assertIn('SandiumNavigationTransitionDim',w.NEW)

    def test_no_second_transition_owner_or_timing_policy(self):
        self.assertEqual(w.NEW.count('getSandiumFeatureName(trimmed)'),1)
        self.assertNotIn('PaintHolding',w.NEW)
        for token in ('postDelayed(', 'SurfaceLayer', 'Bitmap', '350', 'DidFirst', 'setAlpha'):
            self.assertNotIn(token,w.NEW)

if __name__ == '__main__': unittest.main()
