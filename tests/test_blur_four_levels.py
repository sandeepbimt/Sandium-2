from pathlib import Path
import importlib.util,runpy,tempfile,subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
def load(n):
 s=importlib.util.spec_from_file_location(n,ROOT/'experiments/single-handoff'/f'{n}.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=load('blur_levels');native=load('native_blur');web=load('web')
class FourLevels(unittest.TestCase):
 def test_migration_and_command_line_executable(self):
  startup=m.startup(web.NEW+'\n    private static String getSandiumFeatureName(String entry) { return entry.split("[<:]",2)[0]; }')
  body,helpers=startup.split('    private static String getSandiumBlurLevel()',1)
  code='''import java.util.*;
class android {static class content {static class SharedPreferences {
Map<String,Object> values=new HashMap<>();boolean contains(String k){return values.containsKey(k);}boolean getBoolean(String k,boolean d){return (boolean)values.getOrDefault(k,d);}String getString(String k,String d){return (String)values.getOrDefault(k,d);}}}}
class ContextUtils {static android.content.SharedPreferences p=new android.content.SharedPreferences();static android.content.SharedPreferences getAppSharedPreferences(){return p;}}
class CommandLine {static CommandLine c=new CommandLine();Map<String,String>v=new HashMap<>();static CommandLine getInstance(){return c;}String getSwitchValue(String k,String d){return v.getOrDefault(k,d);}void appendSwitchWithValue(String k,String s){v.put(k,s);}}
public class Harness {static void start(){'''+body+'''}
    private static String getSandiumBlurLevel()'''+helpers+'''
public static void main(String[]a){
String choice="sandium_page_transition_blur_choice",old="sandium_page_transition_blur_enabled";
if(!getSandiumBlurLevel().equals("low"))throw new AssertionError();
for(boolean b:new boolean[]{false,true}){ContextUtils.p.values.put(old,b);if(!getSandiumBlurLevel().equals(b?"low":"off"))throw new AssertionError();}
for(String level:new String[]{"off","low","medium","high"}){ContextUtils.p.values.put(choice,level);ContextUtils.p.values.put("sandium_page_transition_darken",true);CommandLine.c.v.put("enable-features","Keep:param/3,SandiumNavigationTransitionFade:duration-ms/999");CommandLine.c.v.put("disable-features","Other,SandiumNavigationTransitionFade");start();String e=CommandLine.c.v.get("enable-features"),d=CommandLine.c.v.get("disable-features");if(!e.contains("Keep:param/3")||!d.contains("Other")||e.contains("999"))throw new AssertionError();boolean on=!level.equals("off");if(e.contains("AndroidNavigationBlurTransitionAnimation")!=on||e.contains("SandiumNavigationTransitionDim")!=on)throw new AssertionError();String duration=level.equals("medium")?"175":level.equals("high")?"200":"";if(duration.isEmpty()?e.contains("SandiumNavigationTransitionFade"):!e.contains("duration-ms/"+duration))throw new AssertionError(e);String first=e+"|"+d;start();if(!first.equals(CommandLine.c.v.get("enable-features")+"|"+CommandLine.c.v.get("disable-features")))throw new AssertionError();}
}}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'Harness.java';p.write_text(code);subprocess.run(['java','com.sun.tools.javac.Main','-d',d,str(p)],check=True);subprocess.run(['java','-cp',d,'Harness'],check=True)
 def test_only_reveal_duration_changed_native_safety_unchanged(self):
  before=native.dim_cc(native.fixture(native.CC));after=m.native(before)
  for signature,end in [('void BlurTransitionAnimationManager::OnBlurHoldTimerExpired()', 'void BlurTransitionAnimationManager::OnDetachCompositor()'),('case AnimationState::kFadeToFallbackColor: {','case AnimationState::kBlurShown:')]:
   self.assertEqual(before.split(signature,1)[1].split(end,1)[0],after.split(signature,1)[1].split(end,1)[0])
  self.assertIn('fallback_opacity > 0.0f',after)
  self.assertEqual(before.count('IgnoreInputEvents'),after.count('IgnoreInputEvents'))
  self.assertIn('std::clamp(kSandiumRevealDurationMs.Get(), 150, 200)',after)
 def test_duration_branch_executable(self):
  function='static base::TimeDelta GetSandiumRevealDuration'+m.NATIVE.split('static base::TimeDelta GetSandiumRevealDuration',1)[1]
  code='#include <algorithm>\n#include <cassert>\nnamespace base {using TimeDelta=int;int Milliseconds(int x){return x;}struct FeatureList {static bool enabled;static bool IsEnabled(int){return enabled;}};bool FeatureList::enabled=false;}\nint GetBlurFadeOutDuration(){return 150;}int kSandiumNavigationTransitionFade=0;struct Param {int value=150;int Get(){return value;}} kSandiumRevealDurationMs;\n'+function+'int main(){for(int ms:{175,200}){kSandiumRevealDurationMs.value=ms;base::FeatureList::enabled=false;assert(GetSandiumRevealDuration(true,0)==150);base::FeatureList::enabled=true;assert(GetSandiumRevealDuration(true,0)==ms);assert(GetSandiumRevealDuration(false,0)==150);assert(GetSandiumRevealDuration(true,0.01f)==150);}kSandiumRevealDurationMs.value=999;assert(GetSandiumRevealDuration(true,0)==200);kSandiumRevealDurationMs.value=-1;assert(GetSandiumRevealDuration(true,0)==150);}\n'
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'duration.cc';p.write_text(code)
   subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror',str(p),'-o',d+'/duration'],check=True)
   subprocess.run([d+'/duration'],check=True)
 def test_settings_real_marker_composition(self):
  b=runpy.run_path(str(ROOT/'.circleci/scripts/apply-sandium-blur-transition.py'));f=runpy.run_path(str(ROOT/'.circleci/scripts/apply-sandium-page-transition-full.py'))
  s='\n'.join(b[k] for k in ['JAVA_PREF_BLOCK','JAVA_HELPER_BLOCK','JAVA_CHANGE_BLOCK','JAVA_INIT_BLOCK'])
  s=s.replace(b['JAVA_INIT_END'],f['JAVA_DARKEN_INIT_BLOCK']+b['JAVA_INIT_END'])+f['JAVA_DARKEN_CHANGE_BLOCK']
  result=m.settings(native.settings(s))
  for text in ['ListPreference pageTransitionBlur','getSandiumBlurLevel()', '"medium"', '"high"', 'darken.setEnabled(!"off".equals(level))']:self.assertIn(text,result)
  xml=m.xml(native.xml(f['transform_appearance_xml'](b['XML_BLOCK'])))
  self.assertIn('android:key="sandium_page_transition_blur_choice"',xml)
  self.assertIn('android:defaultValue="low"',xml)
  self.assertIn('android:key="sandium_page_transition_darken"',xml)
 def test_welcome_uses_same_migration_and_keeps_center(self):
  s=(ROOT/'android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java').read_text()
  self.assertIn(m.HELPER.strip(),s)
  for name in ('low','medium','high'):self.assertIn('R.string.sandium_welcome_blur_'+name,s)
  self.assertIn('mBlurValue.setGravity(Gravity.CENTER)',s)
  self.assertIn('new LinearLayout.LayoutParams(dp(112), dp(40))',s)
  self.assertIn('mDarkenSwitch.setEnabled(enabled)',s)
  self.assertNotIn('.putBoolean(PREF_DARKEN, enabled',s)
if __name__=='__main__':unittest.main()
