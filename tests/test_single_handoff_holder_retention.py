"""Compile actual dormant holder methods; Android collaborators are explicit doubles."""
import gzip,json,importlib.util,pathlib,tempfile,subprocess,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];HERE=ROOT/'experiments/single-handoff'
s=importlib.util.spec_from_file_location('retention',HERE/'holder_retention.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Retention(unittest.TestCase):
 def fixture(self):return json.loads(gzip.decompress((HERE/'fixtures/native-holder.json.gz').read_bytes()))['files'][m.PATH]['source']
 def test_full_source(self):
  out=m.transform(self.fixture());self.assertEqual(m.transform(out),out)
  self.assertNotIn('addView(retained',out);self.assertIn('if (!show && mSandiumRetained',out)
  with self.assertRaises(ValueError):m.transform(out.replace(' + 500;', ' + 501;',1))
 def test_release_reservation_negative_mutation(self):
  original=m.METHODS
  try:
   m.METHODS=original.replace('mSandiumReleaseDepth != 0 || ', '')
   with self.assertRaises(AssertionError) as caught:self.test_actual_holder_lifetime()
   self.assertIn('java.lang.AssertionError',str(caught.exception))
  finally:m.METHODS=original
 def test_actual_holder_lifetime(self):
  transformed=m.transform(self.fixture())
  hooks=''
  for signature,original in (
   ('public boolean dispatchTouchEvent(MotionEvent e)', '        assert e != null'),
   ('public boolean dispatchKeyEvent(KeyEvent event)', '        // If mSceneOverlay'),
   ('public boolean dispatchDragEvent(DragEvent e)', '        if (e.getAction()'),
   ('public boolean dispatchGenericMotionEvent(MotionEvent e)', '        if (mLayoutManager'),
   ('public boolean dispatchHoverEvent(MotionEvent e)', '        if (mNodeProvider')):
   a=transformed.index('    '+signature+' {')
   # Match original body start AFTER inserted hook, using original source prefix.
   old=self.fixture();start=old.index('    '+signature+' {')+len('    '+signature+' {')
   native_prefix=old[start:].lstrip('\n').splitlines()[0]
   b=transformed.index(native_prefix,a+len('    '+signature+' {'))
   hooks+=transformed[a:b]+'        nativeInputs++; return false;\n    }\n'
  files={
'android/view/MotionEvent.java':'package android.view;public class MotionEvent {public static final int ACTION_UP=1,ACTION_CANCEL=3;int action;public MotionEvent(int a){action=a;}public int getActionMasked(){return action;}}',
'android/view/DragEvent.java':'package android.view;public class DragEvent {public static final int ACTION_DRAG_ENDED=4;int action;public DragEvent(int a){action=a;}public int getAction(){return action;}}',
'android/view/KeyEvent.java':'package android.view;public class KeyEvent {public static final int ACTION_UP=1,KEYCODE_BACK=4,KEYCODE_ESCAPE=111;int action,key;public KeyEvent(int a,int k){action=a;key=k;}public int getAction(){return action;}public int getKeyCode(){return key;}}',
'android/graphics/Canvas.java':'package android.graphics;public class Canvas {}',
'android/os/SystemClock.java':'package android.os;public class SystemClock {public static long now;public static long uptimeMillis(){return now;}}',
'android/view/View.java':'''package android.view;public class View {public static final int VISIBLE=0,IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS=4;public Object parent;public int x,y,w=300,h=600,a11y=1;public boolean layout;public View focus;public Runnable mutate,focusMutation;public int clears;public Object getParent(){return parent;}public int getVisibility(){return 0;}public float getAlpha(){return 1f;}public Object getAnimation(){return null;}public boolean hasTransientState(){return false;}public void getLocationInWindow(int[]x){x[0]=this.x;x[1]=y;}public int getLeft(){return x;}public int getTop(){return y;}public int getWidth(){return w;}public int getHeight(){return h;}public boolean isLayoutRequested(){return layout;}public View findFocus(){return focus;}public boolean hasFocus(){return focus!=null;}public void clearFocus(){clears++;focus=null;if(focusMutation!=null){Runnable r=focusMutation;focusMutation=null;r.run();}}public int getImportantForAccessibility(){return a11y;}public void setImportantForAccessibility(int n){a11y=n;if(mutate!=null){Runnable r=mutate;mutate=null;r.run();}}}''',
'android/view/ViewGroup.java':'''package android.view;public class ViewGroup extends View {public static final int FOCUS_BLOCK_DESCENDANTS=5;public int df=2;public int getDescendantFocusability(){return df;}public void setDescendantFocusability(int n){df=n;}}''',
'org/chromium/chrome/browser/tab/Tab.java':'''package org.chromium.chrome.browser.tab;public class Tab {public android.view.View active;public android.view.View getView(){return active;}public Object page=new Object(),contents=new Object();public Object getNativePage(){return page;}public Object getWebContents(){return contents;}}''',
'org/chromium/chrome/browser/tab/NativePageHandoffOffer.java':'''package org.chromium.chrome.browser.tab;import android.view.View;public class NativePageHandoffOffer {public Claim c;public NativePageHandoffOffer(Claim x){c=x;}public Claim claim(Tab t,View v){if(c==null||c.t!=t||c.v!=v)return null;Claim r=c;c=null;return r;}public static class Claim {public Tab t;public View v;public Object p,w;public boolean valid=true;public int closes;public Runnable cleanup;public Claim(Tab t,View v,Object p){this.t=t;this.v=v;this.p=p;w=t.contents;}public Tab tab(){return t;}public View view(){if(closes!=0)throw new IllegalStateException();return v;}public Object contents(){return w;}public Object page(){return p;}public boolean isValid(){return valid&&closes==0;}public void close(){if(closes++!=0)throw new AssertionError();if(cleanup!=null)cleanup.run();}}}''',
'Harness.java':'''import java.util.*;import android.view.*;import org.chromium.chrome.browser.tab.*;
@interface Nullable {} class Base extends ViewGroup {public void onWindowFocusChanged(boolean x){}protected void dispatchDraw(android.graphics.Canvas c){}}
class Compositor extends View {boolean accept=true;int starts,cancels;java.util.function.Consumer<Boolean> completion;boolean beginSandiumNativeHandoff(long n,Tab t,Object w,Object l,java.util.function.BooleanSupplier gate,java.util.function.Consumer<Boolean> done){starts++;completion=done;return accept;}void cancelSandiumNativeHandoff(long n){cancels++;if(completion!=null){var c=completion;completion=null;c.accept(false);}}}
public class Harness extends Base {int nativeInputs;View mView,mUrlBar;Tab mTabVisible;Compositor mCompositorView=new Compositor();Object mLayoutManager=new Object();boolean mInTouch,mInGesture,mContentViewScrolling,mIsKeyboardShowing,safe=true,attached=true,window=true,mContentOverlayVisiblity=true;Runnable mSandiumUnsafeCallback,acquisitionMutation,focusMutation,policyMutation;List<View> children=new ArrayList<>();List<Runnable> timers=new ArrayList<>();boolean isAttachedToWindow(){return attached;}boolean hasWindowFocus(){return window;}boolean isShown(){return true;}boolean isSandiumNativeHandoffUiSafe(){if(policyMutation!=null){Runnable r=policyMutation;policyMutation=null;r.run();}return safe;}int getChildCount(){return children.size();}View getChildAt(int i){return children.get(i);}boolean postDelayed(Runnable r,long ms){if(ms<0||ms>500)throw new AssertionError();timers.add(r);return true;}void removeCallbacks(Runnable r){timers.remove(r);}void removeView(View v){children.remove(v);v.parent=null;}
'''+m.FIELDS+m.METHODS+hooks+'''
static void check(boolean b){if(!b)throw new AssertionError();}
NativePageHandoffOffer.Claim begin(){Tab t=new Tab();ViewGroup v=new ViewGroup();v.mutate=acquisitionMutation;v.focusMutation=focusMutation;acquisitionMutation=null;focusMutation=null;v.parent=this;mView=v;mTabVisible=t;children.add(mCompositorView);children.add(v);Object p=t.page;t.page=null;var c=new NativePageHandoffOffer.Claim(t,v,p);offerSandiumNativeHome(t,new NativePageHandoffOffer(c));return c;}
void destination(){mView=new View();mTabVisible.active=mView;mView.parent=this;children.add(1,mView);layout=true;startSandiumNativeHome();check(mCompositorView.starts==0);layout=false;dispatchDraw(new android.graphics.Canvas());}
public static void main(String[]args){
 Harness h=new Harness();var c=h.begin();check(h.mSandiumRetained==c&&c.v.parent==h);check(c.v.a11y==4);h.destination();check(h.mCompositorView.starts==1);h.mCompositorView.completion.accept(true);check(c.closes==1&&c.v.parent==null&&h.timers.isEmpty());check(c.v.a11y==1&&((ViewGroup)c.v).df==2);h.releaseSandiumNativeHome(1);check(c.closes==1);
 h=new Harness();c=h.begin();Runnable old=h.timers.get(0);h.destination();h.releaseSandiumNativeHome(1);h.children.clear();var next=h.begin();check(h.mSandiumRetained==next);old.run();check(next.closes==0&&h.mSandiumRetained==next);h.releaseSandiumNativeHome(h.mSandiumRetainedToken);
 h=new Harness();c=h.begin();h.destination();android.os.SystemClock.now=501;check(!h.sandiumRetainedEligible(1));h.dispatchDraw(new android.graphics.Canvas());check(c.closes==1);android.os.SystemClock.now=0;
 h=new Harness();c=h.begin();h.destination();c.v.y=4;h.dispatchDraw(new android.graphics.Canvas());check(c.closes==1);
 h=new Harness();c=h.begin();h.mCompositorView.accept=false;h.destination();check(c.closes==1);
 h=new Harness();c=h.begin();h.destination();c.t.page=c.p;h.releaseSandiumNativeHome(1);check(c.v.parent==h&&c.closes==1&&c.v.a11y==1);
 h=new Harness();h.safe=false;c=h.begin();check(h.mSandiumRetained==null&&c.closes==0);
 h=new Harness();c=h.begin();h.destination();h.safe=false;h.mSandiumUnsafeCallback.run();check(c.closes==1);
 h=new Harness();c=h.begin();h.destination();check(h.dispatchTouchEvent(new MotionEvent(0)));check(c.closes==1);check(h.dispatchTouchEvent(new MotionEvent(2)));check(h.dispatchTouchEvent(new MotionEvent(1)));check(!h.dispatchTouchEvent(new MotionEvent(0))&&h.nativeInputs==1);
 for(int key:new int[]{4,111}){h=new Harness();c=h.begin();h.destination();check(!h.dispatchKeyEvent(new KeyEvent(0,key)));check(c.closes==1);check(!h.dispatchKeyEvent(new KeyEvent(1,key)));check(h.nativeInputs==2&&h.mSandiumConsumeKeys.isEmpty());}
 h=new Harness();c=h.begin();h.destination();check(h.dispatchKeyEvent(new KeyEvent(0,66)));check(h.dispatchKeyEvent(new KeyEvent(1,66)));check(h.nativeInputs==0&&h.mSandiumConsumeKeys.isEmpty());
 h=new Harness();c=h.begin();h.destination();check(h.dispatchDragEvent(new DragEvent(1)));check(h.dispatchDragEvent(new DragEvent(3)));check(h.dispatchDragEvent(new DragEvent(4)));check(!h.dispatchDragEvent(new DragEvent(1))&&h.nativeInputs==1);
 h=new Harness();c=h.begin();h.destination();check(h.dispatchGenericMotionEvent(new MotionEvent(2))&&c.closes==1);
 h=new Harness();c=h.begin();h.destination();check(h.dispatchHoverEvent(new MotionEvent(2))&&c.closes==1);
 for(boolean useFocus:new boolean[]{false,true}) {
  Harness owner=new Harness();NativePageHandoffOffer.Claim[] replacement={null};
  Runnable reenter=()->{var previous=owner.mSandiumRetained;previous.t.page=previous.p;owner.releaseSandiumNativeHome(owner.mSandiumRetainedToken);previous.t.page=null;replacement[0]=new NativePageHandoffOffer.Claim(previous.t,previous.v,previous.p);owner.offerSandiumNativeHome(previous.t,new NativePageHandoffOffer(replacement[0]));};
  if(useFocus)owner.focusMutation=reenter;else owner.acquisitionMutation=reenter;
  var oldClaim=owner.begin();check(oldClaim.closes==1);check(owner.mSandiumRetained==replacement[0]&&replacement[0].closes==0);check(owner.timers.size()==1);check(replacement[0].v.a11y==4);check(replacement[0].v.clears==(useFocus?2:1));owner.releaseSandiumNativeHome(owner.mSandiumRetainedToken);check(replacement[0].closes==1);
 }
 h=new Harness();c=h.begin();h.destination();View overlay=new View();h.children.add(overlay);h.dispatchDraw(new android.graphics.Canvas());check(c.closes==1);
 h=new Harness();c=h.begin();h.destination();h.mTabVisible.active=new View();h.dispatchDraw(new android.graphics.Canvas());check(c.closes==1);
 Harness policyOwner=new Harness();var policyClaim=policyOwner.begin();policyOwner.destination();policyOwner.policyMutation=()->policyOwner.releaseSandiumNativeHome(policyOwner.mSandiumRetainedToken);check(!policyOwner.sandiumRetainedEligible(1));check(policyClaim.closes==1);
 for(boolean reretire:new boolean[]{false,true}) {
  Harness releasing=new Harness();var retiring=releasing.begin();releasing.destination();NativePageHandoffOffer.Claim[] nested={null};
  retiring.v.mutate=()->{retiring.t.page=retiring.p;releasing.children.remove(releasing.mView);releasing.mView=retiring.v;retiring.t.active=retiring.v;if(reretire){retiring.t.page=null;nested[0]=new NativePageHandoffOffer.Claim(retiring.t,retiring.v,retiring.p);releasing.offerSandiumNativeHome(retiring.t,new NativePageHandoffOffer(nested[0]));check(releasing.mSandiumRetained==null);}};
  releasing.releaseSandiumNativeHome(1);check(retiring.closes==1&&retiring.v.a11y==1&&((ViewGroup)retiring.v).df==2);check(releasing.mSandiumReleaseDepth==0);check(releasing.mSandiumRetained==null);check(retiring.v.parent==(reretire?null:releasing));
 }
 System.out.println("HOLDER_LIFETIME=PASS");}}
'''}
  with tempfile.TemporaryDirectory() as d:
   paths=[]
   for p,v in files.items():
    q=pathlib.Path(d)/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(v);paths.append(str(q))
   r=subprocess.run(['java','--module','jdk.compiler/com.sun.tools.javac.Main','-d',d]+paths,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
   r=subprocess.run(['java','-cp',d,'Harness'],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr);self.assertIn('HOLDER_LIFETIME=PASS',r.stdout)
