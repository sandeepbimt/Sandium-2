"""Actual single-use component + transformed TabImpl ownership path with Java doubles."""
import gzip,json,hashlib,importlib.util,pathlib,tempfile,subprocess,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];HERE=ROOT/'experiments/single-handoff'
s=importlib.util.spec_from_file_location('holder',HERE/'holder.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Offer(unittest.TestCase):
 def fixture(self):return json.loads(gzip.decompress((HERE/'fixtures/native-holder.json.gz').read_bytes()))['files']
 def test_exact_source_and_history_composition(self):
  f=self.fixture()
  for path in (m.TAB,m.OBSERVER,m.NTP):
   self.assertEqual(hashlib.sha256(f[path]['source'].encode()).hexdigest(),f[path]['sha256'])
   out=m.transform(path,f[path]['source']);self.assertEqual(m.transform(path,out),out)
  spec=importlib.util.spec_from_file_location('home',HERE/'home.py');home=importlib.util.module_from_spec(spec);spec.loader.exec_module(home)
  merged=m.transform(m.TAB,home.tab(f[m.TAB]['source']))
  self.assertIn('if (!retireSandiumHandoff()) return;',merged)
  self.assertIn('if (!stillOwner) return;\n',merged)
  self.assertLess(merged.index('mNativePage = null;',merged.index('private void hideNativePage')),merged.index(m.MARKER))
  self.assertEqual(merged.count('hideNativePage(true, null, mSandiumNativeHandoffRevision, mWebContents);'),1)
  with self.assertRaises(ValueError):m.transform(m.TAB,merged.replace(m.OFFER_BLOCK,m.OFFER_BLOCK.replace('offer.closeUnclaimed();','',1)))
 def test_disposal_reservation_negative_mutation(self):
  original=m.transform
  def broken(path,source):
   return original(path,source).replace('        if (mSandiumNativeHandoffReservations.containsKey(nativePage)) return;','')
  try:
   m.transform=broken
   with self.assertRaises(AssertionError) as caught:self.test_actual_offer_and_transformed_retirement()
   self.assertIn('java.lang.AssertionError',str(caught.exception))
  finally:m.transform=original
 def test_actual_offer_and_transformed_retirement(self):
  source=m.transform(m.TAB,self.fixture()[m.TAB]['source'])
  a=source.index('    void showRenderedPage() {');b=source.index('\n    void updateWindowAndroid',a);show=source[a:b]
  a=source.index('    private void hideNativePage(boolean notify, @Nullable Runnable postHideTask) {');b=source.index('\n    /**',a);hide=source[a:b]
  a=source.index('    private void destroyNativePageInternal(@Nullable NativePage nativePage) {');b=source.index('\n    /**',a);destroy=source[a:b]
  files={
   'android/view/View.java':'package android.view; public class View {float alpha=1;public void setAlpha(float a){alpha=a;}public void removeOnAttachStateChangeListener(Object x){}}',
   'org/chromium/build/annotations/Nullable.java':'package org.chromium.build.annotations;import java.lang.annotation.*;@Target({ElementType.TYPE_USE,ElementType.FIELD,ElementType.PARAMETER,ElementType.LOCAL_VARIABLE})public @interface Nullable {}',
   'org/chromium/content_public/browser/WebContents.java':'package org.chromium.content_public.browser;public class WebContents {public boolean dead;public boolean isDestroyed(){return dead;}}',
   'org/chromium/chrome/browser/ui/native_page/NativePage.java':'package org.chromium.chrome.browser.ui.native_page;import android.view.View;public interface NativePage {boolean isFrozen();View getView();void destroy();}',
   'org/chromium/chrome/browser/tab/Tab.java':'package org.chromium.chrome.browser.tab; public interface Tab {}',
   'org/chromium/chrome/browser/tab/TabObserver.java':'package org.chromium.chrome.browser.tab;public interface TabObserver {'+m.OBSERVER_HOOK+'default void onContentChanged(Tab tab) {}}',
  }
  for name in ('NativePageHandoffOffer.java','NativePageHandoffSource.java'):
   path='org/chromium/chrome/browser/tab/'+name;files[path]=(HERE/'components'/path).read_text()
  files['org/chromium/chrome/browser/tab/Harness.java']='''package org.chromium.chrome.browser.tab;
import java.util.*;import android.view.View;import org.chromium.build.annotations.Nullable;import org.chromium.content_public.browser.WebContents;import org.chromium.chrome.browser.ui.native_page.NativePage;
class Page implements NativePage {int destroys;boolean frozen;View view=new View();public boolean isFrozen(){return frozen;}public View getView(){return view;}public void destroy(){destroys++;}}
class Home extends Page implements NativePageHandoffSource {}
class URL {String scheme="https";String getScheme(){return scheme;}}
class Delegate {void cancel(){}}
public class Harness implements Tab {NativePage mNativePage;WebContents mWebContents=new WebContents();Object mSandiumNativeHandoffRevision=new Object(),mAttachStateChangeListener;java.util.IdentityHashMap<NativePage,Object> mSandiumNativeHandoffReservations=new java.util.IdentityHashMap<>();boolean mWaitingOnBgColorAfterHidingNativePage,dead,privateTab;Delegate mNativePageSmoothTransitionDelegate;List<TabObserver> mObservers=new ArrayList<>();URL url=new URL();int notifications,titles;boolean isDestroyed(){return dead;}boolean isIncognito(){return privateTab;}URL getUrl(){return url;}boolean isNativePage(){return mNativePage!=null;}View getView(){return mNativePage==null?null:mNativePage.getView();}static void assumeNonNull(Object x){if(x==null)throw new AssertionError();}void updateTitle(){titles++;}void notifyContentChanged(){notifications++;for(TabObserver o:mObservers)o.onContentChanged(this);}
'''+show+hide+destroy+'''
static void check(boolean x){if(!x)throw new AssertionError();}
public static void main(String[]args)throws Exception {
 Harness h=new Harness();Home home=new Home();h.mNativePage=home;final NativePageHandoffOffer.Claim[] claimed={null};h.mObservers.add(new TabObserver(){public void onNativePageHandoffOffered(Tab t,NativePageHandoffOffer offer){check(((Harness)t).mNativePage==null);claimed[0]=offer.claim(t,home.view);check(offer.claim(t,home.view)==null);}});h.showRenderedPage();check(claimed[0]!=null&&home.destroys==0&&h.notifications==1);claimed[0].close();claimed[0].close();check(home.destroys==1);
 // Generic hides, unsupported pages, incognito, native destinations never offer.
 for(int mode=0;mode<5;mode++){Harness x=new Harness();Page p=mode==1?new Page():new Home();x.mNativePage=p;x.privateTab=mode==2;x.url.scheme=mode==3?"chrome":"https";p.frozen=mode==4;x.mObservers.add(new TabObserver(){public void onNativePageHandoffOffered(Tab t,NativePageHandoffOffer o){throw new AssertionError();}});if(mode==0)x.hideNativePage(true,null);else x.showRenderedPage();check(p.destroys==1);}
 // Unclaimed and exceptions destroy exact retired resource once.
 Harness x=new Harness();Home p=new Home();x.mNativePage=p;x.showRenderedPage();check(p.destroys==1);
 x=new Harness();p=new Home();x.mNativePage=p;x.mObservers.add(new TabObserver(){public void onNativePageHandoffOffered(Tab t,NativePageHandoffOffer o){throw new IllegalStateException();}});try{x.showRenderedPage();throw new AssertionError();}catch(IllegalStateException expected){}check(p.destroys==1);
 // Claim followed by observer failure: ownership remains claimant, not finally.
 x=new Harness();final Home q=new Home();x.mNativePage=q;x.mObservers.add(new TabObserver(){public void onNativePageHandoffOffered(Tab t,NativePageHandoffOffer o){claimed[0]=o.claim(t,q.view);}public void onContentChanged(Tab t){throw new IllegalStateException();}});try{x.showRenderedPage();throw new AssertionError();}catch(IllegalStateException expected){}check(q.destroys==0);claimed[0].close();check(q.destroys==1);
 // Nested notification creates another page/offer; outer offer cannot claim newer target.
 x=new Harness();final Harness nested=x;final Home first=new Home(),second=new Home();x.mNativePage=first;final int[] nesting={0};x.mObservers.add(new TabObserver(){public void onNativePageHandoffOffered(Tab t,NativePageHandoffOffer o){if(nesting[0]++==0){nested.mSandiumNativeHandoffRevision=new Object();nested.mNativePage=second;nested.showRenderedPage();check(o.claim(t,first.view)==null);}else claimed[0]=o.claim(t,second.view);}});x.showRenderedPage();check(first.destroys==1&&second.destroys==0);claimed[0].close();check(second.destroys==1);
 // Reentrant exact page restored active: old retirement must not destroy it.
 x=new Harness();final Harness restored=x;final Home active=new Home();x.mNativePage=active;x.mObservers.add(new TabObserver(){public void onNativePageHandoffOffered(Tab t,NativePageHandoffOffer o){restored.mSandiumNativeHandoffRevision=new Object();restored.mNativePage=active;check(o.claim(t,active.view)==null);}});x.showRenderedPage();check(active.destroys==0&&x.mNativePage==active);
 // Claim validation can reenter offer close; no spent claim is returned.
 final NativePageHandoffOffer[] offer={null};final int[] destroyed={0};Harness tab=new Harness();Home resource=new Home();offer[0]=new NativePageHandoffOffer(tab,resource,resource.view,tab.mWebContents,()->{offer[0].closeUnclaimed();return true;},()->destroyed[0]++);check(offer[0].claim(tab,resource.view)==null&&destroyed[0]==1);
 Harness reserved=new Harness();Home same=new Home();NativePageHandoffOffer.Claim[] held={null};int[] offers={0};reserved.mNativePage=same;reserved.mObservers.add(new TabObserver(){public void onNativePageHandoffOffered(Tab t,NativePageHandoffOffer o){offers[0]++;held[0]=o.claim(reserved,same.view);}});reserved.showRenderedPage();check(offers[0]==1&&reserved.mSandiumNativeHandoffReservations.size()==1);reserved.mNativePage=same;reserved.mSandiumNativeHandoffRevision=new Object();reserved.showRenderedPage();check(offers[0]==1&&same.destroys==0);held[0].close();check(same.destroys==1&&reserved.mSandiumNativeHandoffReservations.isEmpty());held[0].close();check(same.destroys==1);
 Harness reactivated=new Harness();Home reactivatedPage=new Home();NativePageHandoffOffer.Claim[] reactivatedClaim={null};reactivated.mNativePage=reactivatedPage;reactivated.mObservers.add(new TabObserver(){public void onNativePageHandoffOffered(Tab t,NativePageHandoffOffer o){reactivatedClaim[0]=o.claim(reactivated,reactivatedPage.view);}});reactivated.showRenderedPage();reactivated.mNativePage=reactivatedPage;reactivatedClaim[0].close();check(reactivatedPage.destroys==0&&reactivated.mSandiumNativeHandoffReservations.isEmpty());
 System.out.println("EXACT_TAB_OFFER_LIFETIME=PASS");
}}
'''
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d);paths=[]
   for path,text in files.items():p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text);paths.append(str(p))
   r=subprocess.run(['java','--module','jdk.compiler/com.sun.tools.javac.Main','-d',d]+paths,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
   r=subprocess.run(['java','-cp',d,'org.chromium.chrome.browser.tab.Harness'],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
   self.assertIn('EXACT_TAB_OFFER_LIFETIME=PASS',r.stdout)
if __name__=='__main__':unittest.main()
