import importlib.util,pathlib,tempfile,subprocess,unittest,gzip
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('home',ROOT/'experiments/single-handoff/home.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Home(unittest.TestCase):
 def test_full_pinned_source_and_identity_guard(self):
  out=m.delegate((m.HERE/'fixtures/NtpSmoothTransitionDelegate.java').read_text())
  self.assertIn('SANDIUM_HOME_HANDOFF_V1',out)
  tab=m.tab(gzip.decompress((m.HERE/'fixtures/TabImpl.java.gz').read_bytes()).decode())
  self.assertIn('mNativePage == page',tab);self.assertIn('getWebContents() == contents',tab)
  for bad in ('setTranslation','setLayoutParams','requestLayout','postInvalidate'):
   self.assertNotIn(bad,out)
  with self.assertRaises(ValueError):m.delegate('unknown')
 def test_bounded_home_web_transaction_roundtrip(self):
  import json
  def load(name):
   spec=importlib.util.spec_from_file_location('test_home_'+name,m.HERE/(name+'.py'));mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
  driver=load('apply');web=load('web')
  native=json.loads(gzip.decompress((ROOT/'tests/fixtures/native-navigation.json.gz').read_bytes()))['native']
  startup=native[web.PATH].replace('            // Native-navigation comparison: use pinned feature defaults.',web.OLD)
  original={m.DELEGATE:(m.HERE/'fixtures/NtpSmoothTransitionDelegate.java').read_text(),m.TAB:gzip.decompress((m.HERE/'fixtures/TabImpl.java.gz').read_bytes()).decode(),web.PATH:startup}
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d)
   for name,text in original.items():
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
   # This three-source fixture tests the bounded home/web component only.
   # Full production planning is covered by navigation_plan and final UI composition.
   with patch.object(driver, 'proposed', side_effect=lambda r: {**web.plan(r), **m.plan(r)}):
    driver.execute(root,True);driver.execute(root,True,True)
   self.assertIn('SANDIUM_HOME_HANDOFF_V1',(root/m.DELEGATE).read_text())
   self.assertIn('SANDIUM_SINGLE_HANDOFF_WEB_V1',(root/web.PATH).read_text())
   driver.execute(root,False)
   for name,text in original.items():self.assertEqual((root/name).read_text(),text)
 def test_actual_tab_async_callback_ownership(self):
  source=m.tab(gzip.decompress((m.HERE/'fixtures/TabImpl.java.gz').read_bytes()).decode())
  begin=source.index('    void handleBackForwardTransitionUiChanged() {')
  end=source.index('\n    // Forwarded from TabWebContentsObserver.',begin)
  method=source[begin:end]
  cb=source.index('final SmoothTransitionDelegate retiringDelegate =')
  ce=max(source.index(token,cb)+len(token) for token in ('retiringDelegate.cancel();','if (!stillOwner) return;'))
  cancel_block=source[cb:ce]
  db=source.index('                    public void onViewDetachedFromWindow(View view) {')
  de=source.index('\n                };',db)
  detach=source[db:de]
  hb=source.index('    private void hideNativePage(boolean notify, @Nullable Runnable postHideTask) {')
  he=source.index('\n    /**',hb)
  hide_method=source[hb:he]
  code='''import java.util.*;
@interface Nullable {}
interface SmoothTransitionDelegate {void start(Runnable r);void cancel();}
class AnimationStage {static final int NONE=0,OTHER=1,WAITING_FOR_EMBEDDER_CONTENT_FOR_COMMITTED_ENTRY=2;}
class View {float alpha=1;List<Runnable> posts=new ArrayList<>();void setAlpha(float x){alpha=x;}float getAlpha(){return alpha;}void post(Runnable r){posts.add(r);}void removeOnAttachStateChangeListener(Object x){}}
class NativePage {View view;boolean isFrozen(){return false;}View getView(){return view;}}
class WebContents {int stage,shown;boolean dead;Runnable onShown;boolean isDestroyed(){return dead;}int getCurrentBackForwardTransitionStage(){return stage;}void onContentForNavigationEntryShown(){shown++;if(onShown!=null)onShown.run();}}
interface TabObserver {void didBackForwardTransitionAnimationChange(Harness h);}
class Delegate implements SmoothTransitionDelegate {Runnable end;int cancellations;public void start(Runnable r){end=r;}public void cancel(){cancellations++;if(end!=null)end.run();}}
class CompositorViewHolder {List<Runnable> queue=new ArrayList<>();void requestRender(Runnable r){queue.add(r);}}
class CompositorViewHolderSupplier {static CompositorViewHolder holder=new CompositorViewHolder();static CompositorViewHolder getValueOrNullFrom(Object x){return holder;}}
public class Harness {
 NativePage mNativePage=new NativePage();View view=new View();WebContents wc=new WebContents();Delegate mNativePageSmoothTransitionDelegate;boolean dead;boolean mIsViewAttachedToWindow=true,mWaitingOnBgColorAfterHidingNativePage;Object mAttachStateChangeListener;int destroyedPages,postHides;int interact;int notify,callerContinued;List<TabObserver> mObservers=new ArrayList<>();
 void destroyNativePageInternal(NativePage p){destroyedPages++;}Harness(){mNativePage.view=view;}NativePage getNativePage(){return mNativePage;}void updateInteractableState(){interact++;}
 boolean isDestroyed(){return dead;}WebContents getWebContents(){return wc;}View getView(){return view;}boolean isNativePage(){return mNativePage!=null;}Object getWindowAndroid(){return null;}void notifyContentChanged(){notify++;}static void assumeNonNull(Object x){}
'''+m.TAB_HELPER+method+detach+hide_method+'\n void cancelOwner(){'+cancel_block+' callerContinued++;}\n'+'''
 static void check(boolean x){if(!x)throw new AssertionError();}
 Runnable hide(){wc.stage=AnimationStage.OTHER;handleBackForwardTransitionUiChanged();return CompositorViewHolderSupplier.holder.queue.remove(0);}
 Runnable cancelled(){view.alpha=0;wc.stage=AnimationStage.WAITING_FOR_EMBEDDER_CONTENT_FOR_COMMITTED_ENTRY;handleBackForwardTransitionUiChanged();return view.posts.remove(0);}
 public static void main(String[]a){
 Harness h=new Harness();Runnable hide=h.hide();hide.run();check(h.view.alpha==0);
 h=new Harness();hide=h.hide();View old=h.view;h.view=new View();hide.run();check(h.view.alpha==1&&old.alpha==1);
 h=new Harness();hide=h.hide();h.wc.stage=AnimationStage.NONE;h.handleBackForwardTransitionUiChanged();hide.run();check(h.view.alpha==1);
 h=new Harness();hide=h.hide();Runnable newer=h.hide();hide.run();check(h.view.alpha==1);newer.run();check(h.view.alpha==0);
 // Cancel reaches WAIT before queued OTHER has hidden anything: alpha remains1.
 h=new Harness();hide=h.hide();h.wc.stage=2;h.handleBackForwardTransitionUiChanged();check(h.view.posts.size()==1);hide.run();check(h.view.alpha==1);Runnable end=h.view.posts.remove(0);end.run();end.run();check(h.wc.shown==1);h.handleBackForwardTransitionUiChanged();check(h.view.posts.isEmpty());
 h=new Harness();end=h.cancelled();h.wc.stage=1;h.handleBackForwardTransitionUiChanged();end.run();check(h.wc.shown==0);CompositorViewHolderSupplier.holder.queue.clear();
 h=new Harness();end=h.cancelled();WebContents oldWc=h.wc;h.wc=new WebContents();end.run();check(oldWc.shown==0&&h.wc.shown==0);
 // Repeated WAIT while delegate pending cannot take cancelled branch or acknowledge early.
 h=new Harness();h.mNativePageSmoothTransitionDelegate=new Delegate();Delegate d=h.mNativePageSmoothTransitionDelegate;h.view.alpha=0;h.wc.stage=2;h.handleBackForwardTransitionUiChanged();h.handleBackForwardTransitionUiChanged();check(h.view.posts.isEmpty()&&h.wc.shown==0&&h.view.alpha==0);d.end.run();d.end.run();check(h.wc.shown==1&&h.notify==1);
 // Real native ack synchronously emits NONE: preserve native notification for same owner.
 h=new Harness();h.mNativePageSmoothTransitionDelegate=new Delegate();d=h.mNativePageSmoothTransitionDelegate;h.wc.stage=2;h.handleBackForwardTransitionUiChanged();final Harness terminal=h;h.wc.onShown=()->{terminal.wc.stage=0;terminal.handleBackForwardTransitionUiChanged();};d.end.run();check(h.wc.shown==1&&h.notify==1);
 h=new Harness();h.mNativePageSmoothTransitionDelegate=new Delegate();d=h.mNativePageSmoothTransitionDelegate;h.wc.stage=2;h.handleBackForwardTransitionUiChanged();final Harness replaced=h;h.wc.onShown=()->{replaced.wc.stage=1;replaced.handleBackForwardTransitionUiChanged();};d.end.run();check(h.wc.shown==1&&h.notify==0);CompositorViewHolderSupplier.holder.queue.clear();
 h=new Harness();h.mNativePageSmoothTransitionDelegate=new Delegate();d=h.mNativePageSmoothTransitionDelegate;h.wc.stage=2;h.handleBackForwardTransitionUiChanged();final Harness destroyedContents=h;h.wc.onShown=()->destroyedContents.wc.dead=true;d.end.run();check(h.wc.shown==1&&h.notify==0);
 // Both detach listener orders: Tab retirement before or after delegate completion.
 for(int order=0;order<2;order++){h=new Harness();h.mNativePageSmoothTransitionDelegate=new Delegate();d=h.mNativePageSmoothTransitionDelegate;h.wc.stage=2;h.handleBackForwardTransitionUiChanged();if(order==0){h.retireSandiumHandoff();d.end.run();}else{d.end.run();h.retireSandiumHandoff();}check(h.wc.shown==1&&!h.mSandiumHandoffPending);h.handleBackForwardTransitionUiChanged();check(h.view.posts.isEmpty()&&h.wc.shown==1);}
 h=new Harness();end=h.cancelled();h.mNativePage=new NativePage();h.retireSandiumHandoff();end.run();check(h.wc.shown==0);
 h=new Harness();end=h.cancelled();h.dead=true;h.retireSandiumHandoff();end.run();check(h.wc.shown==0);
 // Old-owner retirement invokes native callback, which synchronously installs a new owner.
 h=new Harness();h.cancelled();final Harness reentrant=h;h.wc.onShown=()->{reentrant.wc.onShown=null;reentrant.wc.stage=1;reentrant.handleBackForwardTransitionUiChanged();reentrant.wc.stage=2;reentrant.handleBackForwardTransitionUiChanged();};h.retireSandiumHandoff();check(h.wc.shown==1&&h.mSandiumHandoffPending);Runnable fresh=h.view.posts.get(h.view.posts.size()-1);fresh.run();check(h.wc.shown==2&&!h.mSandiumHandoffPending);
 // Actual detach callback must finish attachment bookkeeping after same-owner ack->NONE.
 h=new Harness();h.mNativePageSmoothTransitionDelegate=new Delegate();d=h.mNativePageSmoothTransitionDelegate;h.wc.stage=2;h.handleBackForwardTransitionUiChanged();final Harness detachOwner=h;h.wc.onShown=()->{detachOwner.wc.stage=0;detachOwner.handleBackForwardTransitionUiChanged();};h.onViewDetachedFromWindow(h.view);d.end.run();check(h.wc.shown==1&&!h.mIsViewAttachedToWindow&&h.interact==1);
 // Actual hide method: normal NONE permits requested replacement, supersession does not.
 h=new Harness();h.cancelled();final Harness hidden=h;h.wc.onShown=()->{hidden.wc.stage=0;hidden.handleBackForwardTransitionUiChanged();};h.hideNativePage(true,()->hidden.postHides++);check(h.postHides==1&&h.destroyedPages==1&&h.wc.shown==1);
 h=new Harness();h.cancelled();final Harness superseded=h;h.wc.onShown=()->{superseded.wc.stage=1;superseded.handleBackForwardTransitionUiChanged();};h.hideNativePage(true,()->superseded.postHides++);check(h.postHides==0&&h.destroyedPages==0&&h.wc.shown==1);
 // Execute the production surrounding cancel block, not only the retirement helper.
 h=new Harness();h.mNativePageSmoothTransitionDelegate=new Delegate();Delegate previous=h.mNativePageSmoothTransitionDelegate;h.wc.stage=2;h.handleBackForwardTransitionUiChanged();h.mNativePageSmoothTransitionDelegate=previous;final Harness owner=h;final Delegate replacement=new Delegate();h.wc.onShown=()->{owner.wc.onShown=null;owner.wc.stage=1;owner.handleBackForwardTransitionUiChanged();owner.mNativePageSmoothTransitionDelegate=replacement;};h.cancelOwner();check(h.mNativePageSmoothTransitionDelegate==replacement&&h.callerContinued==0&&h.wc.shown==1);
 // Cached native page returns the SAME delegate for a new operation during acknowledgement.
 h=new Harness();final Delegate cached=new Delegate();h.mNativePageSmoothTransitionDelegate=cached;h.wc.stage=2;h.handleBackForwardTransitionUiChanged();h.mNativePageSmoothTransitionDelegate=cached;final Harness reused=h;h.wc.onShown=()->{reused.wc.onShown=null;reused.wc.stage=1;reused.handleBackForwardTransitionUiChanged();reused.mNativePageSmoothTransitionDelegate=cached;reused.wc.stage=2;reused.handleBackForwardTransitionUiChanged();};h.cancelOwner();check(cached.cancellations==0&&h.callerContinued==0&&h.wc.shown==1&&h.mSandiumHandoffPending);cached.end.run();check(h.wc.shown==2&&!h.mSandiumHandoffPending);

 }
}
'''
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'Harness.java';p.write_text(code)
   r=subprocess.run(['java','--module','jdk.compiler/com.sun.tools.javac.Main','-d',d,str(p)],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
   r=subprocess.run(['java','-cp',d,'Harness'],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
 def test_actual_delegate_compile_lifecycle(self):
  files={
'android/animation/Animator.java':'''package android.animation; public class Animator {public java.util.List<AnimatorListenerAdapter> ls=new java.util.ArrayList<>();boolean running;public void addListener(AnimatorListenerAdapter l){ls.add(l);}public void removeAllListeners(){ls.clear();}public void start(){running=true;}public void cancel(){if(running){running=false;for(var l:new java.util.ArrayList<>(ls))l.onAnimationEnd(this);}}public void end(){running=false;for(var l:new java.util.ArrayList<>(ls))l.onAnimationEnd(this);}public boolean isRunning(){return running;}public void setInterpolator(Object x){}public void setDuration(long x){} }''',
'android/animation/AnimatorListenerAdapter.java':'package android.animation; public class AnimatorListenerAdapter {public void onAnimationEnd(Animator a){}}',
'android/animation/ObjectAnimator.java':'package android.animation; public class ObjectAnimator extends Animator {public static ObjectAnimator ofFloat(Object v,Object p,float a,float b){return new ObjectAnimator();}}',
'android/os/SystemClock.java':'package android.os;public class SystemClock {public static long now;public static long uptimeMillis(){return now;}}',
'android/os/Looper.java':'package android.os;public class Looper {public static Looper getMainLooper(){return new Looper();}}',
'android/os/Handler.java':'package android.os;public class Handler {public static java.util.List<Runnable> tasks=new java.util.ArrayList<>();public Handler(Looper l){}public void postDelayed(Runnable r,long d){tasks.add(r);}public void removeCallbacks(Runnable r){tasks.removeIf(x->x==r);}}',
'android/view/ViewTreeObserver.java':'''package android.view;public class ViewTreeObserver {public interface OnPreDrawListener {boolean onPreDraw();}public java.util.List<OnPreDrawListener> ls=new java.util.ArrayList<>();public void addOnPreDrawListener(OnPreDrawListener l){ls.add(l);}public void removeOnPreDrawListener(OnPreDrawListener l){ls.remove(l);}public boolean isAlive(){return true;}public void draw(){for(var l:new java.util.ArrayList<>(ls))if(!l.onPreDraw())throw new AssertionError();}}''',
'android/view/View.java':'''package android.view;public class View {public static Object ALPHA=new Object();public float alpha=1;public boolean attached=true,layout=true,pending=false;public java.util.List<OnAttachStateChangeListener> ls=new java.util.ArrayList<>();public interface OnAttachStateChangeListener {void onViewAttachedToWindow(View v);void onViewDetachedFromWindow(View v);}public ViewTreeObserver tree=new ViewTreeObserver();public void setAlpha(float a){alpha=a;}public boolean isAttachedToWindow(){return attached;}public boolean isLaidOut(){return layout;}public boolean isLayoutRequested(){return pending;}public int getWidth(){return 100;}public int getHeight(){return 200;}public void addOnAttachStateChangeListener(OnAttachStateChangeListener l){ls.add(l);}public void removeOnAttachStateChangeListener(OnAttachStateChangeListener l){ls.remove(l);}public ViewTreeObserver getViewTreeObserver(){return tree;}}''',
'com/google/common/annotations/VisibleForTesting.java':'package com.google.common.annotations;public @interface VisibleForTesting {}',
'org/chromium/build/annotations/NullMarked.java':'package org.chromium.build.annotations;public @interface NullMarked {}',
'org/chromium/build/annotations/Nullable.java':'package org.chromium.build.annotations;public @interface Nullable {}',
'org/chromium/build/NullUtil.java':'package org.chromium.build;public class NullUtil {public static void assumeNonNull(Object x){}}',
'org/chromium/base/Callback.java':'package org.chromium.base;public interface Callback<T>{void onResult(T x);}',
'org/chromium/base/TimeUtils.java':'package org.chromium.base;public class TimeUtils {public static long currentTimeMillis(){return 1;}}',
'org/chromium/base/supplier/NonNullObservableSupplier.java':'package org.chromium.base.supplier;public interface NonNullObservableSupplier<T>{void addSyncObserverAndPostIfNonNull(org.chromium.base.Callback<T> c);void removeObserver(org.chromium.base.Callback<T> c);}',
'org/chromium/chrome/browser/back_press/BackPressMetrics.java':'package org.chromium.chrome.browser.back_press;public class BackPressMetrics {public static int MAX_FALLBACK_DELAY_NTP_SMOOTH_TRANSITION=300;public static void recordNTPSmoothTransitionMethod(boolean b){}public static void recordNTPFeedRestorationDuration(long v){}}',
'org/chromium/chrome/browser/feed/FeedSurfaceProvider.java':'package org.chromium.chrome.browser.feed;public interface FeedSurfaceProvider {class RestoringState {public static final int NO_STATE_TO_RESTORE=0,RESTORED=1,WAITING_TO_RESTORE=2;}}',
'org/chromium/chrome/browser/ui/native_page/NativePage.java':'package org.chromium.chrome.browser.ui.native_page;public interface NativePage {interface SmoothTransitionDelegate {void prepare();void start(Runnable r);void cancel();}}',
'org/chromium/ui/interpolators/Interpolators.java':'package org.chromium.ui.interpolators;public class Interpolators {public static Object FAST_OUT_SLOW_IN_INTERPOLATOR=new Object();}',
'org/chromium/chrome/browser/ntp/NtpSmoothTransitionDelegate.java':m.delegate((m.HERE/'fixtures/NtpSmoothTransitionDelegate.java').read_text()),
'Harness.java':'''import android.view.*;import android.os.*;import org.chromium.base.*;import org.chromium.base.supplier.*;import org.chromium.chrome.browser.ntp.*;
public class Harness {static int ends;static void check(boolean x){if(!x)throw new AssertionError();}static class Supplier implements NonNullObservableSupplier<Integer>{java.util.List<Callback<Integer>> ls=new java.util.ArrayList<>();public void addSyncObserverAndPostIfNonNull(Callback<Integer> c){ls.add(c);}public void removeObserver(Callback<Integer> c){ls.remove(c);}void ready(){for(var c:new java.util.ArrayList<>(ls))c.onResult(0);}}
static void clean(View v){check(v.ls.isEmpty()&&v.tree.ls.isEmpty()&&Handler.tasks.isEmpty());}
public static void main(String[]x){View v=new View();Supplier s=new Supplier();var d=new NtpSmoothTransitionDelegate(v,s);d.prepare();d.start(()->ends++);s.ready();check(!d.getAnimatorForTesting().isRunning());v.pending=true;v.tree.draw();check(!d.getAnimatorForTesting().isRunning());v.pending=false;v.tree.draw();check(d.getAnimatorForTesting().isRunning());d.getAnimatorForTesting().end();check(ends==1&&v.alpha==1);clean(v);d.cancel();check(ends==1);
d.prepare();d.start(()->ends++);Runnable oldTimeout=Handler.tasks.get(0);Callback<Integer> stale=s.ls.get(s.ls.size()-1);var oldAnimator=d.getAnimatorForTesting();d.prepare();check(ends==2);d.start(()->ends++);stale.onResult(0);v.tree.draw();check(!d.getAnimatorForTesting().isRunning());oldAnimator.end();oldTimeout.run();check(ends==2);Handler.tasks.get(0).run();check(ends==3&&v.alpha==1);clean(v);
d.prepare();d.start(()->ends++);s.ready();v.attached=false;for(var l:new java.util.ArrayList<>(v.ls))l.onViewDetachedFromWindow(v);check(ends==4);clean(v);
d.prepare();d.start(()->ends++);s.ready();check(v.tree.ls.isEmpty());v.attached=true;for(var l:new java.util.ArrayList<>(v.ls))l.onViewAttachedToWindow(v);v.tree.draw();check(d.getAnimatorForTesting().isRunning());d.cancel();check(ends==5);clean(v);
d.prepare();d.start(()->d.start(()->ends++));d.start(()->ends++);check(ends==6);check(Handler.tasks.size()==1);s.ready();v.tree.draw();d.getAnimatorForTesting().end();check(ends==7);clean(v);
d.prepare();d.start(()->ends++);s.ready();SystemClock.now+=301;v.tree.draw();check(ends==8&&!d.getAnimatorForTesting().isRunning());clean(v);
}}
'''}
  with tempfile.TemporaryDirectory() as d:
   paths=[]
   for name,text in files.items():
    p=pathlib.Path(d)/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text);paths.append(str(p))
   r=subprocess.run(['java','--module','jdk.compiler/com.sun.tools.javac.Main','-d',d]+paths,text=True,capture_output=True);self.assertEqual(r.returncode,0,r.stderr)
   r=subprocess.run(['java','-cp',d,'Harness'],text=True,capture_output=True);self.assertEqual(r.returncode,0,r.stderr)
if __name__=='__main__':unittest.main()
