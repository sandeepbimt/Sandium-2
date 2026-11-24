"""Execute actual RawS Home geometry and keep exact active-source contracts honest."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RECIPE=ROOT/'raws-adblock/production-restore-recipe.json'

def read(name):
    files=json.loads(RECIPE.read_text())['files']
    keys=[p for p in files if p.endswith('/'+name)]
    assert len(keys)==1,(name,keys)
    identity=files[keys[0]]['after_sha256']
    data=(ROOT/'raws-adblock/production-postimages'/identity).read_bytes()
    assert hashlib.sha256(data).hexdigest()==identity
    return data.decode()

def method(s,name):
    start=s.index(name)
    inside=s.index('{',start)
    depth=1
    i=inside+1
    while depth:
        depth+=(s[i]=='{')-(s[i]=='}')
        i+=1
    return s[start:i]

class RawSHomeGridTest(unittest.TestCase):
    def test_real_java_grid_viewport_and_bottom_scroll(self):
        m=read('MostVisitedTilesLayout.java')
        t=read('NewTabPageLayout.java')
        methods='\n'.join(method(m,'static int '+name+'(') for name in
                          ['rawSGridRow','rawSGridColumn','rawSGridScrollY'])
        methods+='\n'+method(t,'static int rawSLowerShortcutsGap(')
        methods+='\n'+method(m,'private int visibleGridHeight()')
        src='''class Grid {
          static final int RAWS_GRID_COLUMNS=4, RAWS_VISIBLE_ROWS=4;
          int[] mRawSGridHeights;
          int getPaddingTop(){return 0;}
          int getPaddingBottom(){return 0;}
          ''' + methods + '''
          static void check(boolean value) { if (!value) throw new AssertionError(); }
          public static void main(String[] args) {
            Grid g=new Grid();
            for (int count : new int[]{0,1,4,5,16,17,20,21,41,200}) {
              int rows=(count+3)/4;
              g.mRawSGridHeights=new int[rows];
              java.util.Arrays.fill(g.mRawSGridHeights,76);
              check(g.visibleGridHeight()==Math.min(rows,4)*76);
              int range=rows*76-g.visibleGridHeight();
              check(rawSGridScrollY(range,0)==range);
              check(rawSGridScrollY(range,76)==Math.max(0,range-76));
              check(rawSGridScrollY(range,999999)==0);
              int prev=-1;
              for (int i=0;i<count;i++) {
                int row=rawSGridRow(i,count),col=rawSGridColumn(i,count);
                check(0<=col && col<4 && 0<=row && row<rows && row*4+col>prev);
                prev=row*4+col;
              }
              if(rows>4){
                int minimumRowVisible=rawSGridScrollY(range,0)/76;
                check(rawSGridRow(count-16,count)==minimumRowVisible);
                check(rawSGridRow(count-17,count)==minimumRowVisible-1);
              }
            }
            check(rawSGridRow(0,5)==0 && rawSGridColumn(0,5)==0);
            check(rawSGridRow(1,5)==1 && rawSGridColumn(1,5)==0);
            check(rawSGridRow(4,5)==1 && rawSGridColumn(4,5)==3);
            int bottom=-1;
            for (int rows=1; rows<=4; rows++) {
              int natural=112+rows*76;
              int anchored=rawSLowerShortcutsGap(800,natural,natural,1f)+natural;
              if(bottom>=0) check(bottom==anchored);
              check(anchored<=800-96); bottom=anchored;
            }
            check(rawSLowerShortcutsGap(490,128,150,1f)==0);
            check(rawSLowerShortcutsGap(590,600,620,1f)==0);
          }
        }'''
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'Grid.java';p.write_text(src)
            subprocess.run([shutil.which('java'),str(p)],check=True)

    def test_actual_scroll_owner_with_simulated_android_boundaries(self):
        s=read('MostVisitedTilesLayout.java')
        impl=method(s,'private static final class RawSGridScrollView')
        impl+='\n'+method(s,'static int rawSGridScrollY(')
        layout='''class Owner {
    static class Context {}
    static class Parent {
      boolean interceptDisabled;
      void requestDisallowInterceptTouchEvent(boolean b){interceptDisabled=b;}
    }
    static class MotionEvent {
      static final int ACTION_DOWN=0, ACTION_UP=1, ACTION_CANCEL=3;
      final int action;
      MotionEvent(int a){action=a;}
      int getActionMasked(){return action;}
    }
    static class TileView {
      int top=0,bottom=76;
      int getTop(){return top;}
      int getBottom(){return bottom;}
    }
    static class MostVisitedTilesLayout {
      int cells=0, rendered=0, viewport=0;
      Integer mTileToMoveInViewIdx;
      final TileView tile=new TileView();
      int getTileCount(){return cells;}
      int visibleGridHeight(){return viewport;}
      int getHeight(){return rendered;}
      TileView getTileAt(int position){return tile;}
    }
    static class ScrollView {
      static final int OVER_SCROLL_IF_CONTENT_SCROLLS=1;
      int y,height,focusReveal=-1;
      final Parent parent=new Parent();
      static class MeasureSpec {
        static final int UNSPECIFIED=0;
        static int getMode(int spec){return spec==0?0:1;}
        static int getSize(int spec){return spec;}
      }
      ScrollView(Context c){}
      void setFillViewport(boolean b){}
      void setHorizontalScrollBarEnabled(boolean b){}
      void setVerticalScrollBarEnabled(boolean b){}
      void setNestedScrollingEnabled(boolean b){}
      void setOverScrollMode(int mode){}
      void requestLayout(){}
      int getHeight(){return height;}
      int getMeasuredWidth(){return 360;}
      int getPaddingTop(){return 0;}
      int getPaddingBottom(){return 0;}
      int getScrollY(){return y;}
      void setMeasuredDimension(int w,int h){height=h;}
      void scrollTo(int x,int y){if(x!=0) throw new AssertionError();this.y=y;}
      Parent getParent(){return parent;}
      boolean dispatchTouchEvent(MotionEvent event){return true;}
      protected void onMeasure(int w,int h){}
      protected void onLayout(boolean changed,int l,int t,int r,int b){
        if(focusReveal>=0) y=focusReveal;
      }
    }
    '''+impl+'''
    static void check(boolean b){ if(!b) throw new AssertionError(); }
    public static void main(String[] args){
      var tiles=new MostVisitedTilesLayout();
      var host=new RawSGridScrollView(new Context(),tiles);
      host.restoreDistanceFromBottom(152);
      host.onMeasure(360,0);host.onLayout(true,0,0,360,0);
      check(host.getHeight()==0 && host.distanceFromBottom()==0);
      tiles.cells=25;tiles.rendered=7*76;tiles.viewport=4*76;
      host.onMeasure(360,0);host.onLayout(true,0,0,360,304);
      check(host.y==76 && host.distanceFromBottom()==152);
      var fresh=new RawSGridScrollView(new Context(),tiles);
      fresh.onMeasure(360,0);fresh.onLayout(true,0,0,360,304);
      check(fresh.y==228 && fresh.distanceFromBottom()==0);
      fresh.dispatchTouchEvent(new MotionEvent(MotionEvent.ACTION_DOWN));
      check(fresh.parent.interceptDisabled);
      fresh.dispatchTouchEvent(new MotionEvent(MotionEvent.ACTION_UP));
      check(!fresh.parent.interceptDisabled);
      fresh.y=152; // Downward finger moved scroll position 76px toward earlier y.
      tiles.cells=29;tiles.rendered=8*76;
      fresh.onMeasure(360,0);fresh.onLayout(true,0,0,360,304);
      check(fresh.y==228 && fresh.distanceFromBottom()==76);
      fresh.focusReveal=120;
      fresh.onLayout(false,0,0,360,304);
      check(fresh.y==120);  // Normal relayout preserves the native focus reveal.
      tiles.mTileToMoveInViewIdx=0;
      fresh.onLayout(false,0,0,360,304);
      check(fresh.y==0 && tiles.mTileToMoveInViewIdx==null);
    }
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'Owner.java'
            p.write_text(layout)
            subprocess.run([shutil.which('java'),str(p)],check=True)

    def test_owners_accessibility_and_native_data_contracts(self):
        ntp=read('NewTabPage.java')
        grid=read('MostVisitedTilesLayout.java')
        self.assertIn('fakebox.setVisibility(View.INVISIBLE)',ntp)
        self.assertIn('return false;',method(read('NewTabPageCoordinator.java'),
                                             'boolean usesRawSHomeSearchLauncher('))
        self.assertIn('tiles.restoreRawSGridDistanceFromBottom(Float.parseFloat(page))',ntp)
        self.assertIn('RAWS_SHORTCUT_GRID_OFFSET',method(ntp,'private void saveRawSShortcutPosition('))
        self.assertIn('mTab.getNativePage() != this',ntp)
        self.assertIn('extends ScrollView',grid)
        self.assertIn('old.removeView(this)',grid)
        self.assertNotIn('mRawSGridPager',grid)
        self.assertNotIn('raws_home_more_shortcuts',grid)
        self.assertIn('mPendingDistance',grid)
        self.assertIn('setSaveFromParentEnabled(false)',grid)
        self.assertIn('reveal < count',grid)
        self.assertIn('scrollTo(0, Math.max',grid)
        self.assertIn('View.LAYOUT_DIRECTION_RTL',grid)
        self.assertNotIn('setImportantForAccessibility',grid)
        self.assertIn('if (!rawSGrid && shouldShowAddNewButton(sectionTiles))',read('TileRenderer.java'))
        self.assertIn('bridge.addCustomLink(title, url, /* pos= */ 0)',ntp)
        self.assertIn('max_links = 200;',read('chrome_custom_links_manager_factory.cc'))
        cap=method(read('custom_links_manager_impl.cc'),'bool CustomLinksManagerImpl::AddLinkTo')
        self.assertIn('current_links_.size() >= max_links_',cap)
        self.assertNotIn('.resize(',cap)
        cache=method(read('most_visited_sites.cc'),'void MostVisitedSites::ReloadCustomLinksCache()')
        self.assertIn('manual_custom_links_only',cache)
        self.assertNotIn('StoreLinks',cache)
        host=method(grid,'public boolean useRawSHomeShortcutGrid()')
        self.assertNotIn('setBackground',host)
        self.assertIn('host.setPaddingRelative(old.getPaddingStart(), old.getPaddingTop(),',host)
        self.assertNotIn('createRawSHomeTranslucentSurface',ntp)

    def test_stardust_is_individual_paint_and_scope_is_native_home(self):
        ntp=read('NewTabPage.java')
        scope=ntp.split('final boolean allowRawSHomeGrid = ',1)[1].split(';',1)[0]
        for condition in ['!mIsLff','!profile.isOffTheRecord()',
                          '!AddressBarPreference.isToolbarConfiguredToShowOnTop()',
                          '!NewTabPageUtils.isBesideMvtModuleEnabled()']:
            self.assertIn(condition,scope)
        self.assertIn('if (useRawSHomeGrid) coordinator.useRawSHomeStardustBrandHalo();',ntp)
        self.assertIn('/* wallpaperIncludesBrand= */ false,',ntp)
        self.assertIn('suggestion.useRawSHomeTilePaint(isRawSHomeShortcutGrid())',
                      read('MostVisitedTilesLayout.java'))
        tile=method(read('SuggestionsTileView.java'),'void useRawSHomeTilePaint(boolean stardust)')
        self.assertIn('stardust ? 0xA6E7C296 : 0x48FFFFFF',tile)
        self.assertIn('mIconBackgroundView.setBackground(backing)',tile)
        for effect in ['setLayoutParams','mIconView','setOnTouchListener','setContentDescription']:
            self.assertNotIn(effect,tile)
        feed=read('FeedSurfaceCoordinator.java')
        draw_child=method(feed,'protected boolean drawChild(Canvas canvas, View child, long drawingTime)')
        self.assertLess(draw_child.index('drawRawSHomeWallpaper(canvas)'),
                        draw_child.index('drawRawSHomeBrand(canvas)'))
        for owner in ['drawRawSHomeWallpaper','decodeRawSHomeWallpaper',
                      'updateRawSHomeStatusPaintColor','updateRawSHomePaddingPaintColor']:
            decl=[l for l in feed.splitlines() if l.lstrip().startswith(('private ','public '))
                  and (owner+'(') in l]
            self.assertEqual(len(decl),1,owner)
            path=method(feed,decl[0].strip())
            self.assertNotIn('Stardust',path)
            self.assertNotIn('drawRawSHomeBrand',path)

    def test_native_title_shadow_only_on_stardust(self):
        tile=method(read('SuggestionsTileView.java'),'void useRawSHomeTilePaint(boolean stardust)')
        src='''class Labels {
          static class GradientDrawable {
            enum Orientation { TL_BR }
            GradientDrawable(Orientation direction,int[] colors){}
            void setCornerRadius(float r){}
            void setStroke(int px,int color){}
          }
          static class Resources {
            Resources getDisplayMetrics(){return this;}
            float density=2f;
          }
          static class Title {
            int draws;
            void setShadowLayer(float r,float x,float y,int color){
              check(r==5f && x==0f && y==2f && color==0xc7000000);
              draws++;
            }
          }
          static class View {
            void setBackground(GradientDrawable g){}
          }
          final Title title=new Title();
          boolean mHasRawSHomeTilePaint;
          View mIconBackgroundView=new View();
          Resources getResources(){return new Resources();}
          Title getTitleView(){return title;}
          ''' + tile + '''
          static void check(boolean value) { if (!value) throw new AssertionError(); }
          public static void main(String[] args) {
            Labels active=new Labels(), inactive=new Labels();
            active.useRawSHomeTilePaint(true); active.useRawSHomeTilePaint(true);
            inactive.useRawSHomeTilePaint(false);
            check(active.title.draws==1 && inactive.title.draws==0);
          }
        }'''
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'Labels.java';p.write_text(src)
            subprocess.run([shutil.which('java'),str(p)],check=True)

    def test_actual_brand_draw_order_across_native_backings(self):
        feed=read('FeedSurfaceCoordinator.java')
        impl='\n'.join(method(feed,owner) for owner in [
            'public void useRawSHomeStardustBrandHalo()',
            'private void drawRawSHomeBrand(Canvas canvas)',
            'private void drawRawSHomeStardustBrandHalo(Canvas canvas)'])
        src='''class Stardust {
          static class Paint {
            static final int ANTI_ALIAS_FLAG=1;
            static int allocations;
            Paint(int flags) { allocations++; }
            void setShader(RadialGradient shader) {}
          }
          static class Shader { enum TileMode { CLAMP } }
          static class RadialGradient {
            RadialGradient(float x,float y,float r,int a,int b,Shader.TileMode mode) {
              check(x==0 && y==0 && r==1 && a==0x40D99853 && b==0x00D99853);
            }
          }
          static class Bitmap { final String label; Bitmap(String s) { label=s; } }
          static class RectF {
            float centerX(){return 200;} float centerY(){return 350;}
            float width(){return 320;} float height(){return 110;}
          }
          record Brand(Bitmap image, Bitmap shadow) {}
          static class Root { void invalidate(){} }
          static class Canvas {
            final StringBuilder trace=new StringBuilder();
            void drawColor(int color) { trace.append('B'); }
            void drawBitmap(Bitmap bitmap,Object src,RectF dest,Paint paint) {
              trace.append(bitmap.label);
            }
            int save(){trace.append('[');return 7;}
            void translate(float x,float y){check(x==200 && y==350);}
            void scale(float x,float y){check(x==320*.72f && y==110*1.35f);}
            void drawCircle(float x,float y,float r,Paint p){
              check(x==0 && y==0 && r==1 && p!=null); trace.append('H');
            }
            void restoreToCount(int n) { check(n==7);trace.append(']'); }
          }
          Object mRawSHomeWallpaperSearch, mRawSHomeBrandSource = new Object();
          Paint mRawSHomeStardustHaloPaint;
          final Paint mRawSHomeBrandShadowPaint = new Paint(0),
                      mRawSHomeWallpaperPaint = new Paint(0);
          final RectF mRawSHomeBrandDest = new RectF(), mRawSHomeBrandShadowDest = new RectF();
          final Root mRootView = new Root();
          Brand mRawSHomeBrand = new Brand(new Bitmap("M"), new Bitmap("S"));
          boolean mRawSHomeBrandPainting=true, mRawSHomeWallpaperIncludesBrand,
                  mRawSHomeWallpaperPainting, mRawSHomeSolidBackdropMoved, mRawSHomeWallpaperDirty;
          int mRawSHomeNativeBackdropColor;
          ''' + impl + '''
          static void check(boolean value) { if (!value) throw new AssertionError(); }
          void checkTrace(String s){
            Canvas c=new Canvas();
            drawRawSHomeBrand(c);
            check(c.trace.toString().equals(s));
          }
          public static void main(String[] args) {
            Stardust d=new Stardust();
            d.useRawSHomeStardustBrandHalo();
            d.checkTrace("SM"); // Off-scope native call cannot enable.
            d.mRawSHomeWallpaperSearch=new Object();
            int before=Paint.allocations;
            d.useRawSHomeStardustBrandHalo();d.useRawSHomeStardustBrandHalo();
            check(d.mRawSHomeWallpaperDirty && Paint.allocations==before+1);
            d.mRawSHomeWallpaperPainting=true;
            d.checkTrace("[H]SM"); // Independently painted over built-in wallpaper.
            d.mRawSHomeWallpaperPainting=false;
            d.checkTrace("[H]SM"); // Native opaque custom image already drawn below.
            d.mRawSHomeSolidBackdropMoved=true;
            d.checkTrace("B[H]SM"); // Native solid still paints before the same logo.
            d.mRawSHomeBrandPainting=false;
            d.checkTrace("");
            check(Paint.allocations==before+1);
          }
        }'''
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'Stardust.java';p.write_text(src)
            subprocess.run([shutil.which('java'),str(p)],check=True)

    def test_real_gate(self):
        sys.path.insert(0,str(ROOT/'tools'))
        from restore_only_feature import load
        manifest=json.loads(RECIPE.read_text())
        a=load(ROOT,manifest['baseline_fingerprint'],manifest['chromium_revision'])
        self.assertEqual(a.identity,hashlib.sha256(RECIPE.read_bytes()).hexdigest())
        self.assertEqual(a.files['chrome/browser/ntp_tiles/chrome_custom_links_manager_factory.cc'][2],'644')

if __name__=='__main__':unittest.main()
