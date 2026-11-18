"""Compile exact native reveal helper with controlled Android collaborators.
Host logic evidence only, not device geometry verification.
"""
import importlib.util,pathlib,subprocess,tempfile,shutil,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location('reveal',ROOT/'experiments/navigation-diagnostics/apply-native-reveal.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
class Reveal(unittest.TestCase):
 def test_pinned_composition_replay(self):
  s=(ROOT/'tests/fixtures/back-controls/NewTabPage.java').read_text();out=m.transform(s)
  self.assertEqual(m.transform(out),out)
  self.assertIn('delegate.prepare();',out);self.assertIn('delegate.cancel();',out)
  self.assertIn('final SandiumRevealProbe probe = mSandiumRevealProbe;',out)
  with self.assertRaises(ValueError):m.transform(s.replace(m.ANCHOR,'drift'))
 def test_home_back_composition_and_reset_ownership(self):
  import json
  src=(ROOT/'tests/fixtures/back-controls/NewTabPage.java').read_text()
  for patch in json.loads((ROOT/'.circleci/features/homepage-surround/backing.json').read_text()):
   if patch['path']==m.PATH:
    self.assertEqual(src.count(patch['old']),1);src=src.replace(patch['old'],patch['new'],1)
  spec=importlib.util.spec_from_file_location('controls',ROOT/'.circleci/scripts/apply-sandium-back-controls.py');controls=importlib.util.module_from_spec(spec);spec.loader.exec_module(controls)
  for path,old,new in controls.CHANGES:
   if path==m.PATH:self.assertEqual(src.count(old),1);src=src.replace(old,new,1)
  out=m.transform(src);self.assertEqual(m.transform(out),out)
  self.assertIn('sandiumRestoringState(',out);self.assertIn('getSandiumForegroundView()',out)
  recipe=json.loads((ROOT/'.circleci/features/removal-recipe.json').read_text());self.assertIn(m.PATH,recipe['chromium_restore'])
 def test_no_layout_side_effect_or_content(self):
  for bad in ('requestLayout(', 'invalidate(', 'getUrl(', 'getTitle(', 'setAlpha(', 'setTranslation', 'setLayoutParams('):self.assertNotIn(bad,m.HELPER)
 def test_compiled_lifetime(self):
  sources={
 'android/os/SystemClock.java':'package android.os;public class SystemClock {public static long now;public static long uptimeMillis(){return now;}}',
 'android/os/Looper.java':'package android.os; public class Looper {static final Looper L=new Looper();public static Looper myLooper(){return L;}public static Looper getMainLooper(){return L;}}',
 'android/os/Handler.java':'package android.os; public class Handler {public static java.util.ArrayList<Runnable> tasks=new java.util.ArrayList<>();public Handler(Looper l){}public void postDelayed(Runnable r,long ms){if(ms!=500)throw new AssertionError();tasks.add(r);}public void removeCallbacks(Runnable r){tasks.remove(r);}}',
 'android/view/ViewTreeObserver.java':'''package android.view;public class ViewTreeObserver {
 public interface OnPreDrawListener{boolean onPreDraw();}public java.util.ArrayList<OnPreDrawListener> listeners=new java.util.ArrayList<>();public void addOnPreDrawListener(OnPreDrawListener l){listeners.add(l);}public void removeOnPreDrawListener(OnPreDrawListener l){listeners.remove(l);}public boolean isAlive(){return true;}public void draw(){for(var l:new java.util.ArrayList<>(listeners))if(!l.onPreDraw())throw new AssertionError();}}''',
 'android/view/View.java':'''package android.view;public class View {
 public interface OnAttachStateChangeListener{void onViewAttachedToWindow(View v);void onViewDetachedFromWindow(View v);}
 public java.util.ArrayList<OnAttachStateChangeListener> listeners=new java.util.ArrayList<>();public ViewTreeObserver tree=new ViewTreeObserver();public boolean attached=true;
 public void addOnAttachStateChangeListener(OnAttachStateChangeListener l){listeners.add(l);}public void removeOnAttachStateChangeListener(OnAttachStateChangeListener l){listeners.remove(l);}public ViewTreeObserver getViewTreeObserver(){return tree;}public boolean isAttachedToWindow(){return attached;}public void getLocationInWindow(int[] p){p[0]=7;p[1]=-48;}public Object getLayoutParams(){return new ViewGroup.MarginLayoutParams();}public int getWidth(){return 1080;}public int getHeight(){return 2234;}public float getTranslationX(){return 0;}public float getTranslationY(){return 0;}public float getAlpha(){return .5f;}public int getScrollX(){return 0;}public int getScrollY(){return 0;}}''',
 'android/view/ViewGroup.java':'package android.view;public class ViewGroup extends View {public static class MarginLayoutParams{public int topMargin=4,bottomMargin=8;}}',
 'Harness.java':'''import android.view.*;
@interface Nullable {}
class Tab {View v;View getView(){return v;}}
class FeedSurfaceCoordinator {View inner=new View();boolean hasSandiumWallpaperRoot(){return true;}View getSandiumForegroundView(){return inner;}}
interface SmoothTransitionDelegate {void prepare();void start(Runnable r);void cancel();}
class NtpSmoothTransitionDelegate implements SmoothTransitionDelegate {Runnable end;public void prepare(){}public void start(Runnable r){end=r;}public void cancel(){if(end!=null)end.run();}}
class Controls {int getContentOffset(){return 0;}int getTopControlsHeight(){return 0;}int getTopControlOffset(){return 0;}int getBottomControlsHeight(){return 144;}int getBottomControlOffset(){return 0;}int getControlsPosition(){return 1;}}
public class Harness {
 NtpSmoothTransitionDelegate mSmoothTransitionDelegate=new NtpSmoothTransitionDelegate();
 Tab mTab=new Tab();View root=new View();Object mFeedSurfaceProvider=new FeedSurfaceCoordinator();Controls mBrowserControlsStateProvider=new Controls();View getView(){return root;}
'''+m.HELPER+'\n SmoothTransitionDelegate enable(){\n'+m.WRAPPER+'\n}\n'+'''
 static long epoch=1;static int stage;static int rows,frames;static boolean fail;
 static void check(boolean v){if(!v)throw new AssertionError();}
 static SandiumRevealObserver sink=new SandiumRevealObserver(){public long epoch(Tab t){return epoch;}public void record(Tab t,long e,boolean c,double[] v){if(fail)throw new RuntimeException();check(e==epoch);check(v.length==(c?10:16));stage=(int)v[1];rows++;if(!c&&v[1]==2&&v[3]==0)frames++;}};
 static Harness create(){Harness h=new Harness();h.mTab.v=h.root;h.beginSandiumReveal();return h;}
 static void clean(Harness h){check(h.root.tree.listeners.isEmpty());check(h.root.listeners.isEmpty());check(android.os.Handler.tasks.isEmpty());}
 public static void main(String[]a){
 setSandiumRevealObserver(sink);
 Harness actual=new Harness();actual.mTab.v=actual.root;var wrapper=actual.enable();wrapper.prepare();check(actual.root.tree.listeners.isEmpty());wrapper.start(()->check(stage==3));actual.mSmoothTransitionDelegate.end.run();check(stage==8);actual.root.tree.draw();check(stage==9);clean(actual);rows=0;frames=0;
 epoch=0;Harness h=create();check(rows==0);clean(h);
 epoch=1;h=create();check(rows==3);for(int i=0;i<30;i++)h.root.tree.draw();check(frames==15);check(!h.root.tree.listeners.isEmpty());h.mSandiumRevealProbe.afterReveal();h.root.tree.draw();check(frames==16);clean(h);
 h=create();int old=rows;epoch=2;h.root.tree.draw();check(rows==old);clean(h);
 h=create();h.stopSandiumReveal(4);clean(h);
 h=create();h.root.attached=false;for(var l:new java.util.ArrayList<>(h.root.listeners))l.onViewDetachedFromWindow(h.root);clean(h);
 h=create();android.os.Handler.tasks.get(0).run();clean(h);
 h=create();android.os.SystemClock.now+=501;h.root.tree.draw();check(stage==5);clean(h);
 h=create();android.os.SystemClock.now+=501;h.mSandiumRevealProbe.sample(3);check(stage==5);old=rows;h.mSandiumRevealProbe.afterReveal();check(rows==old);clean(h);
 h=create();fail=true;h.root.tree.draw();clean(h);fail=false;
 h=create();var probe=h.mSandiumRevealProbe;h.stopSandiumReveal(4);old=rows;probe.sample(3);check(rows==old);clean(h);
 }
}'''}
  with tempfile.TemporaryDirectory() as d:
   paths=[]
   for name,s in sources.items():p=pathlib.Path(d)/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s);paths.append(str(p))
   compiler=['javac'] if shutil.which('javac') else ['java','--module','jdk.compiler/com.sun.tools.javac.Main']
   p=subprocess.run(compiler+paths,text=True,capture_output=True);self.assertEqual(p.returncode,0,p.stderr)
   p=subprocess.run(['java','-cp',d,'Harness'],text=True,capture_output=True);self.assertEqual(p.returncode,0,p.stderr)
