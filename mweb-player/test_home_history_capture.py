"""Regression for recorded lower Home thumbnail versus settled live Home (#1516)."""

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import home_history_capture as change

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).with_name('fixtures') / 'home-history-capture'
IMAGES = ROOT / 'raws-adblock/production-postimages'
FILES = json.loads((ROOT / 'raws-adblock/production-restore-recipe.json').read_text())['files']


class HomeHistoryCaptureTest(unittest.TestCase):
    def setUp(self):
        self.before = {
            **{p: (IMAGES / sha).read_bytes() for p, sha in change.OWNERS.items()},
            **{p: (FIXTURES / Path(p).name).read_bytes() for p in change.TRACKED},
        }
        self.after = {p: change.transform(p, data).decode() for p, data in self.before.items()}

    def test_exact_pinned_preimages_and_active_postimages(self):
        for path, before in self.before.items():
            with self.subTest(path=path):
                if path in change.TRACKED:
                    blob = b'blob ' + str(len(before)).encode() + b'\0' + before
                    self.assertEqual(hashlib.sha1(blob).hexdigest(), change.GIT_BLOBS[path])
                    self.assertEqual(FILES[path]['before_sha256'], change.TRACKED[path])
                data = self.after[path].encode()
                digest = hashlib.sha256(data).hexdigest()
                self.assertEqual(FILES[path]['after_sha256'], digest)
                self.assertEqual((IMAGES / digest).read_bytes(), data)
                with self.assertRaises(ValueError):
                    change.transform(path, before + b'\n')

    def test_scope_only_capture_origin_and_existing_live_measurement_agreement(self):
        ntp = self.after[change.NTP]
        self.assertEqual(ntp.replace(change.HOME_CONTRACT, '', 1), self.before[change.NTP].decode())
        self.assertIn('final int topMargin = getToolbarExtraYOffset() + topControlsDistanceToRest;', ntp)
        self.assertIn('mBrowserControlsStateProvider.getContentOffset()\n'
                      '                        - mBrowserControlsStateProvider.getTopControlsHeight()', ntp)
        cap = self.after[change.CAPTURER]
        self.assertIn('capture(tab, true, topControlsHeight)', cap)
        self.assertIn('capture(tab, false, 0)', cap)
        self.assertIn('return capturer.mHardwareDraw.startBitmapCapture(', cap)
        self.assertIn('canvas.translate(0, -overlap + (fullscreen ? topControlsHeight : 0));', cap)
        self.assertEqual(cap.count('getHeightOverlappedForHistoryScreenshot()'), 2)
        for fixed in ('canvas.drawColor(tab.getNativePage().getBackgroundColor());',
                      'view.draw(canvas);', 'bitmap.eraseColor(page.getBackgroundColor());'):
            self.assertIn(fixed, cap)
        self.assertEqual(self.after[change.BASE_PAGE].replace(change.BASE_CONTRACT, '', 1),
                         self.before[change.BASE_PAGE].decode())

    def test_negative_attached_origin_and_stock_fallbacks(self):
        java = shutil.which('java')
        if not java:
            self.skipTest('Java source launcher unavailable')
        # Execute the exact production methods including the real default interface fallback.
        ordinary_capture = re.search(r'            int overlap = fullscreen\n.*?;\n'
                                     r'            canvas.translate[^\n]+',
                                     self.after[change.CAPTURER], re.S)[0]
        source = '''class HomeTest implements NativePage {
    static class ViewGroup {
        static class MarginLayoutParams { int topMargin = -112; }
    }
    static class Matrix {
        boolean identity = true;
        boolean isIdentity() { return identity; }
    }
    static class View {
        int top = -112, height = 1500;
        boolean attached = true, laidOut = true, pending;
        Object params = new ViewGroup.MarginLayoutParams();
        Matrix matrix = new Matrix();
        boolean isAttachedToWindow() { return attached; }
        boolean isLaidOut() { return laidOut; }
        boolean isLayoutRequested() { return pending; }
        Object getLayoutParams() { return params; }
        Matrix getMatrix() { return matrix; }
        int getTop() { return top; }
        int getHeight() { return height; }
    }
    static class ControlsPosition { static final int TOP = 1, BOTTOM = 2; }
    static class Controls {
        int position = ControlsPosition.BOTTOM;
        int content, bottom;
        int getControlsPosition() { return position; }
        int getContentOffset() { return content; }
        int getBottomControlOffset() { return bottom; }
    }
    class Tab {
        boolean destroyed, hidden, offTheRecord;
        Object nativePage = HomeTest.this;
        View view = root;
        boolean isDestroyed() { return destroyed; }
        boolean isHidden() { return hidden; }
        boolean isOffTheRecord() { return offTheRecord; }
        Object getNativePage() { return nativePage; }
        View getView() { return view; }
    }
    class Context {
        String packageName = "io.github.sandeepbimt.raws";
        String getPackageName() { return packageName; }
    }
    final View root = new View();
    final Context mContext = new Context();
    final Tab mTab = new Tab();
    final Controls mBrowserControlsStateProvider = new Controls();
    final java.util.function.Supplier<Tab> mActivityTabProvider = () -> this.active ? mTab : null;
    final java.util.function.Supplier<Integer> mTabStripHeightSupplier = () -> this.tabStripHeight;
    boolean active = true, mIsLff, mIsDestroyed;
    int tabStripHeight, mToolbarHeight = 112, ordinaryOverlap;
    View getView() { return root; }
    @Override public int getHeightOverlappedWithTopControls() { return ordinaryOverlap; }
''' + change.HOME_CONTRACT + '''
    static class Canvas {
        int y;
        void translate(int x, int y) { this.y = y; }
    }
    static int captureOrigin(NativePage page, boolean fullscreen, int topControlsHeight) {
        Canvas canvas = new Canvas();
''' + ordinary_capture + '''
        return canvas.y;
    }
    static void equal(int expected, int actual) {
        if (expected != actual) throw new AssertionError("expected " + expected + ", got " + actual);
    }
    static void fallback(java.util.function.Consumer<HomeTest> change) {
        HomeTest page = new HomeTest();
        change.accept(page);
        equal(0, page.getHeightOverlappedForHistoryScreenshot());
    }
    public static void main(String[] args) {
        HomeTest page = new HomeTest();
        equal(112, page.getHeightOverlappedForHistoryScreenshot());
        equal(0, captureOrigin(page, true, 0));
        equal(-112, captureOrigin(page, false, 0));
        for (int featureY : new int[]{260, 650, 1120}) {
            int live = page.root.top + featureY;
            int legacyPreview = featureY - page.getHeightOverlappedWithTopControls();
            equal(112, legacyPreview - live);
            equal(live, captureOrigin(page, false, 0) + featureY);
        }
        page.ordinaryOverlap = 121;
        equal(-121, captureOrigin(page, false, 0));
        equal(0, captureOrigin(page, true, 121));
        equal(7, captureOrigin(page, true, 128));
        NativePage other = () -> 71;
        equal(-71, captureOrigin(other, false, 0));
        equal(0, captureOrigin(other, true, 71));
        fallback(p -> p.mContext.packageName = "other.package");
        fallback(p -> p.mTab.offTheRecord = true);
        fallback(p -> p.mIsLff = true);
        fallback(p -> p.mIsDestroyed = true);
        fallback(p -> p.mTab.destroyed = true);
        fallback(p -> p.mTab.hidden = true);
        fallback(p -> p.active = false);
        fallback(p -> p.mTab.nativePage = null);
        fallback(p -> p.mTab.view = new View());
        fallback(p -> p.root.attached = false);
        fallback(p -> p.root.laidOut = false);
        fallback(p -> p.root.pending = true);
        fallback(p -> p.root.matrix.identity = false);
        fallback(p -> p.root.params = null);
        fallback(p -> ((ViewGroup.MarginLayoutParams) p.root.params).topMargin = 0);
        fallback(p -> p.root.top = 0);
        fallback(p -> p.root.height = 100);
        fallback(p -> p.mToolbarHeight = 0);
        fallback(p -> p.tabStripHeight = 1);
        fallback(p -> p.mBrowserControlsStateProvider.bottom = 20);
        fallback(p -> p.mBrowserControlsStateProvider.content = 10);
        fallback(p -> p.mBrowserControlsStateProvider.position = ControlsPosition.TOP);
    }
}
interface NativePage {
    int getHeightOverlappedWithTopControls();
''' + change.BASE_CONTRACT + '}'
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / 'HomeTest.java'
            file.write_text(source)
            subprocess.run([java, file], check=True)


if __name__ == '__main__':
    unittest.main()
