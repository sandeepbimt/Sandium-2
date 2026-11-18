"""Compile exact injected Java boundary methods, with explicit JNI/View collaborators."""
import pathlib, importlib.util, tempfile, subprocess, unittest, gzip, json, hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
HERE=ROOT/'experiments/single-handoff'
s=importlib.util.spec_from_file_location('java_adapter',HERE/'java_adapter.py');adapter=importlib.util.module_from_spec(s);s.loader.exec_module(adapter)
PREFIX=r'''
import org.chromium.content_public.browser.WebContents;
import org.chromium.chrome.browser.tab.Tab;
@java.lang.annotation.Target({java.lang.annotation.ElementType.TYPE_USE}) @java.lang.annotation.Retention(java.lang.annotation.RetentionPolicy.CLASS) @interface Nullable {} @interface CalledByNative {}
class View {static final int VISIBLE=0;}
class SceneLayer {}
class Layout {boolean eligible=true;Runnable duringQuery;boolean isSandiumNativeHandoffSceneEligible(Tab t,WebContents w,SceneLayer s){if(duringQuery!=null)duringQuery.run();return eligible&&!t.dead&&!w.dead&&t.wc==w;}}
class LayoutProvider {Layout layout=new Layout();Layout getActiveLayout(){return layout;}}
class CompositorViewJni {
 static Native n=new Native();static Native get(){return n;}
 static class Native {boolean accept=true,failBegin,failCancel;int begins,cancels;Runnable duringCancel,duringBegin;
  boolean beginSandiumNativeHandoff(long ptr,long token,WebContents w){begins++;if(duringBegin!=null)duringBegin.run();if(failBegin)throw new IllegalStateException();return accept;}
  void cancelSandiumNativeHandoff(long ptr,long token){cancels++;if(duringCancel!=null)duringCancel.run();if(failCancel)throw new IllegalStateException();}
 }
}
public class Harness {
 long mNativeCompositorView=1;
 boolean mIsDrawPaused,mIsInXr,mIsXrFullSpaceMode,mOverlayVideoEnabled,mSelectionHandlesActive,mHasActiveTouchInterceptors;
 boolean attached=true,focused=true,acceptPost=true;int visibility=View.VISIBLE,renders;java.util.List<Runnable> posts=new java.util.ArrayList<>();boolean post(Runnable r){if(!acceptPost)return false;posts.add(r);return true;}void requestRender(){renders++;}
 boolean isAttachedToWindow(){return attached;}boolean hasWindowFocus(){return focused;}int getVisibility(){return visibility;}
'''
MAIN=r'''
 static void check(boolean value){if(!value)throw new AssertionError();}
 void frame(LayoutProvider p,SceneLayer s){mSandiumFinalizationProvider=p;mSandiumFinalizedScene=s;}
 static class Case {
  Harness h=new Harness();Tab t=new Tab();WebContents w=new WebContents();LayoutProvider p=new LayoutProvider();SceneLayer s=new SceneLayer();int ends;boolean presented;
  Case(){t.wc=w;h.frame(p,s);CompositorViewJni.n=new CompositorViewJni.Native();}
  boolean begin(long token){return h.beginSandiumNativeHandoff(token,t,w,p,()->true,x->{ends++;presented=x;});}
 }
 public static void main(String[]args){
  Case c=new Case();check(c.begin(1));check(c.h.renders==0&&c.h.posts.size()==1);c.h.posts.remove(0).run();check(c.h.renders==1);check(!c.begin(2));check(c.h.getSandiumNativeHandoffScene(1)==c.s);c.h.onSandiumNativeHandoffComplete(1,true);check(c.ends==1&&c.presented);c.h.onSandiumNativeHandoffComplete(1,true);check(c.ends==1);check(!c.begin(1));check(c.begin(2));c.h.onSandiumNativeHandoffComplete(1,true);check(c.ends==1);c.h.cancelSandiumNativeHandoff(2);check(c.ends==2&&!c.presented);
  c=new Case();CompositorViewJni.n.accept=false;check(!c.begin(1)&&c.ends==0);CompositorViewJni.n.accept=true;check(!c.begin(1));check(c.begin(2));c.h.cancelSandiumNativeHandoff(2);
  c=new Case();CompositorViewJni.n.failBegin=true;try{c.begin(1);throw new AssertionError();}catch(IllegalStateException expected){}check(c.ends==0&&c.h.mSandiumHandoffToken==0);
  c=new Case();check(c.begin(1));c.p.layout=new Layout();c.p.layout.eligible=false;c.h.onSandiumNativeHandoffComplete(1,true);check(c.ends==1&&!c.presented);
  c=new Case();check(c.begin(1));c.h.frame(new LayoutProvider(),c.s);check(c.h.getSandiumNativeHandoffScene(1)==null);c.h.cancelSandiumNativeHandoff(1);
  c=new Case();check(c.begin(1));c.h.mIsDrawPaused=true;check(c.h.getSandiumNativeHandoffScene(1)==null);c.h.mIsDrawPaused=false;c.h.mIsInXr=true;check(c.h.getSandiumNativeHandoffScene(1)==null);c.h.mIsInXr=false;c.h.mIsXrFullSpaceMode=true;check(c.h.getSandiumNativeHandoffScene(1)==null);c.h.mIsXrFullSpaceMode=false;c.h.mOverlayVideoEnabled=true;check(c.h.getSandiumNativeHandoffScene(1)==null);c.h.mOverlayVideoEnabled=false;c.h.mSelectionHandlesActive=true;check(c.h.getSandiumNativeHandoffScene(1)==null);c.h.mSelectionHandlesActive=false;c.h.mHasActiveTouchInterceptors=true;check(c.h.getSandiumNativeHandoffScene(1)==null);c.h.mHasActiveTouchInterceptors=false;c.h.attached=false;check(c.h.getSandiumNativeHandoffScene(1)==null);c.h.attached=true;c.h.focused=false;check(c.h.getSandiumNativeHandoffScene(1)==null);c.h.focused=true;c.h.visibility=4;check(c.h.getSandiumNativeHandoffScene(1)==null);c.h.cancelSandiumNativeHandoff(1);
  c=new Case();check(c.begin(1));c.h.abandonSandiumNativeHandoffForShutdown();c.h.onSandiumNativeHandoffComplete(1,true);check(c.ends==0&&!c.begin(2));check(c.h.mSandiumHandoffCompletion==null&&c.h.mSandiumFinalizedScene==null);
  c=new Case();check(c.begin(1));Case current=c;CompositorViewJni.n.duringCancel=()->current.h.onSandiumNativeHandoffComplete(1,true);c.h.cancelSandiumNativeHandoff(1);check(c.ends==1&&!c.presented);
  c=new Case();check(c.begin(1));CompositorViewJni.n.failCancel=true;try{c.h.cancelSandiumNativeHandoff(1);throw new AssertionError();}catch(IllegalStateException expected){}check(c.ends==1&&c.h.mSandiumHandoffToken==0);
  // Final flags are rechecked AFTER the arbitrary holder policy runs.
  c=new Case();Case paused=c;
  check(c.h.beginSandiumNativeHandoff(1,c.t,c.w,c.p,()->{paused.h.mIsDrawPaused=true;return true;},x->{paused.ends++;paused.presented=x;}));
  c.h.onSandiumNativeHandoffComplete(1,true);check(c.ends==1&&!c.presented);
  c=new Case();Case focus=c;
  check(c.h.beginSandiumNativeHandoff(1,c.t,c.w,c.p,()->{focus.h.focused=false;return true;},x->{focus.ends++;focus.presented=x;}));
  c.h.onSandiumNativeHandoffComplete(1,true);check(c.ends==1&&!c.presented);
  c=new Case();Case layoutPaused=c;c.p.layout.duringQuery=()->layoutPaused.h.mIsDrawPaused=true;check(c.begin(1));c.h.onSandiumNativeHandoffComplete(1,true);check(c.ends==1&&!c.presented);
  c=new Case();Case changedProvider=c;
  check(c.h.beginSandiumNativeHandoff(1,c.t,c.w,c.p,()->{changedProvider.h.frame(new LayoutProvider(),changedProvider.s);return true;},x->{changedProvider.ends++;changedProvider.presented=x;}));
  c.h.onSandiumNativeHandoffComplete(1,true);check(c.ends==1&&!c.presented);
  c=new Case();Case violate=c;CompositorViewJni.n.duringBegin=()->violate.h.onSandiumNativeHandoffComplete(1,true);
  check(!c.begin(1)&&c.ends==0&&c.h.mSandiumHandoffToken==0&&CompositorViewJni.n.cancels==1);
  c=new Case();Case cancelBegin=c;CompositorViewJni.n.duringBegin=()->cancelBegin.h.cancelSandiumNativeHandoff(1);
  check(!c.begin(1)&&c.ends==0&&c.h.mSandiumHandoffToken==0);
  c=new Case();c.h.acceptPost=false;check(!c.begin(1)&&c.ends==0&&c.h.mSandiumHandoffToken==0);
  c=new Case();org.chromium.base.ThreadUtils.ui=false;try{c.begin(1);throw new AssertionError();}catch(IllegalStateException expected){}finally{org.chromium.base.ThreadUtils.ui=true;}check(c.h.mSandiumHandoffToken==0);
  // Holder policy can revoke and replace while a delivered success is being checked.
  c=new Case();Case reentrant=c;
  check(c.h.beginSandiumNativeHandoff(1,c.t,c.w,c.p,()->{reentrant.h.cancelSandiumNativeHandoff(1);check(reentrant.begin(2));return true;},x->{reentrant.ends++;}));
  c.h.onSandiumNativeHandoffComplete(1,true);check(c.ends==1&&c.h.mSandiumHandoffToken==2);c.h.cancelSandiumNativeHandoff(2);check(c.ends==2);
  c=new Case();check(!c.begin(0)&&!c.begin(-1));c.t.dead=true;check(!c.begin(1));c.t.dead=false;c.w.dead=true;check(!c.begin(1));c.w.dead=false;c.t.wc=new WebContents();check(!c.begin(1));
 }
}
'''
class JavaAdapter(unittest.TestCase):
 def _compile_methods(self, methods=None, success=True):
  with tempfile.TemporaryDirectory() as directory:
   root=pathlib.Path(directory)
   files={
    'org/chromium/content_public/browser/WebContents.java':'package org.chromium.content_public.browser;public class WebContents {public boolean dead;public boolean isDestroyed(){return dead;}}',
    'org/chromium/chrome/browser/tab/Tab.java':'package org.chromium.chrome.browser.tab;import org.chromium.content_public.browser.WebContents;public class Tab {public boolean dead;public WebContents wc;public boolean isDestroyed(){return dead;}public WebContents getWebContents(){return wc;}}',
    'org/chromium/base/ThreadUtils.java':'package org.chromium.base;public class ThreadUtils {public static boolean ui=true;public static void assertOnUiThread(){if(!ui)throw new IllegalStateException();}}',
    'org/chromium/base/Callback.java':'package org.chromium.base;public interface Callback<T>{void onResult(T value);}',
    'Harness.java':PREFIX+adapter.FIELDS+(adapter.METHODS if methods is None else methods)+MAIN}
   paths=[]
   for name,body in files.items():
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body);paths.append(str(p))
   r=subprocess.run(['java','--module','jdk.compiler/com.sun.tools.javac.Main','-Xlint:all','-Werror','-d',str(root),*paths],capture_output=True,text=True)
   self.assertEqual(r.returncode,0,r.stderr)
   result=subprocess.run(['java','-cp',str(root),'Harness'],capture_output=True,text=True)
   if success:self.assertEqual(result.returncode,0,result.stderr)
   else:
    self.assertNotEqual(result.returncode,0);self.assertIn('AssertionError',result.stderr)
 def test_actual_methods(self):
  self._compile_methods()
 def test_reentrant_flags_regression_rejects_old_guard(self):
  mutated=adapter.METHODS.replace('|| !isSandiumNativeHandoffLocallyEligible(token)', '|| token != mSandiumHandoffToken')
  self.assertNotEqual(mutated,adapter.METHODS);self._compile_methods(mutated,False)

 def test_full_pinned_transform(self):
  fixture=json.loads(gzip.decompress((HERE/'fixtures/compositor-view-java.json.gz').read_bytes()))
  self.assertEqual(fixture['pin'],'d331de35ca8ab1358c7a17e4bd41627d55eaef51')
  self.assertEqual(hashlib.sha256(fixture['text'].encode()).hexdigest(),fixture['sha256'])
  out=adapter.transform(fixture['text']);self.assertEqual(adapter.transform(out),out)
  self.assertLess(out.index('mSandiumFinalizedScene = sceneLayer;'),out.index('CompositorViewJni.get().finalizeLayers(mNativeCompositorView);'))
  self.assertIn('public void shutDown() {\n        abandonSandiumNativeHandoffForShutdown();',out)
  with self.assertRaises(ValueError):adapter.transform('unknown')
  with self.assertRaises(ValueError):adapter.transform(out.replace('token <= mSandiumLastHandoffToken','token < mSandiumLastHandoffToken'))
 def test_not_active(self):
  self.assertNotIn("'java_adapter'",(HERE/'apply.py').read_text())
