"""Host checks against exact sealed Home toolbar wallpaper paint."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import home_toolbar_wallpaper as d
import seal

ROOT = Path(__file__).resolve().parents[1]


class HomeToolbarWallpaper(unittest.TestCase):
    def read(self):
        recipe = json.loads((ROOT / seal.RECIPE).read_bytes())['files']
        return {k:(ROOT / seal.IMAGE / recipe[k]['after_sha256']).read_text() for k in d.OWNERS}

    def test_exact_four_owners_and_no_geometry_or_compositor_change(self):
        read = lambda name: seal.git('show', d.BASE + ':' + name)
        patch = seal.plan(read, d.OWNERS, d.MAN, d.PROOF, d.transform)
        for name, data in patch.items():
            self.assertEqual((ROOT / name).read_bytes(), data)
        original = json.loads(read(seal.RECIPE))['files']
        current = json.loads((ROOT / seal.RECIPE).read_bytes())['files']
        self.assertEqual(set(current), set(original))
        self.assertEqual({k for k in original if original[k] != current[k]}, set(d.OWNERS))
        source = self.read()
        for owner, start, end in (
                (d.HOME, '    public int getHeightOverlappedForHistoryScreenshot() {',
                 '    @Override\n'),
                (d.FEED, '    private boolean updateRawSHomeWallpaperGeometry() {',
                 '    // The shipped bitmap is untouched.'),
                (d.PHONE, '    private @ColorInt int getRawSSoftBackingColor() {',
                 '    private void clearRawSSoftWebColor()')):
            def section(text):
                i = text.index(start)
                return text[i:text.index(end, i+len(start))]
            actual = section(source[owner])
            if owner == d.FEED:
                self.assertIn('mRawSHomeToolbarGeometryDirty = true;', actual)
                actual = actual.replace('            mRawSHomeToolbarGeometryDirty = true;\n', '')
            self.assertEqual(actual, section(read(seal.IMAGE+d.OWNERS[owner]).decode()))

    def test_success_replaces_both_opaque_branches_pre_control_draw(self):
        source = self.read()
        phone = source[d.PHONE]
        start = phone.index('    protected void dispatchDraw(Canvas canvas)')
        method = phone[start:phone.index('    private boolean drawRawSLegacyCapsuleBehindControls', start)]
        guard = 'rawSBackingColor != Color.TRANSPARENT && isRawSBottomNativeHomeOmnibox()'
        self.assertIn('mTextureCaptureMode ? Color.TRANSPARENT', method)
        self.assertIn(guard, method)
        self.assertIn('Color.alpha(mCurrentLocationBarColor) == 255', method)
        self.assertIn('painter != null && painter.test(canvas, this)', method)
        before, after = method.split('} else if (rawSBackingColor != Color.TRANSPARENT)', 1)
        self.assertNotIn('mRawSSoftBacking.draw', before)
        self.assertNotIn('mToolbarBackground.draw', before)
        self.assertIn('mRawSHomeToolbarScrim.draw(canvas)', before)
        self.assertIn('0x16000000', phone)
        self.assertIn('mRawSSoftBacking.draw(canvas)', after)
        self.assertIn('mToolbarBackground.draw(canvas)', after)
        self.assertIn('mLocationBarBackgroundBounds', after)
        self.assertIn('drawWithoutBackground(canvas)', after)
        home = source[d.HOME]
        for guard in ('mTab.getNativePage() == this', 'mActivityTabProvider.get() == mTab',
                      'getBottomControlOffset() == 0', 'getContentOffset() == 0'):
            self.assertIn(guard, home)
        self.assertIn('home.drawRawSHomeToolbarWallpaper(canvas, toolbar)', source[d.MANAGER])
        self.assertIn('if (mRawSHomeToolbarGeometryDirty', source[d.FEED])
        self.assertIn('invalidateRawSHomeCompanionPaint();', source[d.FEED])
        self.assertIn('toolbar.invalidateRawSHomeToolbarBacking();', home)
        self.assertIn('mTab.getView() == getView()', home)

    def test_extracted_java_reuses_wallpaper_at_boundary_without_rescale(self):
        java = shutil.which('java')
        if not java:
            self.skipTest('Java source launcher absent')
        feed = self.read()[d.FEED]
        extract = feed[feed.index('    public boolean drawRawSHomeToolbarWallpaper('):
                       feed.index('    private void drawRawSHomeWallpaper(Canvas canvas)')]
        fixture = r"""
class Check {
  static void ok(boolean x) { if (!x) throw new AssertionError(); }
  public static void main(String[] args) {
    var owner = new Home();
    var toolbar = new View(0, 765, 400, 55);
    var canvas = new Canvas();
    ok(owner.drawRawSHomeToolbarWallpaper(canvas, toolbar));
    ok(canvas.draws == 1 && canvas.right == 400 && canvas.bottom == 55);
    var m = owner.mRawSHomeToolbarWallpaperMatrix;
    ok(m.sx == .5f && m.sy == .5f && m.x == -6f && m.y == -877f);
    ok(owner.mRawSHomeToolbarWallpaperPaint.shader == owner.mRawSHomeToolbarWallpaperShader);
    toolbar.y -= 4;
    ok(owner.drawRawSHomeToolbarWallpaper(canvas, toolbar) && m.y == -873f);
    toolbar.y += 8;
    ok(!owner.drawRawSHomeToolbarWallpaper(canvas, toolbar));
    toolbar.y -= 4;
    owner.mRootView.laid = false;
    ok(!owner.drawRawSHomeToolbarWallpaper(canvas, toolbar));
    owner.mRootView.laid = true;
    owner.mRawSHomeWallpaperPainting = false;
    ok(!owner.drawRawSHomeToolbarWallpaper(canvas, toolbar));
    owner.mRawSHomeWallpaperPainting = true;
    owner.mRawSHomeNativeImageActive = true;
    ok(!owner.drawRawSHomeToolbarWallpaper(canvas, toolbar));
    ok(canvas.draws == 2);
  }
}
class Home {
  boolean mRawSHomeWallpaperPainting = true, mRawSHomeWallpaperIncludesBrand, mRawSHomeNativeImageActive;
  Bitmap mRawSHomeWallpaperBitmap = new Bitmap();
  BitmapShader mRawSHomeToolbarWallpaperShader = new BitmapShader();
  RectF mRawSHomeWallpaperDest = new RectF();
  View mRootView = new View(0, -112, 400, 877);
  int mRawSHomeWallpaperWidth = 400, mRawSHomeWallpaperHeight = 877;
  int[] mRawSHomeRootLocation = new int[2], mRawSHomeToolbarLocation = new int[2];
  Matrix mRawSHomeToolbarWallpaperMatrix = new Matrix();
  Paint mRawSHomeToolbarWallpaperPaint = new Paint();
  METHOD
}
class Bitmap {
  int getWidth() { return 824; }
  int getHeight() { return 1754; }
}
class RectF {
  float left = -6, top = 0;
  float width() { return 412; }
  float height() { return 877; }
  boolean isEmpty() { return false; }
}
class Matrix {
  float sx, sy, x, y;
  void setScale(float a, float b) { sx = a; sy = b; }
  void postTranslate(float a, float b) { x = a; y = b; }
  boolean isIdentity() { return true; }
}
class BitmapShader { void setLocalMatrix(Matrix x) {} }
class Paint {
  BitmapShader shader;
  void setShader(BitmapShader v) { shader = v; }
}
class Canvas {
  int draws, right, bottom;
  void drawRect(int a, int b, int c, int d, Paint p) { draws++; right = c; bottom = d; }
}
class View {
  int x,y,w,h;
  boolean laid = true;
  View(int a,int b,int c,int d) { x=a; y=b; w=c; h=d; }
  boolean isAttachedToWindow() { return true; }
  boolean isShown() { return true; }
  boolean isLaidOut() { return laid; }
  boolean isLayoutRequested() { return false; }
  Matrix getMatrix() { return new Matrix(); }
  Object getWindowToken() { return View.class; }
  void getLocationInWindow(int[] p) { p[0]=x; p[1]=y; }
  int getWidth() { return w; }
  int getHeight() { return h; }
}
"""
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / 'Check.java'
            p.write_text(fixture.replace('METHOD', extract))
            subprocess.run([java, str(p)], check=True)


if __name__ == '__main__':
    unittest.main()
