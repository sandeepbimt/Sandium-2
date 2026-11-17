import importlib.util,pathlib,tempfile,unittest,subprocess,shutil
P=pathlib.Path
HERE=P(__file__).parent;ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('origin',HERE/'apply.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
class Tests(unittest.TestCase):
 def test_exact_pinned_roundtrip_and_no_urls(self):
  inputs={a.JAVA:(HERE/'NativePageBitmapCapturer.java').read_text(),a.BLUR:(ROOT/'tests/fixtures/ordinary-transition/blur_transition_animation_manager.cc').read_text(),a.BACK:(ROOT/'tests/fixtures/back-transition'/a.BACK).read_text()}
  for path,fn in [(a.JAVA,a.java),(a.BLUR,a.blur),(a.BACK,a.back)]:
   output=fn(inputs[path]);self.assertEqual(fn(output),output)
   added=output.replace(inputs[path],'')
   self.assertNotIn('getUrl()',a.HELPER);self.assertNotIn('getTitle()',a.HELPER)
  with tempfile.TemporaryDirectory() as d:
   src=P(d)
   for p,t in inputs.items():(src/p).parent.mkdir(parents=True,exist_ok=True);(src/p).write_text(t)
   (src/a.BACK).write_text('bad final anchor');before={p:p.read_bytes() for p in src.rglob('*') if p.is_file()}
   with self.assertRaises(ValueError):a.plan(src)
   self.assertEqual(before,{p:p.read_bytes() for p in src.rglob('*') if p.is_file()})
 @unittest.skipUnless(shutil.which("javac"), "JDK compiler absent: Java execution NOT verified")
 def test_java_numbers_and_null_guards(self):
  with tempfile.TemporaryDirectory() as d:
   p=P(d);(p/'android/util').mkdir(parents=True);(p/'android/os').mkdir(parents=True)
   (p/'android/util/Log.java').write_text('package android.util; public class Log {public static int VERBOSE=2;public static boolean isLoggable(String tag,int level){return true;}public static String last=""; public static int i(String tag,String msg){last=msg;return 0;}}')
   (p/'android/os/SystemClock.java').write_text('package android.os; public class SystemClock {public static long uptimeMillis(){return 99;}}')
   (p/'Harness.java').write_text('''class Matrix {String toShortString(){return "identity";}}
class View {int getScrollY(){return 0;} int getPaddingTop(){return 0;} Matrix getMatrix(){return new Matrix();} int y; boolean attached=true; View(int y){this.y=y;} void getLocationInWindow(int[] xy){xy[1]=y;} float getY(){return y;} int getHeight(){return 1000;} boolean isAttachedToWindow(){return attached;}}
class Native {int getHeightOverlappedWithTopControls(){return 0;}}
class Delegate {View web=new View(112); View getContainerView(){return web;}}
class Web {Delegate d=new Delegate(); Delegate getViewAndroidDelegate(){return d;}}
class Profile {boolean isOffTheRecord(){return false;}}
class Tab {Profile getProfile(){return new Profile();} View root=new View(0);Web web=new Web();View getView(){return root;}Native getNativePage(){return new Native();}Web getWebContents(){return web;}}
public class Harness {'''+a.HELPER+'''public static void main(String[] args){Tab t=new Tab();sandiumTraceOrigin(t,2,0); if(!android.util.Log.last.contains("nativeWindowY=0,webWindowX=0,webWindowY=112"))throw new AssertionError(android.util.Log.last); t.root.attached=false;sandiumTraceOrigin(t,1,56);if(!android.util.Log.last.contains("nativeAttached=false"))throw new AssertionError();String before=android.util.Log.last;t.root=null;sandiumTraceOrigin(t,3,0);if(!before.equals(android.util.Log.last))throw new AssertionError();}}
''')
   subprocess.run(['javac']+[str(x) for x in p.rglob('*.java')],check=True);subprocess.run(['java','-cp',d,'Harness'],check=True)
 def test_layer_probe_compiles_and_does_not_mutate(self):
  with tempfile.TemporaryDirectory() as d:
   p=P(d)/'test.cc'
   p.write_text('''#include <string>
#define TRACE_EVENT_INSTANT(...) ((void)0)
struct Point{float x(){return 0;}float y(){return 112;}};struct Transform{std::string ToString(){return "identity";}};
struct Layer{Layer* p=nullptr;Point position(){return {};}Transform transform(){return {};}Layer* parent(){return p;}};
int main(){Layer root;Layer child;child.p=&root;Layer* first=&child;'''+a.layer_probe('first','Probe')+'''return child.p==&root?0:1;}
''')
   subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror',str(p),'-o',str(p.with_suffix(''))],check=True);subprocess.run([str(p.with_suffix(''))],check=True)
if __name__=='__main__':unittest.main()
