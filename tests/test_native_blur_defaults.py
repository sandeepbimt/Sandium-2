"""Compile exact startup activation; saved Sandium levels cannot affect native params."""
import json,pathlib,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class Defaults(unittest.TestCase):
 def test_activation_without_parameter_overrides(self):
  patches=json.loads((ROOT/'experiments/native-navigation/patches.json').read_text())
  block=next(x['new'] for x in patches if x['path'].endswith('SplitCompatApplication.java'))
  self.assertNotIn('getAppSharedPreferences',block)
  for key in ('nav-animation-blur-sigma/','nav-animation-fade-hold-duration-ms/','nav-animation-fade-out-duration-ms/'):self.assertNotIn(key,block)
  source='''import java.util.*;
class CommandLine {static CommandLine c=new CommandLine();Map<String,String> m=new HashMap<>();static CommandLine getInstance(){return c;}String getSwitchValue(String k,String v){return m.getOrDefault(k,v);}void appendSwitchWithValue(String k,String v){m.put(k,v);}}
public class Harness {
static String getSandiumFeatureName(String e){int a=e.indexOf('<'),b=e.indexOf(':');if(a<0||(b>=0&&b<a))a=b;return a<0?e:e.substring(0,a);}
static boolean containsSandiumFeature(String list,String target){for(String x:list.split(","))if(getSandiumFeatureName(x.trim()).equals(target))return true;return false;}
static void activate(){
'''+block+'''
}
public static void main(String[]a){CommandLine c=CommandLine.c;
 c.m.put("enable-features","OtherFeature:foo/bar,AndroidNavigationBlurTransitionAnimation:nav-animation-blur-sigma/9");activate();String v=c.m.get("enable-features");if(!v.equals("OtherFeature:foo/bar,AndroidNavigationBlurTransitionAnimation"))throw new AssertionError(v);
 activate();if(!v.equals(c.m.get("enable-features")))throw new AssertionError();
 c.m.put("disable-features","AndroidNavigationBlurTransitionAnimation");c.m.put("enable-features","OtherFeature");activate();if(!c.m.get("enable-features").equals("OtherFeature"))throw new AssertionError();
}}
'''
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'Harness.java';p.write_text(source)
   subprocess.run(['java','--module','jdk.compiler/com.sun.tools.javac.Main',str(p)],check=True,capture_output=True)
   subprocess.run(['java','-cp',d,'Harness'],check=True,capture_output=True)
if __name__=='__main__':unittest.main()
