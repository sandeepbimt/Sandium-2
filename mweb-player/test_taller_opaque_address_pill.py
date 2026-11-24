"""Exact #1520+Incognito design checks; no Android device APIs are impersonated."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import seal
import taller_opaque_address_pill as t

ROOT = Path(__file__).resolve().parents[1]


def live_manifest():
    return json.loads((ROOT / seal.RECIPE).read_bytes())['files']


def source(path):
    digest = live_manifest()[path]['after_sha256']
    data = (ROOT / seal.IMAGE / digest).read_bytes()
    assert seal.digest(data) == digest
    return data.decode()


def method(src, start):
    start = src.index(start)
    return src[start:src.index('\n    }', start) + 6]


class TallerCapsuleTests(unittest.TestCase):
    def test_shared_native_path_and_unchanged_layout(self):
        before = (ROOT / seal.IMAGE / t.OWNERS[t.PHONE]).read_text()
        now = source(t.PHONE)
        methods = [
            '    private void updateLocationBarBackgroundBounds(',
            '    private int calculateOnFocusHeightIncrease(',
            '    public void getLocationBarContentRect(',
            '    private boolean canUseRawSPageActions(',
            '    private boolean isRawSUnifiedPrivateNtp(',
            '    private boolean isRawSBottomNativeHomeOmnibox(',
        ]
        for name in methods:
            self.assertEqual(method(before, name), method(now, name), name)
        bounds = '    private boolean getRawSUnifiedPaintBounds('
        self.assertEqual(method(before, bounds).replace(
            'getRawSUnifiedCapsuleVerticalExtra(inset, rest)',
            'getRawSUnifiedCapsuleVerticalExtra(rest)'), method(now, bounds))
        capsule = '    private boolean drawRawSLegacyCapsuleBehindControls('
        # Only the paint color travels through this path; keep its exact guard and bounds.
        old_capsule = method(before, capsule)
        expected = old_capsule.replace('(Canvas canvas)', '(Canvas canvas, int slimPillColor)')
        expected = expected.replace('mLocationBarBackground.draw(canvas);',
                                    'mLocationBarBackground.drawWithRawSFill(canvas, slimPillColor);')
        self.assertEqual(expected, method(now, capsule))
        self.assertIn('getRawSUnifiedPaintBounds(', method(now, capsule))
        self.assertIn('getRawSUnifiedPaintBounds(outRect, outRect)', method(now, methods[2]))

    def test_exact_geometry_executes_at_multiple_densities_and_focus(self):
        changed = method(source(t.PHONE), '    private int getRawSUnifiedCapsuleVerticalExtra(')
        dp = method(source(t.PHONE), '    private int rawSDp(')
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp, 'Geometry.java')
            src.write_text('''
class Geometry {
    int mLocationBarBackgroundVerticalInset, focus;
    float density;
    int calculateOnFocusHeightIncrease() { return focus; }
    Geometry getResources() { return this; }
    Geometry getDisplayMetrics() { return this; }
''' + changed + '\n' + dp + '''
    static void expect(int actual, int wanted) {
        if (wanted != actual) throw new AssertionError(actual + " != " + wanted);
    }
    static void check(float density) {
        Geometry g = new Geometry();
        g.density = density;
        g.mLocationBarBackgroundVerticalInset = g.rawSDp(8);
        int extra = g.getRawSUnifiedCapsuleVerticalExtra(1f);
        int old = g.rawSDp(4);
        if (extra <= old) throw new AssertionError("pill did not get taller");
        int padding = g.mLocationBarBackgroundVerticalInset - extra;
        if (padding < g.rawSDp(2) || padding - g.rawSDp(2) > 1)
            throw new AssertionError("padding not slim and positive");
        expect(g.getRawSUnifiedCapsuleVerticalExtra(0f), 0);
        int last = extra;
        for (int percent = 1; percent <= 100; percent++) {
            g.focus = Math.round(g.rawSDp(8) * percent / 100f);
            int next = g.getRawSUnifiedCapsuleVerticalExtra(1f - percent / 100f);
            if (next > last) throw new AssertionError("focus reverses growth");
            if (next > 0 && g.mLocationBarBackgroundVerticalInset - g.focus - next < g.rawSDp(2))
                throw new AssertionError("overpaint at focus");
            last = next;
        }
        expect(last, 0);
        g.focus = g.rawSDp(9);
        expect(g.getRawSUnifiedCapsuleVerticalExtra(.8f), 0);
    }
    public static void main(String[] args) {
        for (float density : new float[]{.75f, 1f, 1.5f, 2f, 2.625f, 3f, 4f})
            check(density);
    }
}
''')
            subprocess.run(['java', str(src)], check=True)

    def test_toolbar_never_paints_home_bitmap_but_preserves_page_and_status_bar(self):
        for p in t.OWNERS:
            for symbol in ('drawRawSHomeToolbarWallpaper', 'invalidateRawSHomeToolbarBacking',
                           'setRawSHomeToolbarBackingPainter'):
                self.assertNotIn(symbol, source(p))
        phone = source(t.PHONE)
        self.assertIn('drawRawSLegacyCapsuleBehindControls(canvas, slimPillColor)', phone)
        self.assertIn('mRawSSoftBacking.draw(canvas);', phone)
        self.assertIn('mRawSCapturedSoftBackingColor = getRawSSoftBackingColor();', phone)
        self.assertIn('Color.alpha(homeColor) == 255 ? homeColor : fallback | 0xff000000', phone)
        self.assertIn('if (tab.isOffTheRecord()) return fallback | 0xff000000;', phone)
        feed = source(t.FEED)
        self.assertIn('mRootView.getLocationInWindow(mRawSHomeRootLocation);', feed)
        self.assertIn('private void drawRawSHomeWallpaper(Canvas canvas)', feed)
        self.assertIn('mRawSHomeStatusBarInvalidator', feed)
        self.assertIn('toolbar.getStatusBarColorController().updateStatusBarColor();', source(t.HOME))
        # Existing native compositor already paints the real opaque band behind captured controls.
        manifests = live_manifest()
        layer = next(p for p in manifests if p.endswith('/layer/toolbar_layer.cc'))
        self.assertIn('SkColorGetA(raws_soft_backing) == 255', source(layer))
        self.assertIn('resource->location_bar_content_rect()', source(layer))

    def test_reviewed_component_postimages_and_active_admission(self):
        current = live_manifest()
        for owner, expected in t.OWNERS.items():
            before = (ROOT / seal.IMAGE / expected).read_bytes()
            self.assertEqual(seal.digest(before), expected)
            result = t.transform(owner, before)
            self.assertEqual((ROOT / seal.IMAGE / seal.digest(result)).read_bytes(), result)
            self.assertIn(owner, current)
        self.assertEqual(seal.digest((ROOT / seal.RECIPE).read_bytes()),
                         json.loads((ROOT / seal.ADMISSION).read_bytes())['manifest_sha256'])


if __name__ == '__main__':
    unittest.main()
