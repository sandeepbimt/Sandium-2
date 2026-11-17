"""Pinned paint composition plus extracted Java policies; not Android runtime QA."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
paint=load('opaque',ROOT/'.circleci/scripts/opaque-status-paint.py')
scroll=load('scroll',ROOT/'.circleci/scripts/apply-sandium-scroll-status-bar.py')
native=load('native',ROOT/'.circleci/scripts/native-status-geometry.py')
CONTROLLER='chrome/android/java/src/org/chromium/chrome/browser/ui/system/StatusBarColorController.java'
HELPER=scroll.FILES['EdgeToEdgeSystemBarColorHelper.java']
SOURCE={CONTROLLER:(ROOT/'.circleci/tests/fixtures/opaque-status/StatusBarColorController.java').read_text(),HELPER:(ROOT/'.circleci/tests/fixtures/status-bar/EdgeToEdgeSystemBarColorHelper.java').read_text()}
def body(text,start):
 a=text.index('{',text.index(start));i=a+1;depth=1
 while depth:
  depth+=(text[i]=='{')-(text[i]=='}');i+=1
 return text[a:i]
class OpaqueStatus(unittest.TestCase):
 def test_pins_and_repeatable_preserve_unrelated(self):
  pins=json.loads((ROOT/'.circleci/features/opaque-status-paint/provenance.json').read_text())['sha256']
  for name,text in SOURCE.items():
   self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),pins[name])
   once=paint.transform(name,text+'\n// Preserve unrelated Sandium customization.\n')
   self.assertEqual(paint.transform(name,once),once)
   self.assertTrue(once.endswith('// Preserve unrelated Sandium customization.\n'))
 def test_coherent_native_geometry_then_opaque_not_full_native_navigation(self):
  for name,path in scroll.FILES.items():
   original=(ROOT/'.circleci/tests/fixtures/status-bar'/name).read_text()
   changed=scroll.transform(name,original)
   # Pure geometry reversal, explicitly without the old experiment's gradient.
   for old,new in reversed(native.REVERSAL[path]):
    self.assertEqual(changed.count(new),1)
    changed=changed.replace(new,old,1)
   self.assertEqual(changed,original)
   final=paint.transform(path,changed)
   self.assertNotIn('mSandiumScrollUnderStatusBar',final)
   self.assertNotIn('mSandiumTopProtectionHeight',final)
   if path!=HELPER:self.assertEqual(final,original)
  self.assertEqual(len(paint.FILES),2)
  for path in paint.FILES:
   self.assertNotIn('BackForwardTransition',path)
   self.assertNotIn('ToolbarPhone',path)
   self.assertNotIn('NewTabPage',path)
 def test_fail_closed_partial_and_underlap(self):
  with self.assertRaises(RuntimeError):paint.transform(HELPER,scroll.transform('EdgeToEdgeSystemBarColorHelper.java',SOURCE[HELPER]))
  s=paint.transform(HELPER,SOURCE[HELPER]).replace('int inverse = 255 - alpha;','int inverse = 254 - alpha;')
  with self.assertRaises(RuntimeError):paint.transform(HELPER,s)
 def test_painted_rgb_and_native_icon_contrast_same(self):
  s=paint.transform(HELPER,SOURCE[HELPER]);method=body(s,'private void updateStatusBarColor()')
  self.assertIn('delegateHelper.setStatusBarColor(effectiveColor)',method)
  self.assertIn('int windowStatusBarColor = effectiveColor',method)
  self.assertIn('updateStatusBarIconColor(mWindow.getDecorView(), effectiveColor)',method)
  self.assertEqual(method.count('windowStatusBarColor = Color.TRANSPARENT'),1)
  self.assertNotIn('else if (mCanSetTransparentStatusBarWithoutDelegate)',method)
  s=paint.transform(CONTROLLER,SOURCE[CONTROLLER])
  self.assertIn('public void onBackgroundColorChanged(Tab tab, @ColorInt int color)',s)
  self.assertIn('mCurrentTab.getBackgroundColor()',s)
  self.assertIn('/* forceLightIconColor= */ false',s)
  self.assertNotIn('evaluateJavaScript',s)
 def test_actual_java_opacity_and_surface_scope(self):
  helper=body(paint.transform(HELPER,SOURCE[HELPER]),'public static int getSandiumOpaqueStatusColor(')
  c=paint.transform(CONTROLLER,SOURCE[CONTROLLER]);prefix=body(c,'private @ColorInt int calculateBaseStatusBarColor()').replace('@ColorInt', '')
  source='''class StatusPolicyTest {
 static class Color {
  static final int TRANSPARENT=0;
  static int alpha(int c){return c>>>24;} static int red(int c){return(c>>>16)&255;}
  static int green(int c){return(c>>>8)&255;} static int blue(int c){return c&255;}
  static int rgb(int r,int g,int b){return 0xff000000|(r<<16)|(g<<8)|b;}
 }
 static class EdgeToEdgeSystemBarColorHelper { static int getSandiumOpaqueStatusColor(int color)
'''+helper+''' }
 static class Tab {int background; Tab(int color){background=color;} int getBackgroundColor(){return background;}}
 static class LayoutType {static final int BROWSING=1;}
 static class Layout {boolean browsing; boolean isLayoutVisible(int type){return browsing;}}
 static final int DEFAULT_STATUS_BAR_COLOR=-2, UNDEFINED_STATUS_BAR_COLOR=-1;
 static class Provider {int value=UNDEFINED_STATUS_BAR_COLOR; int getBaseStatusBarColor(Tab t){return value;}}
 Provider mStatusBarColorProvider=new Provider();
 static class Window {Object getContext(){return null;}}
 static class TabUiThemeUtil {static int getTabStripBackgroundColor(Object c,boolean i,boolean d,boolean r){return 12345;}}
 static class AppHeaderUtils {static boolean isAppInDesktopWindow(Object d){return false;}}
 static class Theme {int getThemeColorOrFallback(Tab t,int fallback){return fallback;}}
 Window mWindow=new Window(); Theme mTopUiThemeColor=new Theme(); Object mDesktopWindowStateManager;
 boolean mTabStripHiddenOnTablet,mIsIncognitoBranded,mIsTopResumedActivity,mToolbarColorChanged;
 int mToolbarColor=12345,mBackgroundColorForNtp=12345;
 boolean isStandardNtp(){return false;} boolean isBottomBarEnabledAndBottomControls(){return false;}
 int calculateDefaultStatusBarColor(){return 12345;}
 boolean mIsTablet,mIsOmniboxFocused; Layout mLayoutStateProvider; Tab mCurrentTab;
 int calculateBaseStatusBarColor()
'''+prefix+'''
 static void check(boolean condition){if(!condition)throw new AssertionError();}
 public static void main(String[] args){
  check(EdgeToEdgeSystemBarColorHelper.getSandiumOpaqueStatusColor(0)==0xff121212);
  check(EdgeToEdgeSystemBarColorHelper.getSandiumOpaqueStatusColor(0xffffffff)==0xffffffff);
  check(EdgeToEdgeSystemBarColorHelper.getSandiumOpaqueStatusColor(0xff000000)==0xff000000);
  for(int alpha=0;alpha<256;alpha++)for(int red=0;red<256;red+=17){
   int input=(alpha<<24)|(red<<16)|0x0080c0;
   int output=EdgeToEdgeSystemBarColorHelper.getSandiumOpaqueStatusColor(input);
   check(Color.alpha(output)==255);
   check(Color.red(output)==(red*alpha+18*(255-alpha)+127)/255);
  }
  StatusPolicyTest test=new StatusPolicyTest();
  check(test.calculateBaseStatusBarColor()==0xff121212);
  test.mCurrentTab=new Tab(0xffffffff);check(test.calculateBaseStatusBarColor()==0xffffffff);
  test.mCurrentTab=new Tab(0xff252525);check(test.calculateBaseStatusBarColor()==0xff252525);
  test.mIsOmniboxFocused=true;check(test.calculateBaseStatusBarColor()==12345);test.mIsOmniboxFocused=false;
  test.mIsTablet=true;check(test.calculateBaseStatusBarColor()==12345);test.mIsTablet=false;
  test.mLayoutStateProvider=new Layout();check(test.calculateBaseStatusBarColor()==12345);
  test.mLayoutStateProvider.browsing=true;check(test.calculateBaseStatusBarColor()==0xff252525);
  // Exercise the complete production method, not a prefix which bypasses providers.
  test.mStatusBarColorProvider.value=0xffabcdef;
  check(test.calculateBaseStatusBarColor()==0xffabcdef);
  test.mStatusBarColorProvider.value=DEFAULT_STATUS_BAR_COLOR;
  check(test.calculateBaseStatusBarColor()==12345);
  test.mStatusBarColorProvider.value=UNDEFINED_STATUS_BAR_COLOR;
  check(test.calculateBaseStatusBarColor()==0xff252525);
  test.mLayoutStateProvider=null;test.mStatusBarColorProvider.value=0xff123456;
  check(test.calculateBaseStatusBarColor()==0xff123456);
  test.mStatusBarColorProvider.value=DEFAULT_STATUS_BAR_COLOR;
  check(test.calculateBaseStatusBarColor()==12345);
  test.mStatusBarColorProvider.value=UNDEFINED_STATUS_BAR_COLOR;
  check(test.calculateBaseStatusBarColor()==0xff252525);
 }
}'''
  java=Path('/usr/lib/jvm/java-21-openjdk-amd64/bin/java')
  self.assertTrue(java.exists())
  with tempfile.TemporaryDirectory() as temp:
   path=Path(temp)/'StatusPolicyTest.java';path.write_text(source)
   compile_result=subprocess.run([str(java),'-m','jdk.compiler/com.sun.tools.javac.Main','-d',temp,str(path)],capture_output=True,text=True)
   self.assertEqual(compile_result.returncode,0,compile_result.stdout+compile_result.stderr)
   result=subprocess.run([str(java),'-cp',temp,'StatusPolicyTest'],capture_output=True,text=True)
   self.assertEqual(result.returncode,0,result.stdout+result.stderr)
if __name__=='__main__':unittest.main()
