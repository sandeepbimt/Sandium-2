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
        # Minimal Android storage double; compile and execute the actual generated block.
        prefs = r'''package android.content;
import java.util.*;
public class SharedPreferences {
 public Map<String,Object> values=new HashMap<>();
 public boolean contains(String k){return values.containsKey(k);}
 public boolean getBoolean(String k,boolean d){return (Boolean)values.getOrDefault(k,d);}
 public String getString(String k,String d){return (String)values.getOrDefault(k,d);}
 public Editor edit(){return new Editor();}
 public class Editor {public Editor putBoolean(String k,boolean v){values.put(k,v);return this;} public void apply(){}}
}'''
        source = r'''import java.util.*;
class ContextUtils {
 static android.content.SharedPreferences p=new android.content.SharedPreferences();
 static android.content.SharedPreferences getAppSharedPreferences(){return p;}
}
class CommandLine {
 static CommandLine c=new CommandLine(); Map<String,String> values=new HashMap<>();
 static CommandLine getInstance(){return c;}
 String getSwitchValue(String k,String v){return values.getOrDefault(k,v);}
 void appendSwitchWithValue(String k,String v){values.put(k,v);}
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
 static void check(Boolean saved,String legacy,boolean dim,boolean wantOn){
  String f="AndroidNavigationBlurTransitionAnimation",d="SandiumNavigationTransitionDim";
  ContextUtils.p.values.clear();
  if(saved!=null)ContextUtils.p.values.put("sandium_page_transition_blur_enabled",saved);
  if(legacy!=null)ContextUtils.p.values.put("sandium_page_transition_blur_level",legacy);
  ContextUtils.p.values.put("sandium_page_transition_darken",dim);
  CommandLine.c.values.clear();
  CommandLine.c.values.put("enable-features","Other:foo/bar,"+f+":sigma/9,"+d+"<Trial,"+f);
  CommandLine.c.values.put("disable-features","Disabled<Trial,"+f+"<Trial,"+d+":x/y");
  activate();
  String enabled="Other:foo/bar"+(wantOn?","+f:"")+(wantOn&&dim?","+d:"");
  String disabled="Disabled<Trial"+(!wantOn?","+f:"")+(!(wantOn&&dim)?","+d:"");
  if(!enabled.equals(CommandLine.c.values.get("enable-features")))throw new AssertionError(CommandLine.c.values);
  if(!disabled.equals(CommandLine.c.values.get("disable-features")))throw new AssertionError(CommandLine.c.values);
  if(!Boolean.valueOf(wantOn).equals(ContextUtils.p.values.get("sandium_page_transition_blur_enabled")))throw new AssertionError("migration");
  Map<String,String> before=new HashMap<>(CommandLine.c.values); activate();
  if(!before.equals(CommandLine.c.values))throw new AssertionError("not idempotent");
 }
 public static void main(String[]args){
  check(null,null,false,true);check(null,"default",true,false);check(null,"off",false,false);
  for(String v:new String[]{"low","medium","high"})check(null,v,true,true);
  check(false,"high",true,false);check(true,"default",true,true);check(true,null,false,true);
 }
}'''
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'Harness.java';p.write_text(source)
            storage=Path(d)/'android/content/SharedPreferences.java'
            storage.parent.mkdir(parents=True);storage.write_text(prefs)
            subprocess.run(['java','--module','jdk.compiler/com.sun.tools.javac.Main','-d',d,str(storage),str(p)],check=True,capture_output=True)
            subprocess.run(['java','-cp',d,'Harness'],check=True,capture_output=True)

    def test_saved_custom_strength_is_not_reintroduced(self):
        self.assertIn('"sandium_page_transition_blur_enabled"', w.NEW)
        for token in ('nav-animation-blur-sigma/', 'nav-animation-fade-hold-duration-ms/', 'nav-animation-fade-out-duration-ms/'):
            self.assertNotIn(token,w.NEW)

    def test_no_second_transition_owner_or_timing_policy(self):
        self.assertIn('appendSwitchWithValue(switchName, cleaned.toString())',w.NEW)
        self.assertEqual(w.NEW.count('getSandiumFeatureName(trimmed)'),1)
        for token in ('PaintHolding','postDelayed(', 'SurfaceLayer', 'Bitmap', '350', 'DidFirst', 'setAlpha'):
            self.assertNotIn(token,w.NEW)

if __name__ == '__main__': unittest.main()
