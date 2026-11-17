"""Native wallpaper-gated toolbar paint transforms; no device-pass claim."""
import importlib.util
from pathlib import Path
import shutil,tempfile,unittest,subprocess,re
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('paint',ROOT/'.circleci/scripts/apply-sandium-homepage-surround.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Paint(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  for name,_,_ in m.CHANGES:
   p=self.root/m.BASE/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'tests/fixtures/homepage-surround'/name,p)
 def test_transform_repeat_and_atomic(self):
  result=m.plan(self.root)
  for p,s in result.items():p.write_text(s)
  self.assertEqual(result,m.plan(self.root))
  p=self.root/m.BASE/'TopToolbarOverlayMediator.java';p.write_text('drift')
  before={p:p.read_bytes() for p in self.root.rglob('*.java')}
  with self.assertRaises(RuntimeError):m.plan(self.root)
  self.assertEqual(before,{p:p.read_bytes() for p in before})
 def test_only_paint_lifecycle_no_geometry_or_input(self):
  for name,old,new in m.CHANGES:
   self.assertNotIn('setLayoutParams(',new);self.assertNotIn('setPadding(',new)
   self.assertNotIn('dispatchTouchEvent(',new);self.assertNotIn('getWebContents(',new)
  result=m.plan(self.root)
  phone=result[self.root/m.BASE/'ToolbarPhone.java']
  native=result[self.root/m.BASE/'TopToolbarOverlayMediator.java']
  self.assertIn('adapter.triggerBitmapCapture()',phone)
  self.assertIn('removeSandiumWallpaperBackingObserver',phone)
  self.assertIn('bindSandiumWallpaperPage(null);',native)
  self.assertIn('getUrlBarBackgroundColor(tab, color)',native)
 def test_composes_with_shipping_phone_transforms(self):
  def module(file):
   spec=importlib.util.spec_from_file_location(file,ROOT/'.circleci/scripts'/file)
   value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
  bottom=module('apply-sandium-bottom-toolbar.py');unified=module('apply-sandium-unified-address.py');refine=module('apply-sandium-toolbar-refinements.py')
  p=self.root/m.BASE/'ToolbarPhone.java';source=p.read_text()
  source=bottom.phone(source)
  for fn in [unified.phone,unified.phone_leading_shield,unified.phone_shield_state,unified.responsive,refine.phone,refine.capsule_color]:source=fn(source)
  p.write_text(source)
  result=m.plan(self.root)
  self.assertIn('SANDIUM_ADDRESS_SHADE_V1',result[p]);self.assertIn('SANDIUM_ADDRESS_HEIGHT_V1',result[p])
  for path,text in result.items():path.write_text(text)
  self.assertEqual(result,m.plan(self.root))
 @unittest.skipUnless(shutil.which('java'),'Java unavailable')
 def test_exact_observer_binding_replaces_native_page(self):
  source=m.plan(self.root)[self.root/m.BASE/'ToolbarPhone.java'];start=source.index('    private void bindSandiumWallpaperPage()');opening=source.index('{',start);end=opening+1;depth=1
  while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
  method=source[start:end]
  self.assertNotRegex(method,r'\bTab\s+tab\b')
  harness="""class Binding {
static class Page {int adds,removes;boolean hasSandiumToolbarWallpaperBacking(){return true;}void setSandiumToolbarWallpaperPaintColor(Integer c){}void addSandiumWallpaperBackingObserver(Runnable r){adds++;}void removeSandiumWallpaperBackingObserver(Runnable r){removes++;}}
static class TestTab {Page page;Page getNativePage(){return page;}}
static class Provider {TestTab tab;TestTab getTab(){return tab;}}
Provider provider=new Provider();Provider getToolbarDataProvider(){return provider;}
boolean mSandiumWallpaperBackingReady;Page mSandiumWallpaperPage;final Runnable mSandiumWallpaperObserver=()->{};
METHOD
public static void main(String[] x){Binding b=new Binding();b.bindSandiumWallpaperPage();TestTab t=new TestTab();Page first=new Page(),second=new Page();t.page=first;b.provider.tab=t;b.bindSandiumWallpaperPage();b.bindSandiumWallpaperPage();if(first.adds!=1)throw new AssertionError();t.page=second;b.bindSandiumWallpaperPage();if(first.removes!=1||second.adds!=1)throw new AssertionError();b.provider.tab=null;b.bindSandiumWallpaperPage();if(second.removes!=1||b.mSandiumWallpaperPage!=null)throw new AssertionError();}
}""".replace('METHOD',method)
  p=self.root/'Binding.java';p.write_text(harness)
  subprocess.run(['java','-m','jdk.compiler/com.sun.tools.javac.Main',str(p)],check=True)
  subprocess.run(['java','-cp',str(self.root),'Binding'],check=True)
 @unittest.skipUnless(shutil.which('java'),'Java unavailable')
 def test_exact_live_gate(self):
  source=m.plan(self.root)[self.root/m.BASE/'ToolbarPhone.java'];start=source.index('    private boolean hasSandiumWallpaperSurround(');opening=source.index('{',start);end=opening+1;depth=1
  while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
  method=source[start:end]
  self.assertNotRegex(method,r'\bTab\s+tab\b')
  harness='''class Gate {
static class VisualState {static int NEW_TAB_NORMAL=1,NEW_TAB_SEARCH_ENGINE_NO_LOGO=2;}
static class ControlsPosition {static int BOTTOM=1;}
static class Page {boolean ready=true;boolean hasSandiumToolbarWallpaperBacking(){return ready;}}
static class TestTab {boolean incognito;Page page=new Page();boolean isIncognito(){return incognito;}Page getNativePage(){return page;}}
static class Provider {TestTab tab=new TestTab();TestTab getTab(){return tab;}}
static class Controls {int position=1;int getControlsPosition(){return position;}}
Provider provider=new Provider();Controls mBrowserControlsStateProvider=new Controls();boolean mInLayoutTransition,mIsInLoadingPhaseFromNtpToWebpage,focus;
Provider getToolbarDataProvider(){return provider;}boolean urlHasFocus(){return focus;}
METHOD
static void check(Gate g,boolean want){if(g.hasSandiumWallpaperSurround(2)!=want)throw new AssertionError();}
public static void main(String[] a){Gate early=new Gate();early.provider=null;if(early.hasSandiumWallpaperSurround(0)||early.hasSandiumWallpaperSurround(2))throw new AssertionError("preinitialize");Gate g=new Gate();check(g,true);if(g.hasSandiumWallpaperSurround(0))throw new AssertionError();
g.focus=true;check(g,false);g.focus=false;g.mInLayoutTransition=true;check(g,false);g.mInLayoutTransition=false;g.mIsInLoadingPhaseFromNtpToWebpage=true;check(g,false);g.mIsInLoadingPhaseFromNtpToWebpage=false;
g.provider.tab.page.ready=false;check(g,false);g.provider.tab.page.ready=true;g.provider.tab.incognito=true;check(g,false);g.provider.tab.incognito=false;
g.mBrowserControlsStateProvider.position=0;check(g,false);g.mBrowserControlsStateProvider.position=1;g.provider.tab.page=null;check(g,false);g.provider.tab=null;check(g,false);}
}'''.replace('METHOD',method)
  p=self.root/'Gate.java';p.write_text(harness)
  subprocess.run(['java','-m','jdk.compiler/com.sun.tools.javac.Main',str(p)],check=True)
  subprocess.run(['java','-cp',str(self.root),'Gate'],check=True)
if __name__=='__main__':unittest.main()
