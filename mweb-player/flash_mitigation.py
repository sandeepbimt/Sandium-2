"""Local RawS Home-to-web transient browser backing; no page/renderer paint changes."""
from __future__ import annotations

import hashlib

TAB = "chrome/android/java/src/org/chromium/chrome/browser/tab/TabImpl.java"
OBSERVER = ("chrome/android/java/src/org/chromium/chrome/browser/tab/"
            "TabWebContentsObserver.java")
TAB_SHA = "40f6374e48c47607f526cb9e542977f18fd48e22b376cdb6c061d96113eb2750"
OBSERVER_SHA = "4621d6935a6782edb37a446bb0885545382dbe0dae3b880c125be3d28112277d"

METHODS = """
    // Protect only the browser-owned backing after this specific native Home is
    // replaced by a committed document. No page/renderer background override.
    void rawsOnTopLevelNavigationStarted(NavigationHandle navigation) {
        if (!navigation.isInPrimaryMainFrame() || navigation.isSameDocument()) return;
        rawsClearHomeBacking(false);
        Context context = getActivityContext().get();
        if (!(mNativePage instanceof NewTabPage)
                || mNativePage.isFrozen() || isHidden() || isIncognito()
                || context == null || !"io.github.sandeepbimt.raws".equals(context.getPackageName())
                || (context.getResources().getConfiguration().uiMode
                                & Configuration.UI_MODE_NIGHT_MASK)
                        != Configuration.UI_MODE_NIGHT_YES
                || navigation.isRendererInitiated() || navigation.isHistory()
                || !rawsWebDestination(navigation.getUrl())) {
            return;
        }
        mRawSHomeBackingNavigation = navigation.getNavigationId();
    }

    void rawsOnTopLevelNavigationFinishing(NavigationHandle navigation) {
        if (mRawSHomeBackingNavigation == 0
                || mRawSHomeBackingNavigation != navigation.getNavigationId()) {
            return;
        }
        NativePage home = mNativePage;
        if (!(home instanceof NewTabPage) || home.isFrozen() || isHidden()
                || navigation.isSameDocument() || navigation.isHistory()
                || !navigation.hasCommitted() || navigation.isErrorPage()
                || navigation.errorCode() != NetError.OK || navigation.isDownload()
                || navigation.isPdf() || !rawsWebDestination(navigation.getUrl())) {
            rawsClearHomeBacking(false);
            return;
        }
        mRawSHomeBackingUrl = navigation.getUrl();
        int color = home.getBackgroundColor();
        mRawSHomeBackingColor = Color.alpha(color) == 255 && Color.luminance(color) < 0.35f
                ? color : 0xff121212;
    }

    private static boolean rawsWebDestination(GURL url) {
        return url.isValid() && ("https".equals(url.getScheme()) || "http".equals(url.getScheme()));
    }

    void rawsOnPrimaryPagePresented(@Nullable GURL completedUrl) {
        GURL expected = mRawSHomeBackingUrl;
        WebContents contents = mWebContents;
        if (expected != null && mNativePage == null && contents != null
                && expected.equals(contents.getLastCommittedUrl())
                && (completedUrl == null
                        || (!contents.isLoading() && expected.equals(completedUrl)))) {
            rawsClearHomeBacking(true);
        }
    }

    void rawsClearHomeBacking(boolean readDestinationColor) {
        boolean wasHolding = mRawSHomeBackingUrl != null;
        mRawSHomeBackingNavigation = 0;
        mRawSHomeBackingUrl = null;
        if (!wasHolding) return;
        if (readDestinationColor && mWebContents != null) {
            mWebContentBackgroundColor = mWebContents.getBackgroundColor();
        }
        onBackgroundColorChanged();
    }
"""


def _source(raw: bytes, want: str) -> str:
    if hashlib.sha256(raw).hexdigest() != want:
        raise ValueError("unexpected #1515 Home handoff input")
    return raw.decode("utf-8")


def _once(s: str, old: str, new: str) -> str:
    if s.count(old) != 1:
        raise ValueError("missing or ambiguous pinned lifecycle seam: " + old)
    return s.replace(old, new, 1)


def transform_tab(raw: bytes) -> bytes:
    s = _source(raw, TAB_SHA)
    for old, new in (
        ('import android.content.Context;', 'import android.content.Context;\n'
         'import android.content.res.Configuration;\nimport android.graphics.Color;'),
        ('import org.chromium.chrome.browser.night_mode.NightModeUtils;',
         'import org.chromium.chrome.browser.night_mode.NightModeUtils;\n'
         'import org.chromium.chrome.browser.ntp.NewTabPage;'),
        ('import org.chromium.content_public.browser.NavigationResult;',
         'import org.chromium.content_public.browser.NavigationHandle;\n'
         'import org.chromium.content_public.browser.NavigationResult;'),
        ('import org.chromium.ui.UiUtils;',
         'import org.chromium.net.NetError;\nimport org.chromium.ui.UiUtils;'),
        ('    private int mWebContentBackgroundColor;',
         '    private int mWebContentBackgroundColor;\n'
         '    private long mRawSHomeBackingNavigation;\n'
         '    private @Nullable GURL mRawSHomeBackingUrl;\n'
         '    private @ColorInt int mRawSHomeBackingColor;'),
        ('        return mWebContentBackgroundColor;\n    }',
         '        GURL pendingHomeDestination = mRawSHomeBackingUrl;\n'
         '        WebContents contents = mWebContents;\n'
         '        if (pendingHomeDestination != null && contents != null\n'
         '                && pendingHomeDestination.equals(contents.getLastCommittedUrl())) {\n'
         '            return mRawSHomeBackingColor;\n        }\n'
         '        return mWebContentBackgroundColor;\n    }'),
        ('            mIsHidden = true;\n            updateInteractableState();',
         '            mIsHidden = true;\n            rawsClearHomeBacking(false);\n'
         '            updateInteractableState();'),
        ('        mWindowAndroid = windowAndroid;\n        initAutofillPrefObserver();',
         '        if (mWindowAndroid != windowAndroid) rawsClearHomeBacking(false);\n'
         '        mWindowAndroid = windowAndroid;\n        initAutofillPrefObserver();'),
        ('    void handleTabCrash() {\n        mIsLoading = false;',
         '    void handleTabCrash() {\n        rawsClearHomeBacking(false);\n'
         '        mIsLoading = false;'),
        ('\n    /** Called to notify when the page had painted something non-empty. */',
         '\n' + METHODS + '\n    /** Called to notify when the page had painted something non-empty. */'),
    ):
        s = _once(s, old, new)
    return s.encode()


def transform_observer(raw: bytes) -> bytes:
    s = _source(raw, OBSERVER_SHA)
    for old, new in (
        ('    public void cleanupWebContents(WebContents webContents) {\n',
         '    public void cleanupWebContents(WebContents webContents) {\n'
         '        mTab.rawsClearHomeBacking(false);\n'),
        ('        public void didStartNavigationInPrimaryMainFrame(NavigationHandle navigation) {\n',
         '        public void didStartNavigationInPrimaryMainFrame(NavigationHandle navigation) {\n'
         '            mTab.rawsOnTopLevelNavigationStarted(navigation);\n'),
        ('        public void didFinishNavigationInPrimaryMainFrame(NavigationHandle navigation) {\n',
         '        public void didFinishNavigationInPrimaryMainFrame(NavigationHandle navigation) {\n'
         '            mTab.rawsOnTopLevelNavigationFinishing(navigation);\n'),
        ('        @Override\n        public void loadProgressChanged(float progress) {',
         '        @Override\n'
         '        public void didStopLoading(GURL url, boolean isKnownValid) {\n'
         '            // A successful blank document may have no non-empty paint.\n'
         '            if (isKnownValid) mTab.rawsOnPrimaryPagePresented(url);\n'
         '        }\n\n'
         '        @Override\n        public void loadProgressChanged(float progress) {'),
        ('            mTab.notifyDidFirstVisuallyNonEmptyPaint();\n',
         '            mTab.rawsOnPrimaryPagePresented(null);\n'
         '            mTab.notifyDidFirstVisuallyNonEmptyPaint();\n'),
    ):
        s = _once(s, old, new)
    return s.encode()


OWNERS = {TAB: TAB_SHA, OBSERVER: OBSERVER_SHA}


def transform(path: str, data: bytes) -> bytes:
    if path == TAB:
        return transform_tab(data)
    if path == OBSERVER:
        return transform_observer(data)
    raise ValueError("unknown #1515 Home handoff owner: " + path)
