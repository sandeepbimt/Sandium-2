"""Source-backed host tests for the exact active private Chrome overlay."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import incognito_frozen_chrome as change
import seal

ROOT = Path(__file__).resolve().parents[1]
BASE = '16f95596b9316caa1a464c36845668761758b0e9'


def runtime(path):
    recipe = json.loads((ROOT / seal.RECIPE).read_text())['files']
    digest = recipe[path]['after_sha256']
    data = (ROOT / seal.IMAGE / digest).read_bytes()
    assert hashlib.sha256(data).hexdigest() == digest
    return data.decode()


def method(source, name):
    at = source.index(name + '(')
    start = max(0, source.rfind('\n', 0, at))
    head = source.index('{', at)
    close = source.index('\n    }', head)
    return source[start:close + 6]


class FrozenIncognitoChrome(unittest.TestCase):
    def test_toolbar_reuses_native_tab_path_for_private_ntp_and_web(self):
        src = runtime(change.TOOLBAR)
        # The call order inside this source ensures these are method declarations.
        action = method(src, 'canUseRawSPageActions')
        home = method(src[src.index('    private boolean isRawSUnifiedNativeHome'):],
                      'isRawSUnifiedNativeHome')
        private = method(src[src.index('    private boolean isRawSUnifiedPrivateNtp'):],
                         'isRawSUnifiedPrivateNtp')
        with tempfile.TemporaryDirectory() as work:
            p = Path(work, 'ToolbarPolicy.java')
            p.write_text('''
class ToolbarPolicy {
  static class ControlsPosition { static final int BOTTOM = 1; }
  static class Controls { int pos = 1; int getControlsPosition() { return pos; } }
  static class Refactor { boolean isEnabled() { return false; } }
  static class ChromeFeatureList {
    static Refactor sToolbarPhoneAnimationRefactor = new Refactor();
  }
  static class NativePage { String getHost() { return "newtab"; } }
  static class Tab {
    boolean otr, ntp, destroyed, error;
    String url = "https://example.test";
    boolean isNativePage() { return ntp; }
    boolean isDestroyed() { return destroyed; }
    boolean isOffTheRecord() { return otr; }
    boolean isShowingErrorPage() { return error; }
    NativePage getNativePage() { return ntp ? new NativePage() : null; }
    String getUrl() { return url; }
  }
  static class UrlUtilities {
    static boolean isHttpOrHttps(String s) { return s.startsWith("https://") || s.startsWith("http://"); }
  }
  static class BottomBarConfigUtils {
    static boolean isNtp(Tab t) { return t.ntp; }
  }
  boolean brand, offRecord, fakebox, mIsToolbarUiRefactorEnabled;
  Object mRawSPageForward = new Object(), mRawSAddressShield = new Object();
  Controls mBrowserControlsStateProvider = new Controls();
  int mRawSPageWidth = 420;
  Tab mRawSPageObservedTab = new Tab(), selected = mRawSPageObservedTab;
  boolean isIncognitoBranded() { return brand; }
  boolean isIncognito() { return offRecord; }
  boolean isLocationBarShownInNtp() { return fakebox; }
  ToolbarPolicy getToolbarDataProvider() { return this; }
  ToolbarPolicy getResources() { return this; }
  ToolbarPolicy getDisplayMetrics() { return this; }
  float density = 1f;
  Tab getTab() { return selected; }
''' + action + home.replace(
                'org.chromium.components.embedder_support.util.UrlConstants.NTP_HOST', '"newtab"')
                + private + '''
  static void expect(boolean v, boolean expected) {
    if (v != expected) throw new AssertionError("row != " + expected);
  }
  public static void main(String[] a) {
    var p = new ToolbarPolicy();
    var t = p.selected;
    // Regular web -> private model while old regular tab is still observed (fallback).
    expect(p.canUseRawSPageActions(), true);
    p.brand = p.offRecord = true;
    expect(p.canUseRawSPageActions(), false);
    // Open native private tab, then start visiting an HTTPS link before page swap.
    t.otr = t.ntp = true; t.url = "chrome://newtab/";
    expect(p.canUseRawSPageActions(), true);
    t.url = "https://example.test";
    expect(p.canUseRawSPageActions(), true);
    t.ntp = false;
    expect(p.canUseRawSPageActions(), true);
    t.url = "chrome://history"; expect(p.canUseRawSPageActions(), false);
    t.url = "https://example.test";
    p.mBrowserControlsStateProvider.pos = 0; expect(p.canUseRawSPageActions(), false);
    p.mBrowserControlsStateProvider.pos = 1;
    p.mRawSPageWidth = 339; expect(p.canUseRawSPageActions(), false);
    p.mRawSPageWidth = 420;
    t.error = true; expect(p.canUseRawSPageActions(), false); t.error = false;
    p.selected = new Tab(); expect(p.canUseRawSPageActions(), false);
    p.mRawSPageObservedTab = p.selected;
    p.offRecord = p.brand = false; expect(p.canUseRawSPageActions(), true);
  }
}
''')
            subprocess.run(['java', str(p)], check=True)
        self.assertIn('|| tab.isOffTheRecord())', src)
        self.assertIn('if (tab.isOffTheRecord()) return fallback | 0xff000000;', src)
        self.assertIn('mVisualState == VisualState.INCOGNITO', src)
        self.assertIn('if (!isRawSUnifiedPrivateNtp(tab)) return false;', src)
        self.assertIn('mLocationBarDataProvider.isIncognitoBranded()', runtime(change.LOCATION_PHONE))
        self.assertIn('mModel.set(StatusProperties.INCOGNITO_BADGE_VISIBLE, visible);',
                      runtime(change.STATUS))

    def test_native_private_menu_is_read_only_and_lock_safe(self):
        delegate = runtime(change.TABBED)
        self.assertIn('!tab.isIncognito()\n                && getMenuGroup()', delegate)
        policy = method(delegate, 'supportsRawSPrivateMenu')
        for expected in ('mActivityTabProvider.get()', '!tab.isDestroyed()', 'tab.isIncognito()',
                         'isIncognitoShowing()', '!isIncognitoReauthShowing()',
                         'getMenuGroup() == MenuGroup.PAGE_MENU'):
            self.assertIn(expected, policy)
        handler = runtime(change.HANDLER)
        # Settings must not become a private edit entry point.
        self.assertIn('if (!rawSMenuEligible() || isAppMenuShowing()', handler)
        self.assertIn('(rawSMenuEligible() || readOnlyPrivateMenu) && mModelList != null', handler)
        menu = runtime(change.MENU)
        self.assertIn('mSandiumReadOnlyPrivateMenu = false;', menu)
        self.assertIn('mSandiumRecentTabs,\n                    mSandiumReadOnlyPrivateMenu', menu)
        pager = runtime(change.PAGED)
        self.assertEqual(2, pager.count('mDraft = mSaved.copy(); render();'))
        self.assertEqual(2, pager.count('if (!mReadOnlyPrivateMenu) {\n')-1)
        self.assertIn('if (mReadOnlyPrivateMenu || mDraft == null || mWriteInFlight) return;', pager)
        self.assertIn('if (!mReadOnlyPrivateMenu && mUncataloguedNativeRow >= 0)', pager)
        self.assertIn('() -> showNative(mUncataloguedNativeRow)', pager)
        self.assertIn('() -> { mAllMenu = false; render(); }', pager)
        self.assertIn('if (mReadOnlyPrivateMenu && mAllMenu)', pager)
        self.assertIn('titleParams.setMarginEnd(backWidth)', pager)
        self.assertIn('handler.onItemClick(entry.model, null);', pager)
        self.assertIn('Configuration.UI_MODE_NIGHT_YES', pager)

    def test_private_home_keeps_native_owner_and_only_paints_mark(self):
        page, view = runtime(change.NTP_PAGE), runtime(change.NTP_VIEW)
        self.assertIn('if (!mProfile.isOffTheRecord())', page)
        self.assertIn('BottomBarConfigUtils.shouldUseRawSUnifiedPhoneToolbar(context)', page)
        self.assertIn('? Color.BLACK : context.getColor(R.color.ntp_bg_incognito)', page)
        self.assertIn('initWithView(mIncognitoNewTabPageView);', page)
        self.assertIn('mIncognitoNewTabPageView.getScrollView(), edgeToEdgeControllerSupplier',
                      page)
        paint = method(view, 'showRawSPrivateHome')
        self.assertIn('setBackgroundColor(Color.BLACK);', paint)
        self.assertIn('mScrollView.setVisibility(View.INVISIBLE);', paint)
        self.assertIn('R.drawable.raws_frozen_shields_mark', paint)
        self.assertIn('Gravity.CENTER', paint)
        for unsupported in ('TextView', 'new SearchBox', 'setOnClickListener', 'Wallpaper', 'Mvt'):
            self.assertNotIn(unsupported, paint)
        self.assertIn('R.string.accessibility_new_incognito_tab_page', view)
        self.assertIn('mManager.onLoadingComplete();', view)

    def test_reviewed_component_postimages_and_active_admission(self):
        before = json.loads(seal.git('show', BASE + ':' + seal.RECIPE))['files']
        after = json.loads((ROOT / seal.RECIPE).read_text())['files']
        self.assertTrue(change.TRACKED.keys().isdisjoint(before))
        self.assertTrue(change.TRACKED.keys() <= after.keys())
        for path, old in change.OWNERS.items():
            self.assertEqual(old, before[path]['after_sha256'])
            result = change.transform(path, (ROOT / seal.IMAGE / old).read_bytes())
            self.assertEqual((ROOT / seal.IMAGE / seal.digest(result)).read_bytes(), result)
        a = json.loads((ROOT / seal.ADMISSION).read_text())
        self.assertEqual(seal.digest((ROOT / seal.RECIPE).read_bytes()), a['manifest_sha256'])
        self.assertTrue(change.TRACKED.keys() <= set(a['extra_tracked']))


if __name__ == '__main__':
    unittest.main()
