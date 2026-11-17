import importlib.util,pathlib,tempfile,subprocess,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('c',ROOT/'apply-capture.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Tests(unittest.TestCase):
 def test_pinned_and_replay(self):
  source=(ROOT.parent/'capture-origin/NativePageBitmapCapturer.java').read_text();out=m.transform(source);self.assertEqual(m.transform(out),out);self.assertNotIn('getUrl',m.HELPER)
 def test_actual_helper_java(self):
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d);(p/'android/os').mkdir(parents=True)
   (p/'android/os/Looper.java').write_text('package android.os;public class Looper {static Looper MAIN=new Looper();public static boolean ui=true;public static Looper myLooper(){return ui?MAIN:null;}public static Looper getMainLooper(){return MAIN;}}')
   (p/'Harness.java').write_text('''import java.lang.annotation.*;
@Target(ElementType.TYPE_USE)@interface Nullable{}
class Matrix{void getValues(float[]v){v[0]=v[4]=v[8]=1;}}
class View{int y;View(int y){this.y=y;}void getLocationInWindow(int[]v){v[1]=y;}int getWidth(){return 720;}int getHeight(){return 1400;}boolean isAttachedToWindow(){return true;}int getScrollY(){return 0;}Matrix getMatrix(){return new Matrix();}}
class Page{int getHeightOverlappedWithTopControls(){return 0;}}
class Delegate{View getContainerView(){return new View(112);}}
class Contents{Delegate getViewAndroidDelegate(){return new Delegate();}}
class Tab{View root=new View(0);View getView(){return root;}Page getNativePage(){return new Page();}Contents getWebContents(){return new Contents();}}
public class Harness {'''+m.HELPER+'''static int count;static boolean enabled;static boolean fail;
public static void main(String[]a){Tab t=new Tab();setSandiumOriginObserver(new SandiumOriginObserver(){public boolean isEnabled(Tab tab){return enabled;}public void record(Tab tab,double[]v){if(v.length!=16||v[5]!=112)throw new AssertionError();count++;if(fail)throw new RuntimeException();}public void matrix(Tab tab,double[]v){if(v.length!=11)throw new AssertionError();count++;}});sandiumCaptureOrigin(t,2,0);if(count!=0)throw new AssertionError();enabled=true;sandiumCaptureOrigin(t,2,0);if(count!=3)throw new AssertionError();android.os.Looper.ui=false;sandiumCaptureOrigin(t,1,0);if(count!=3)throw new AssertionError();android.os.Looper.ui=true;fail=true;sandiumCaptureOrigin(t,3,0);if(count!=4)throw new AssertionError();setSandiumOriginObserver(null);sandiumCaptureOrigin(t,2,0);if(count!=4)throw new AssertionError();}}
''')
   subprocess.run(['java','--module','jdk.compiler/com.sun.tools.javac.Main','-d',d]+[str(x) for x in p.rglob('*.java')],check=True);subprocess.run(['java','-cp',d,'Harness'],check=True)
if __name__=='__main__':unittest.main()
