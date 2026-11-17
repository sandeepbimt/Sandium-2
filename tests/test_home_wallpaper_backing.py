import importlib.util, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PKG=ROOT/'tests/fixtures/homepage-backing'
spec=importlib.util.spec_from_file_location('home',ROOT/'.circleci/scripts/apply-sandium-homepage-backing.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Backing(unittest.TestCase):
 def prepare(self,root):
  for p in m.PATCHES:
   f=root/p['path'];f.parent.mkdir(parents=True,exist_ok=True)
   f.write_text((PKG/f.name).read_text())
 def test_plan_replay_and_exact_source_scope(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);self.prepare(r);one=m.plan(r)
   for p,s in one.items():p.write_text(s)
   self.assertEqual(one,m.plan(r))
   self.assertEqual(len(one),6)
   feed=next(v for k,v in one.items() if k.name=='FeedSurfaceCoordinator.java')
   self.assertIn('ViewUtils.captureBitmap(getView(), canvas);',feed)
   self.assertIn('mMediator.onThumbnailCaptured();',feed)
   self.assertIn('mSandiumWallpaperDirty || mMediator.shouldCaptureThumbnail()',feed)
   ntp=next(v for k,v in one.items() if k.name=='NewTabPage.java')
   self.assertIn('getSandiumForegroundView()',ntp)
   self.assertIn('layoutParams.bottomMargin = bottomMargin;',ntp)
 def test_all_anchors_before_write(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);self.prepare(r);p=r/m.PATCHES[-1]['path'];p.write_text('broken')
   before={p:p.read_text() for p in r.rglob('*.java')}
   with self.assertRaises(RuntimeError):m.plan(r)
   self.assertEqual(before,{p:p.read_text() for p in before})
 def test_pinned_preference_registrar_constructor(self):
  source='\n'.join(p['new'] for p in m.PATCHES)
  self.assertNotIn('new org.chromium.components.prefs.PrefChangeRegistrar();',source)
  self.assertNotIn('mSandiumWallpaperPrefObserver.init(',source)
  self.assertIn('new org.chromium.components.prefs.PrefChangeRegistrar(\n                UserPrefs.get(mProfile))',source)
 def test_all_owners_reset_and_pinned_ntp_patch_replayed(self):
  import json
  recipe=json.loads((ROOT/'.circleci/features/removal-recipe.json').read_text())
  paint=json.loads((ROOT/'.circleci/features/homepage-surround/paint.json').read_text())
  paths={p['path'] for p in m.PATCHES}
  paths.update('chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/top/'+p[0] for p in paint)
  for path in paths:
   key='core_restore' if path.startswith('brave/') else 'chromium_restore'
   self.assertIn(path[6:] if path.startswith('brave/') else path,recipe[key])
  self.assertEqual(recipe['chromium_restore_patches']['chrome/android/java/src/org/chromium/chrome/browser/ntp/NewTabPage.java'],'patches/chrome-android-java-src-org-chromium-chrome-browser-ntp-NewTabPage.java.patch')
 def test_bitmap_existing_worker_cancellation_and_dimensions(self):
  worker=(PKG/'FetchWallpaperWorkerTask.java').read_text()
  self.assertIn('NTPImageUtil.getWallpaperBitmap(mNTPImage, mLayoutWidth, mLayoutHeight)',worker)
  self.assertLess(worker.index('if (isCancelled()) return;'),worker.index('mCallback.bgWallpaperRetrieved('))

 def test_shipping_layout_composition(self):
  def module(name,file):
   spec=importlib.util.spec_from_file_location(name,ROOT/'.circleci/scripts'/file);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v);return v
  consumer=module('homeconsumer','apply-sandium-ntp-consumers.py')
  shortcuts=module('homeshortcuts','apply-sandium-home-shortcuts.py')
  branding=module('homebranding','apply-sandium-branding-refresh.py')
  rel='android/java/org/chromium/chrome/browser/ntp/BraveNewTabPageLayout.java'
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);self.prepare(r);p=r/'brave'/rel
   p.write_text((ROOT/'.circleci/features/news-removal/expected'/rel).read_text())
   branding.replace_once(p, "                && mNtpImageGlobal instanceof Wallpaper\n                && getTab() != null\n", "                && mNtpImageGlobal instanceof Wallpaper\n                && ((Wallpaper) mNtpImageGlobal).isSponsored()\n                && getTab() != null\n", 'sponsored-infobar-guard')
   p.write_text(shortcuts.layout(consumer.transform(rel,p.read_text())))
   result=m.plan(r)
   self.assertIn('mSandiumShortcuts',result[p])
   self.assertIn('mSandiumWallpaperCoordinator.setSandiumWallpaperAllowed(',result[p])
   self.assertIn('mSandiumWallpaperPrefObserver.destroy()',result[p])
   for path,text in result.items():path.write_text(text)
   self.assertEqual(result,m.plan(r))

 def test_executed_provider_readiness_capture_and_foreground(self):
  import subprocess,shutil
  if not shutil.which('java'):self.skipTest('java unavailable')
  fields=next(p['new'].split('\n',1)[1] for p in m.PATCHES if p['old']=='    private final FrameLayout mRootView;')
  methods=next(p['new'] for p in m.PATCHES if p['path'].endswith('/feed/FeedSurfaceCoordinator.java') and 'public View getView()' in p['old'])
  code=(fields+methods).replace('@Nullable ','').replace('@Override','').replace('android.graphics.drawable.Drawable','Drawable').replace('android.widget.ImageView','ImageView').replace('org.chromium.ui.UiUtils.','UiUtils.')
  harness=r"""
import java.util.*;
class HomeHarness {
 static class Drawable {int w,h;Drawable(int a,int b){w=a;h=b;}int getIntrinsicWidth(){return w;}int getIntrinsicHeight(){return h;}}
 static class View {
  static final int VISIBLE=0,INVISIBLE=4;int width,height,visibility;Object parent;Drawable background;
  interface OnAttachStateChangeListener {void onViewAttachedToWindow(View v);void onViewDetachedFromWindow(View v);}
  interface LayoutListener {void changed(View v,int l,int t,int r,int b,int ol,int ot,int or,int ob);}
  OnAttachStateChangeListener attach;LayoutListener layout;
  Object getParent(){return parent;}Drawable getBackground(){return background;}void setBackground(Drawable d){background=d;}
  void setClickable(boolean b){}void setFocusable(boolean b){}void setVisibility(int v){visibility=v;}void invalidate(){}
  void setBackgroundColor(int c){background=new Drawable(0,0);}void setClipChildren(boolean b){}
  int getWidth(){return width;}int getHeight(){return height;}
  void addOnLayoutChangeListener(LayoutListener l){layout=l;}void addOnAttachStateChangeListener(OnAttachStateChangeListener l){attach=l;}
 }
 static class FrameLayout extends View {FrameLayout(Object a){}static class LayoutParams {LayoutParams(int a,int b){}}List<View>children=new ArrayList<>();void addView(View v,LayoutParams p){v.parent=this;children.add(v);}}
 static class ImageView extends View {Drawable drawable;Drawable getDrawable(){return drawable;}}
 static class UiUtils {static void removeViewFromParent(View v){v.parent=null;}}
 Object mActivity=new Object();int mDefaultBackgroundColor=0;FrameLayout mRootView=new FrameLayout(mActivity);View mRecyclerView=new View(),mNtpHeader=new View();
 METHODS
 static void require(boolean b){if(!b)throw new AssertionError();}
 public static void main(String[]args){
  HomeHarness h=new HomeHarness();Drawable original=new Drawable(0,0);h.mRootView.background=original;
  require(h.getView()==h.mRootView);ImageView image=new ImageView();h.initializeSandiumWallpaperBacking(image);
  FrameLayout outer=(FrameLayout)h.getView();require(outer.children.get(0)==image&&outer.children.get(1)==h.mRootView);
  require(h.getSandiumForegroundView()==h.mRootView);final int[]n={0};h.addSandiumWallpaperBackingObserver(()->n[0]++);
  h.setSandiumWallpaperAllowed(true);require(!h.isSandiumWallpaperBackingReady());
  outer.width=400;outer.height=800;image.drawable=new Drawable(400,800);h.onSandiumWallpaperBitmapChanged();require(!h.isSandiumWallpaperBackingReady());
  outer.attach.onViewAttachedToWindow(outer);require(h.isSandiumWallpaperBackingReady()&&h.mRootView.background==null);
  int count=n[0];h.setSandiumToolbarWallpaperPaintColor(123);require(n[0]==count+1);
  h.setSandiumToolbarWallpaperPaintColor(123);require(n[0]==count+1);
  h.setSandiumToolbarWallpaperPaintColor(null);require(n[0]==count+2);
  require(h.isSandiumWallpaperBackingReady());
  int old=n[0];h.onSandiumWallpaperBitmapChanged();require(n[0]==old+1);
  outer.attach.onViewDetachedFromWindow(outer);require(!h.isSandiumWallpaperBackingReady()&&h.mRootView.background==null);
  outer.attach.onViewAttachedToWindow(outer);require(h.isSandiumWallpaperBackingReady());
  h.setSandiumWallpaperAllowed(false);require(!h.isSandiumWallpaperBackingReady()&&image.visibility==View.INVISIBLE&&h.mRootView.background==original);
  h.setSandiumWallpaperAllowed(true);require(h.isSandiumWallpaperBackingReady());
  outer.width=800;outer.height=400;outer.layout.changed(outer,0,0,800,400,0,0,400,800);require(!h.isSandiumWallpaperBackingReady());
  image.drawable=new Drawable(800,400);h.onSandiumWallpaperBitmapChanged();require(h.isSandiumWallpaperBackingReady());
 }
}
""".replace('METHODS',code)
  with tempfile.TemporaryDirectory() as td:
   f=Path(td)/'HomeHarness.java';f.write_text(harness)
   subprocess.run(['java','-m','jdk.compiler/com.sun.tools.javac.Main',str(f)],check=True)
   subprocess.run(['java','-cp',td,'HomeHarness'],check=True)

if __name__=='__main__':unittest.main()
