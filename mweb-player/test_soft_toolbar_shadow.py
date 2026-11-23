import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

import materialize_soft_shadow as materialize
import soft_toolbar_shadow as change
import seal

HERE = Path(__file__).resolve().parents[1]
PREIMAGES = HERE.parent / 'chromium-52bdd-preimages'


def method(text, name):
    index = text.index(name)
    start = text.index('{', index)
    depth = 1
    for stop in range(start + 1, len(text)):
        depth += (text[stop] == '{') - (text[stop] == '}')
        if not depth:
            return text[index:stop+1]
    raise ValueError(name)


class SoftToolbarShadowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not all((PREIMAGES / path).is_file()
                   for path in change.OWNERS if path != change.PHONE):
            raise unittest.SkipTest('Exact pinned Chromium source fixtures not installed')
        _, out = materialize.make_plan(PREIMAGES)
        cls.sources = {}
        for path, expected in change.OWNERS.items():
            before = (PREIMAGES / path).read_bytes() if path != change.PHONE else seal.git(
                'show', materialize.BASE + ':' + seal.IMAGE + expected)
            post = change.transform(path, before)
            assert out[seal.IMAGE + hashlib.sha256(post).hexdigest()] == post
            cls.sources[path] = post.decode()

    def test_shadow_only_and_native_capture_order(self):
        src = self.sources[change.PHONE]
        self.assertIn('mTextureCaptureMode ? Color.TRANSPARENT : getRawSSoftBackingColor()', src)
        self.assertLess(src.index('mRawSSoftShade.draw(canvas)'), src.index('mRawSLegacyCapsuleDrawn ='))
        self.assertIn('int[] {0x00000000, 0x48000000}', src)
        self.assertIn('mRawSCapturedSoftBackingColor = getRawSSoftBackingColor();', src)
        for event in ('onDidStartNavigationInPrimaryMainFrame',
                      'onDidFinishNavigationInPrimaryMainFrame', 'onContentChanged'):
            self.assertIn('clearRawSSoftWebColor();', method(src, 'public void ' + event + '('))
        self.assertIn('getToolbarHairline().setVisibility(INVISIBLE);', method(
            src, 'public void setTextureCaptureMode('))
        self.assertIn('&& super.shouldDrawHairline()', method(src, 'protected boolean shouldDrawHairline('))
        self.assertIn('snapshotDifference = ToolbarSnapshotDifference.THEME_COLOR;', src)
        self.assertIn('mToolbar.getRawSCapturedSoftBackingColor()', self.sources[change.CONTAINER])
        self.assertIn('mToolbarLayout instanceof ToolbarPhone phone', self.sources[change.COORD])
        layer = self.sources[change.LAYER_C]
        self.assertIn('gfx::LinearGradient mask(270);', layer)
        self.assertIn('mask.AddStep(1.f, 72);', layer)
        self.assertIn('toolbar_background_layer_->AddChild(raws_soft_shade_layer_);', layer)
        self.assertIn('raws_soft_shade_layer_->SetHideLayerAndSubtree(!show_raws_soft_shade)', layer)
        self.assertIn('raws_soft_backing_color_', method(
            self.sources[change.RESOURCE_C], 'std::unique_ptr<ui::Resource> ToolbarResource::CreateForCopy('))

    def test_jni_and_exact_layout_contract(self):
        java = self.sources[change.FACTORY_J]
        cxx = self.sources[change.FACTORY_C]
        self.assertEqual(10, len(re.findall(r'int \w+', java.split('public interface Natives')[1])))
        self.assertEqual(10, len(re.findall(r'int32_t \w+', cxx.split('JNI_ResourceFactory_')[1])))
        for path in change.OWNERS:
            self.assertNotIn('CompositorViewHolder', path)
            self.assertNotIn('ToolbarPositionController', path)
        src = self.sources[change.PHONE]
        paint = method(src, 'protected void dispatchDraw(Canvas canvas)')
        self.assertNotIn('setLayoutParams', paint)
        self.assertNotIn('notifyToolbarColorChanged', paint)
        self.assertIn('getRawSUnifiedPaintBounds', src)
        self.assertIn('0, 0, getWidth(), getHeight()', paint)

    def test_emitted_toolbar_observer_uses_pinned_type_imports(self):
        src = self.sources[change.PHONE]
        for symbol in ('org.chromium.content_public.browser.NavigationHandle',
                       'org.chromium.content_public.browser.WebContents',
                       'org.chromium.url.GURL'):
            self.assertEqual(src.splitlines().count(f'import {symbol};'), 1, symbol)
        for declaration in (
                'onDidStartNavigationInPrimaryMainFrame( Tab tab, NavigationHandle navigation)',
                'onDidFinishNavigationInPrimaryMainFrame( Tab tab, NavigationHandle navigation)',
                'onBackgroundColorChanged(Tab tab, int color)',
                'onPageLoadFinished(Tab tab, GURL url)',
                'onContentChanged(Tab tab)'):
            self.assertIn(declaration, ' '.join(src.split()))

    def test_actual_background_policy_in_jdk(self):
        java = shutil.which('java')
        if java is None:
            self.skipTest('No JDK')
        policy = method(self.sources[change.PHONE], 'private @ColorInt int getRawSSoftBackingColor(')
        with tempfile.TemporaryDirectory() as t:
            source = Path(t) / 'ShadowPolicyTest.java'
            source.write_text(JAVA_HEAD + policy + JAVA_TEST)
            subprocess.run([java, source], check=True)


JAVA_HEAD = r"""
class ShadowPolicyTest {
  @interface ColorInt {}
  static class Color {
    static final int TRANSPARENT=0;
    static int alpha(int c) { return c >>> 24; }
  }
  static class ChromeFeatureList {
    static final ChromeFeatureList sToolbarPhoneAnimationRefactor = new ChromeFeatureList();
    boolean enabled;
    boolean isEnabled() { return enabled; }
  }
  static class Contents {
    boolean dead;
    String committed = "https://one.test";
    boolean isDestroyed() { return dead; }
    String getLastCommittedUrl() { return committed; }
  }
  static class Tab {
    boolean home, loading;
    Contents c = new Contents();
    int color = 0xff223344;
    boolean isNativePage() { return home; }
    int getBackgroundColor() { return color; }
    Contents getWebContents() { return c; }
    boolean isLoading() { return loading; }
    String getUrl() { return "https://one.test"; }
  }
  static class Background { int getColor() { return 0xff353638; } }
  final Background mToolbarBackground = new Background();
  Tab mRawSPageObservedTab = new Tab();
  Contents mRawSSoftBackingContents;
  String mRawSSoftBackingCommittedUrl;
  int mRawSSoftBackingWebColor;
  static final int STATIC_TAB = 0;
  int mTopPaddingForEdgeToEdgeNtp, mTabSwitcherState;
  float mUrlFocusChangeFraction;
  boolean mRawSPageActionsActive=true, allowed=true, focus,
          mUrlFocusChangeInProgress, mInLayoutTransition, suppressed,
          mIsInLoadingPhaseFromNtpToWebpage, mBrandColorTransitionActive;
  boolean canUseRawSPageActions(){return allowed;}
  boolean urlHasFocus(){return focus;}
  boolean isToolbarHairlineSuppressed(){return suppressed;}
"""

JAVA_TEST = r"""
  static void check(boolean ok) { if (!ok) throw new AssertionError(); }
  public static void main(String[] args) {
    var t = new ShadowPolicyTest();
    // Even a color already cached on the tab cannot stand in for a current callback.
    check(t.getRawSSoftBackingColor() == 0xff353638);
    t.mRawSSoftBackingContents = t.mRawSPageObservedTab.c;
    t.mRawSSoftBackingCommittedUrl = t.mRawSPageObservedTab.c.committed;
    t.mRawSSoftBackingWebColor = t.mRawSPageObservedTab.color;
    check(t.getRawSSoftBackingColor() == 0xff223344);
    t.mRawSPageObservedTab.loading = true;
    check(t.getRawSSoftBackingColor() == 0xff353638);
    t.mRawSPageObservedTab.loading = false;
    t.mRawSPageObservedTab.c.committed = "https://stale.test";
    check(t.getRawSSoftBackingColor() == 0xff353638);
    t.mRawSPageObservedTab.c.committed = "https://one.test";
    t.mRawSSoftBackingWebColor = 0x50223344;
    check(t.getRawSSoftBackingColor() == 0xff353638);
    t.mRawSPageObservedTab.home = true;
    t.mRawSPageObservedTab.color = 0xff101011;
    check(t.getRawSSoftBackingColor() == 0xff101011);
    t.focus = true;
    check(t.getRawSSoftBackingColor() == 0);
    t.focus = false;
    t.mUrlFocusChangeFraction = .01f;
    check(t.getRawSSoftBackingColor() == 0);
    t.mUrlFocusChangeFraction = 0;
    t.mTabSwitcherState = 1;
    check(t.getRawSSoftBackingColor() == 0);
    t.mTabSwitcherState = 0;
    t.mInLayoutTransition = true;
    check(t.getRawSSoftBackingColor() == 0);
    t.mInLayoutTransition = false;
    t.mIsInLoadingPhaseFromNtpToWebpage = true;
    check(t.getRawSSoftBackingColor() == 0);
    t.mIsInLoadingPhaseFromNtpToWebpage = false;
    t.allowed = false;
    check(t.getRawSSoftBackingColor() == 0);
    t.allowed = true;
    ChromeFeatureList.sToolbarPhoneAnimationRefactor.enabled = true;
    check(t.getRawSSoftBackingColor() == 0);
  }
}
"""

if __name__ == '__main__':
    unittest.main()
