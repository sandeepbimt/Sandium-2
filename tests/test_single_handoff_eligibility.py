"""Actual transformed eligibility methods, compiled with explicit Java doubles."""
import gzip,hashlib,importlib.util,json,pathlib,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('eligibility',ROOT/'experiments/single-handoff/eligibility.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Eligibility(unittest.TestCase):
 def fixtures(self):
  return json.loads(gzip.decompress((ROOT/'experiments/single-handoff/fixtures/static-layout-eligibility.json.gz').read_bytes()))['files']
 def test_full_pinned_transform_replay_and_fail_closed(self):
  for path,item in self.fixtures().items():
   self.assertEqual(hashlib.sha256(item['source'].encode()).hexdigest(),item['sha256'])
   out=m.transform(path,item['source']);self.assertEqual(m.transform(path,out),out)
   self.assertEqual(out.count(m.MARKER),1)
   method=m.DEFAULT if path==m.LAYOUT else m.OVERRIDE
   with self.assertRaises(ValueError):m.transform(path,out.replace(method,method.replace('return false;','return true;',1),1))
  with self.assertRaises(ValueError):m.transform(m.STATIC,'unknown')
  with self.assertRaises(ValueError):m.transform('unknown','')
 def test_actual_method_runtime(self):
  # Extract exact inserted bodies from complete transformed pinned sources.
  transformed={p:m.transform(p,i['source']) for p,i in self.fixtures().items()}
  for path,method in ((m.LAYOUT,m.DEFAULT),(m.STATIC,m.OVERRIDE)):
   self.assertIn(method,transformed[path])
  code='''import java.util.*;
@interface Nullable {}
class SceneLayer {}
class WebContents {boolean dead;boolean isDestroyed(){return dead;}}
class URL {String scheme="https";String getScheme(){return scheme;}}
class Tab {static final int INVALID_TAB_ID=-1;int id=4;boolean dead,hidden,nativePage,bf,sad;WebContents contents=new WebContents();URL url=new URL();int getId(){return id;}boolean isDestroyed(){return dead;}boolean isHidden(){return hidden;}WebContents getWebContents(){return contents;}boolean isNativePage(){return nativePage;}boolean isDisplayingBackForwardAnimation(){return bf;}URL getUrl(){return url;}}
class SadTab {static boolean isShowing(Tab t){return t.sad;}}
class Selector {Tab tab;Tab getCurrentTab(){return tab;}}
class Key<T> {T value;Key(T v){value=v;}}
class LayoutTab {static final Key<Boolean> IS_ACTIVE_LAYOUT=new Key<>(true),CAN_USE_LIVE_TEXTURE=new Key<>(true);static final Key<Integer> TAB_ID=new Key<>(4);static final Key<Float> SCALE=new Key<>(1f),X=new Key<>(0f),Y=new Key<>(0f),RENDER_X=new Key<>(0f),RENDER_Y=new Key<>(0f);}
class Model {<T>T get(Key<T> key){return key.value;}}
class LayoutType {static final int BROWSING=1;}
class Layout {'''+m.DEFAULT+'''}
class StaticLayout extends Layout {SceneLayer mSceneLayer=new SceneLayer();Selector mTabModelSelector=new Selector();Model mModel=new Model();boolean active=true,mIsShowing=true,hiding,showing,animating;int type=1;boolean isActive(){return active;}int getLayoutType(){return type;}boolean isStartingToHide(){return hiding;}boolean isStartingToShow(){return showing;}boolean isRunningAnimations(){return animating;}
'''+m.OVERRIDE+'''}
public class Harness {static void check(boolean x){if(!x)throw new AssertionError();}public static void main(String[]a){StaticLayout l=new StaticLayout();Tab t=new Tab();l.mTabModelSelector.tab=t;WebContents w=t.contents;SceneLayer s=l.mSceneLayer;java.util.function.BooleanSupplier ok=()->l.isSandiumNativeHandoffSceneEligible(t,w,s);check(ok.getAsBoolean());check(!new Layout().isSandiumNativeHandoffSceneEligible(t,w,s));check(!l.isSandiumNativeHandoffSceneEligible(null,w,s));check(!l.isSandiumNativeHandoffSceneEligible(t,null,s));check(!l.isSandiumNativeHandoffSceneEligible(t,w,new SceneLayer()));
l.active=false;check(!ok.getAsBoolean());l.active=true;l.mIsShowing=false;check(!ok.getAsBoolean());l.mIsShowing=true;l.hiding=true;check(!ok.getAsBoolean());l.hiding=false;l.showing=true;check(!ok.getAsBoolean());l.showing=false;l.animating=true;check(!ok.getAsBoolean());l.animating=false;l.type=2;check(!ok.getAsBoolean());l.type=1;
LayoutTab.IS_ACTIVE_LAYOUT.value=false;check(!ok.getAsBoolean());LayoutTab.IS_ACTIVE_LAYOUT.value=true;LayoutTab.CAN_USE_LIVE_TEXTURE.value=false;check(!ok.getAsBoolean());LayoutTab.CAN_USE_LIVE_TEXTURE.value=true;LayoutTab.TAB_ID.value=8;check(!ok.getAsBoolean());LayoutTab.TAB_ID.value=4;
for(Key<Float> k:List.of(LayoutTab.X,LayoutTab.Y,LayoutTab.RENDER_X,LayoutTab.RENDER_Y)){k.value=1f;check(!ok.getAsBoolean());k.value=Float.NaN;check(!ok.getAsBoolean());k.value=0f;}LayoutTab.SCALE.value=.5f;check(!ok.getAsBoolean());LayoutTab.SCALE.value=1f;
l.mTabModelSelector.tab=new Tab();check(!ok.getAsBoolean());l.mTabModelSelector.tab=null;check(!ok.getAsBoolean());l.mTabModelSelector.tab=t;t.contents=new WebContents();check(!ok.getAsBoolean());t.contents=w;w.dead=true;check(!ok.getAsBoolean());w.dead=false;
t.dead=true;check(!ok.getAsBoolean());t.dead=false;t.hidden=true;check(!ok.getAsBoolean());t.hidden=false;t.nativePage=true;check(!ok.getAsBoolean());t.nativePage=false;t.bf=true;check(!ok.getAsBoolean());t.bf=false;t.sad=true;check(!ok.getAsBoolean());t.sad=false;t.url.scheme="chrome-native";check(!ok.getAsBoolean());t.url.scheme="http";check(ok.getAsBoolean());t.id=-1;check(!ok.getAsBoolean());t.id=4;
// Delivery-time recheck uses LIVE selection, not the previous admitted root/tab.
l.mSceneLayer=new SceneLayer();check(!ok.getAsBoolean());l.mSceneLayer=s;check(ok.getAsBoolean());l.mTabModelSelector=null;check(!ok.getAsBoolean());
}}
'''
  with tempfile.TemporaryDirectory() as d:
   p=pathlib.Path(d)/'Harness.java';p.write_text(code)
   r=subprocess.run(['java','--module','jdk.compiler/com.sun.tools.javac.Main','-d',d,str(p)],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
   r=subprocess.run(['java','-cp',d,'Harness'],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
 def test_not_wired_and_no_geometry_mutation(self):
  self.assertNotIn('eligibility',(ROOT/'experiments/single-handoff/apply.py').read_text())
  for mutation in ('setAlpha','setTranslation','requestLayout','mModel.set','loadUrl'):
   self.assertNotIn(mutation,m.OVERRIDE)
if __name__=='__main__':unittest.main()
