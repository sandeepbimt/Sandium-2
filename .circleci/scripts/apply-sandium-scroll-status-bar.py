#!/usr/bin/env python3
"""EXPERIMENTAL stable Android16 web underlap. Native compile/device validation required.
See docs/STATUS_BAR_RESEARCH.md before integration.
"""
import argparse
from pathlib import Path

FILES = {
 'EdgeToEdgeControllerTest.java': 'chrome/browser/ui/android/edge_to_edge/internal/junit/src/org/chromium/chrome/browser/ui/edge_to_edge/EdgeToEdgeControllerTest.java',
 'EdgeToEdgeLayoutUnitTest.java': 'ui/edge_to_edge/android/junit/src/org/chromium/ui/edge_to_edge/layout/EdgeToEdgeLayoutUnitTest.java',
 'EdgeToEdgeSystemBarColorHelperUnitTest.java': 'ui/edge_to_edge/android/junit/src/org/chromium/ui/edge_to_edge/EdgeToEdgeSystemBarColorHelperUnitTest.java',

 'EdgeToEdgeUtils.java': 'chrome/browser/ui/android/edge_to_edge/java/src/org/chromium/chrome/browser/ui/edge_to_edge/EdgeToEdgeUtils.java',
 'EdgeToEdgeLayoutCoordinator.java': 'ui/edge_to_edge/android/java/src/org/chromium/ui/edge_to_edge/layout/EdgeToEdgeLayoutCoordinator.java',
 'EdgeToEdgeBaseLayout.java': 'ui/edge_to_edge/android/java/src/org/chromium/ui/edge_to_edge/layout/EdgeToEdgeBaseLayout.java',

 'EdgeToEdgeControllerImpl.java': 'chrome/browser/ui/android/edge_to_edge/internal/java/src/org/chromium/chrome/browser/ui/edge_to_edge/EdgeToEdgeControllerImpl.java',
 'InsetObserver.java': 'ui/android/java/src/org/chromium/ui/insets/InsetObserver.java',
 'EdgeToEdgeSystemBarColorHelper.java': 'ui/edge_to_edge/android/java/src/org/chromium/ui/edge_to_edge/EdgeToEdgeSystemBarColorHelper.java',
}

def replace(s, old, new):
    if new in s: return s
    if s.count(old) != 1: raise RuntimeError('Unexpected pinned source: '+old[:100])
    return s.replace(old,new,1)

def transform(name,s):
    # Normalize the isolated rollback gate before idempotence checks.
    s=s.replace("SANDIUM_TOP_UNDERLAP_EXPERIMENT = false;", "SANDIUM_TOP_UNDERLAP_EXPERIMENT = true;")
    if name == 'InsetObserver.java':
        s=replace(s,'    private int mBottomInsetsForEdgeToEdge;', '    private int mBottomInsetsForEdgeToEdge;\n    private int mSandiumTopInsetForEdgeToEdge;')
        s=replace(s,'        newSafeArea.bottom += mBottomInsetsForEdgeToEdge;', '        newSafeArea.bottom += mBottomInsetsForEdgeToEdge;\n        newSafeArea.top = Math.max(newSafeArea.top, mSandiumTopInsetForEdgeToEdge);')
        s=replace(s,'    public void updateBottomInsetForEdgeToEdge(int bottomInset) {', '''    /** Sandium: forward top underlap to Blink CSS env(safe-area-inset-top). */
    public int getSandiumTopInsetForEdgeToEdge() {
        return mSandiumTopInsetForEdgeToEdge;
    }

    public void updateSandiumTopInsetForEdgeToEdge(int topInset) {
        topInset = Math.max(0, topInset);
        if (mSandiumTopInsetForEdgeToEdge == topInset) return;
        mSandiumTopInsetForEdgeToEdge = topInset;
        updateCurrentSafeArea();
    }

    public void updateBottomInsetForEdgeToEdge(int bottomInset) {''')
    elif name == 'EdgeToEdgeSystemBarColorHelper.java':
        s=replace(s,'    private final Window mWindow;', '''    private final Window mWindow;
    // The inset owner is the only writer. Keep the ordinary requested color intact for restore.
    private boolean mSandiumScrollUnderStatusBar;
    private boolean mSandiumRestoringStatusBar;

    /** Translucent black protection, not an opaque replacement of the page content. */
    public void setSandiumScrollUnderStatusBar(boolean active) {
        if (mSandiumScrollUnderStatusBar == active) return;
        mSandiumRestoringStatusBar = mSandiumScrollUnderStatusBar && !active;
        mSandiumScrollUnderStatusBar = active;
        updateStatusBarColor();
        mSandiumRestoringStatusBar = false;
    }
''')
        s=replace(s,'        int windowStatusBarColor = mStatusBarColor;', '''        int effectiveColor = mSandiumScrollUnderStatusBar ? 0x00000000 : mStatusBarColor;
        int windowStatusBarColor = effectiveColor;''')
        s=replace(s,'                delegateHelper.setStatusBarColor(mStatusBarColor);','                delegateHelper.setStatusBarColor(effectiveColor);')
        s=replace(s,'        if (mForceLightStatusBarColor) {','        if (mForceLightStatusBarColor || mSandiumScrollUnderStatusBar) {')
        s=replace(s,'        return mCanColorStatusBarColor;','        return mCanColorStatusBarColor || mSandiumScrollUnderStatusBar || mSandiumRestoringStatusBar;')
    elif name == 'EdgeToEdgeUtils.java':
        s=replace(s,'        return ChromeFeatureList.sEdgelessTopInset.isEnabled();',
            '        return ChromeFeatureList.sEdgelessTopInset.isEnabled()\n                || isSandiumTopUnderlapExperimentEnabled();')
        s=replace(s,'    public static boolean isEdgelessTopInsetEnabled() {', """    /** Isolated rollback gate. Trial only: Android 16 unified inset architecture. */
    public static boolean isSandiumTopUnderlapExperimentEnabled() {
        return SANDIUM_TOP_UNDERLAP_EXPERIMENT && Build.VERSION.SDK_INT >= 36;
    }

    private static final boolean SANDIUM_TOP_UNDERLAP_EXPERIMENT = true;

    public static boolean isEdgelessTopInsetEnabled() {""")
    elif name == 'EdgeToEdgeLayoutCoordinator.java':
        s=replace(s,'        mView.setStatusBarInsets(statusBarInsets);', """        mView.setStatusBarInsets(statusBarInsets);
        // This geometry is independent of the consumed status/cutout insets. It paints only;
        // it must NOT add padding back to the web surface.
        mView.setSandiumTopProtectionHeight(mInsetObserver == null ? 0
                : mInsetObserver.getSandiumTopInsetForEdgeToEdge());""")
    elif name == 'EdgeToEdgeBaseLayout.java':
        s=replace(s,'    private boolean mEnableExtraEdgeToEdgeLogging;', """    private boolean mEnableExtraEdgeToEdgeLogging;
    private int mSandiumTopProtectionHeight;
    private final Paint mSandiumTopProtectionPaint = new Paint();

    int getSandiumTopProtectionHeightForTesting() {
        return mSandiumTopProtectionHeight;
    }

    void setSandiumTopProtectionHeight(int height) {
        height = Math.max(0, height);
        if (mSandiumTopProtectionHeight == height) return;
        mSandiumTopProtectionHeight = height;
        mSandiumTopProtectionPaint.setShader(height == 0 ? null :
                new android.graphics.LinearGradient(0, 0, 0, height * 1.5f,
                        new int[] {0xB3000000, 0x99000000, 0x00000000},
                        new float[] {0f, 0.67f, 1f}, android.graphics.Shader.TileMode.CLAMP));
        invalidate();
    }

    @Override
    protected void dispatchDraw(Canvas canvas) {
        super.dispatchDraw(canvas);
        // Draw AFTER the web surface, not in onDraw behind children. Non-interactive paint.
        if (mSandiumTopProtectionHeight > 0) {
            canvas.drawRect(0, 0, getWidth(), mSandiumTopProtectionHeight * 1.5f,
                    mSandiumTopProtectionPaint);
        }
    }
""")
    elif name == 'EdgeToEdgeLayoutUnitTest.java':
        s=replace(s,'    private void initialize(InsetObserver insetObserver, boolean useBackupNavbarInsets) {', """    @Test
    public void testSandiumConsumedTopPreservesProtectionNotPadding() {
        initializePortraitLayout(false);
        doReturn(STATUS_BAR_SIZE).when(mInsetObserver).getSandiumTopInsetForEdgeToEdge();
        var insets = new WindowInsetsCompat.Builder()
                .setInsets(STATUS_BARS, Insets.NONE)
                .setInsets(NAVIGATION_BARS, Insets.of(0, 0, 0, NAV_BAR_SIZE)).build();
        mEdgeToEdgeLayoutCoordinator.onApplyWindowInsets(mEdgeToEdgeLayout, insets);
        measureAndLayoutRootView(400, 600);
        assertPaddings(0, 0, 0, NAV_BAR_SIZE);
        assertEquals(STATUS_BAR_SIZE,
                mEdgeToEdgeLayout.getSandiumTopProtectionHeightForTesting());
        assertEquals(new Rect(), mEdgeToEdgeLayout.getStatusBarRectForTesting());

        doReturn(0).when(mInsetObserver).getSandiumTopInsetForEdgeToEdge();
        var restored = new WindowInsetsCompat.Builder(insets)
                .setInsets(STATUS_BARS, Insets.of(0, STATUS_BAR_SIZE, 0, 0)).build();
        mEdgeToEdgeLayoutCoordinator.onApplyWindowInsets(mEdgeToEdgeLayout, restored);
        measureAndLayoutRootView(400, 600);
        assertPaddings(0, STATUS_BAR_SIZE, 0, NAV_BAR_SIZE);
        assertEquals(0, mEdgeToEdgeLayout.getSandiumTopProtectionHeightForTesting());
    }

    @Test
    public void testSandiumProtectionRejectsNegativeHeight() {
        initializePortraitLayout(false);
        mEdgeToEdgeLayout.setSandiumTopProtectionHeight(-1);
        assertEquals(0, mEdgeToEdgeLayout.getSandiumTopProtectionHeightForTesting());
    }

    private void initialize(InsetObserver insetObserver, boolean useBackupNavbarInsets) {""")
    elif name == 'EdgeToEdgeSystemBarColorHelperUnitTest.java':
        s=replace(s,'    private void initEdgeToEdgeColorHelper() {', """    @Test
    public void testSandiumUnderlapRestoresLatestRequestedColor() {
        initEdgeToEdgeColorHelper();
        mDelegateHelperSupplier.set(mDelegateColorHelper);
        mEdgeToEdgeColorHelper.setStatusBarColor(Color.RED);
        clearInvocations(mDelegateColorHelper, mWindowInsetsController);
        mEdgeToEdgeColorHelper.setSandiumScrollUnderStatusBar(true);
        verify(mDelegateColorHelper).setStatusBarColor(Color.TRANSPARENT);
        verifyStatusBarAppearance(false);
        mEdgeToEdgeColorHelper.setStatusBarColor(Color.WHITE);
        clearInvocations(mDelegateColorHelper);
        mEdgeToEdgeColorHelper.setSandiumScrollUnderStatusBar(false);
        verify(mDelegateColorHelper).setStatusBarColor(Color.WHITE);
        verifyStatusBarAppearance(true);
    }

    private void initEdgeToEdgeColorHelper() {""")
    elif name == 'EdgeToEdgeControllerTest.java':
        s=replace(s,'    private Activity mActivity;', """    // Lightweight activity whose name matches the production eligibility boundary. This tests
    // controller behavior without depending on the heavyweight chrome/android activity GN target.
    public static class ChromeTabbedActivity extends AppCompatActivity {}

    @Test
    @Config(sdk = 36, qualifiers = "sw400dp-port")
    @EnableFeatures({ChromeFeatureList.EDGE_TO_EDGE_EVERYWHERE,
            ChromeFeatureList.EDGELESS_TOP_INSET})
    public void testSandiumActiveUnderlapKeyboardCutoutAndUrlRestoration() {
        mEdgeToEdgeControllerImpl.destroy();
        mTabProvider.set(null);
        mActivity = Robolectric.buildActivity(ChromeTabbedActivity.class).setup().get();
        var colorHelper = Mockito.mock(
                org.chromium.ui.edge_to_edge.EdgeToEdgeSystemBarColorHelper.class);
        doReturn(colorHelper).when(mEdgeToEdgeManager).getEdgeToEdgeSystemBarColorHelper();
        when(mTab.getUrl()).thenReturn(new GURL("https://example.com/"));
        when(mLayoutManager.getActiveLayoutType()).thenReturn(LayoutType.BROWSING);
        when(mBrowserControlsStateProvider.getControlsPosition())
                .thenReturn(BrowserControlsStateProvider.ControlsPosition.TOP);
        when(mBrowserControlsStateProvider.getTopControlsHeight()).thenReturn(100);
        mEdgeToEdgeControllerImpl = new EdgeToEdgeControllerImpl(
                mActivity, mWindowAndroid, mTabProvider, mOsWrapper, mEdgeToEdgeManager,
                mBrowserControlsStateProvider, mLayoutManagerSupplier, mFullscreenManager);
        mEdgeToEdgeControllerImpl.addObserver(mTopInsetObserver);
        mTabProvider.set(mTab);
        var active = mEdgeToEdgeControllerImpl.handleWindowInsets(
                mViewMock, SYSTEM_BARS_WINDOW_INSETS);
        assertTrue(mEdgeToEdgeControllerImpl.isDrawingToTopEdge());
        assertEquals(Insets.NONE, active.getInsets(WindowInsetsCompat.Type.statusBars()));
        verify(colorHelper, atLeastOnce()).setSandiumScrollUnderStatusBar(true);
        verify(mInsetObserver, atLeastOnce()).updateSandiumTopInsetForEdgeToEdge(TOP_INSET);

        var keyboard = mEdgeToEdgeControllerImpl.handleWindowInsets(
                mViewMock, SYSTEM_BARS_WINDOW_INSETS_WITH_KEYBOARD);
        assertFalse(mEdgeToEdgeControllerImpl.isDrawingToTopEdge());
        assertEquals(STATUS_BAR_INSETS, keyboard.getInsets(WindowInsetsCompat.Type.statusBars()));
        verify(colorHelper, atLeastOnce()).setSandiumScrollUnderStatusBar(false);
        verify(mInsetObserver, atLeastOnce()).updateSandiumTopInsetForEdgeToEdge(0);

        mEdgeToEdgeControllerImpl.handleWindowInsets(mViewMock, SYSTEM_BARS_WINDOW_INSETS);
        assertTrue(mEdgeToEdgeControllerImpl.isDrawingToTopEdge());
        var cutout = new WindowInsetsCompat.Builder(SYSTEM_BARS_WINDOW_INSETS)
                .setInsets(WindowInsetsCompat.Type.displayCutout(), Insets.of(1, 0, 0, 0))
                .build();
        var excluded = mEdgeToEdgeControllerImpl.handleWindowInsets(mViewMock, cutout);
        assertFalse(mEdgeToEdgeControllerImpl.isDrawingToTopEdge());
        assertEquals(Insets.of(1, 0, 0, 0),
                excluded.getInsets(WindowInsetsCompat.Type.displayCutout()));

        mEdgeToEdgeControllerImpl.handleWindowInsets(mViewMock, SYSTEM_BARS_WINDOW_INSETS);
        assertTrue(mEdgeToEdgeControllerImpl.isDrawingToTopEdge());
        verify(mTab, atLeastOnce()).addObserver(mTabObserverArgumentCaptor.capture());
        when(mTab.getUrl()).thenReturn(new GURL("chrome://newtab/"));
        mTabObserverArgumentCaptor.getValue().onUrlUpdated(mTab);
        assertFalse(mEdgeToEdgeControllerImpl.isDrawingToTopEdge());
    }

    @Test
    public void testSandiumTopGeometryRejectsUnsafeCutoutsAndCaption() {
        assertTrue(EdgeToEdgeControllerImpl.isSandiumTopGeometrySupported(
                SYSTEM_INSETS, Insets.NONE, Insets.NONE));
        assertTrue(EdgeToEdgeControllerImpl.isSandiumTopGeometrySupported(
                SYSTEM_INSETS, Insets.of(0, TOP_INSET, 0, 0), Insets.NONE));
        for (Insets cutout : new Insets[] {Insets.of(1, 0, 0, 0),
                Insets.of(0, 0, 1, 0), Insets.of(0, 0, 0, 1),
                Insets.of(0, TOP_INSET + 1, 0, 0)}) {
            assertFalse(EdgeToEdgeControllerImpl.isSandiumTopGeometrySupported(
                    SYSTEM_INSETS, cutout, Insets.NONE));
        }
        assertFalse(EdgeToEdgeControllerImpl.isSandiumTopGeometrySupported(
                SYSTEM_INSETS, Insets.NONE, Insets.of(0, 1, 0, 0)));
        assertFalse(EdgeToEdgeControllerImpl.isSandiumTopGeometrySupported(
                Insets.NONE, Insets.NONE, Insets.NONE));
    }

    @Test
    public void testSandiumWebEligibilityAndRestorationConditions() {
        when(mTab.getUrl()).thenReturn(new GURL("https://example.com/"));
        when(mBrowserControlsStateProvider.getControlsPosition())
                .thenReturn(BrowserControlsStateProvider.ControlsPosition.TOP);
        when(mBrowserControlsStateProvider.getTopControlsHeight()).thenReturn(100);
        assertTrue(EdgeToEdgeControllerImpl.isSandiumPageAndControlsSupported(
                mTab, mBrowserControlsStateProvider));
        when(mTab.getUrl()).thenReturn(new GURL("chrome://newtab/"));
        assertFalse(EdgeToEdgeControllerImpl.isSandiumPageAndControlsSupported(
                mTab, mBrowserControlsStateProvider));
        when(mTab.getUrl()).thenReturn(new GURL("https://example.com/"));
        when(mTab.isNativePage()).thenReturn(true);
        assertFalse(EdgeToEdgeControllerImpl.isSandiumPageAndControlsSupported(
                mTab, mBrowserControlsStateProvider));
        when(mTab.isNativePage()).thenReturn(false);
        when(mTab.isIncognito()).thenReturn(true);
        assertFalse(EdgeToEdgeControllerImpl.isSandiumPageAndControlsSupported(
                mTab, mBrowserControlsStateProvider));
        when(mTab.isIncognito()).thenReturn(false);
        when(mTab.isShowingErrorPage()).thenReturn(true);
        assertFalse(EdgeToEdgeControllerImpl.isSandiumPageAndControlsSupported(
                mTab, mBrowserControlsStateProvider));
        when(mTab.isShowingErrorPage()).thenReturn(false);
        when(mBrowserControlsStateProvider.isVisibilityForced()).thenReturn(true);
        assertFalse(EdgeToEdgeControllerImpl.isSandiumPageAndControlsSupported(
                mTab, mBrowserControlsStateProvider));
        when(mBrowserControlsStateProvider.isVisibilityForced()).thenReturn(false);
        when(mBrowserControlsStateProvider.getControlsPosition())
                .thenReturn(BrowserControlsStateProvider.ControlsPosition.BOTTOM);
        assertFalse(EdgeToEdgeControllerImpl.isSandiumPageAndControlsSupported(
                mTab, mBrowserControlsStateProvider));
        when(mBrowserControlsStateProvider.getControlsPosition())
                .thenReturn(BrowserControlsStateProvider.ControlsPosition.TOP);
        assertTrue(EdgeToEdgeControllerImpl.isSandiumPageAndControlsSupported(
                mTab, mBrowserControlsStateProvider));
    }

    private Activity mActivity;""")
    elif name == 'EdgeToEdgeControllerImpl.java':
        s=replace(s,'    private final boolean mIsEdgelessTopInsetEnabled;', """    private final boolean mIsEdgelessTopInsetEnabled;
    private boolean mSandiumScrollUnderStatusBar;
    private boolean mSandiumNonBrowsingTransition;
    private boolean mSandiumCrashedTab;
    private Insets mSandiumCutoutInsets = Insets.NONE;
    private Insets mSandiumCaptionInsets = Insets.NONE;

    @VisibleForTesting
    static boolean isSandiumTopGeometrySupported(
            Insets systemInsets, Insets cutoutInsets, Insets captionInsets) {
        // Trial deliberately declines cutouts extending beyond status-bar protection.
        // Never consume a side/bottom cutout or a desktop caption to manufacture underlap.
        return systemInsets.top > 0 && systemInsets.left == 0 && systemInsets.right == 0
                && cutoutInsets.left == 0 && cutoutInsets.right == 0 && cutoutInsets.bottom == 0
                && cutoutInsets.top <= systemInsets.top && captionInsets.equals(Insets.NONE);
    }

    @VisibleForTesting
    static boolean isSandiumPageAndControlsSupported(
            @Nullable Tab tab, BrowserControlsStateProvider controls) {
        if (tab == null || tab.isNativePage() || tab.isIncognito() || tab.isShowingErrorPage()
                || tab.getWebContents() == null) return false;
        String scheme = tab.getUrl().getScheme();
        if (!"https".equals(scheme) && !"http".equals(scheme)) return false;
        return controls.getControlsPosition() == BrowserControlsStateProvider.ControlsPosition.TOP
                && controls.getTopControlsHeight() > 0
                && controls.getTopControlsMinHeightOffset() == 0
                && !controls.isVisibilityForced();
    }

    private boolean shouldSandiumUnderlap(@Nullable Tab tab) {
        if (!EdgeToEdgeUtils.isSandiumTopUnderlapExperimentEnabled()
                || !mDisablePaddingRootView || mSystemInsets.top <= 0) return false;
        if (!"ChromeTabbedActivity".equals(mActivity.getClass().getSimpleName())) return false;
        if (mActivity.isInMultiWindowMode() || mActivity.isInPictureInPictureMode()) return false;
        var config = mActivity.getResources().getConfiguration();
        if (config.smallestScreenWidthDp >= 600
                || config.orientation != android.content.res.Configuration.ORIENTATION_PORTRAIT) {
            return false;
        }
        if (EdgeToEdgeUtils.hasTappableNavigationBar(mActivity.getWindow())) return false;
        if (mStatusIndicatorVisible || mSandiumNonBrowsingTransition || mSandiumCrashedTab
                || mFullscreenManager == null
                || mFullscreenManager.getPersistentFullscreenMode()) return false;
        if (mLayoutManager == null || mLayoutManager.getActiveLayoutType() != LayoutType.BROWSING) {
            return false;
        }
        if (mKeyboardInsets != null && mKeyboardInsets.bottom > 0) return false;
        return isSandiumTopGeometrySupported(
                        mSystemInsets, mSandiumCutoutInsets, mSandiumCaptionInsets)
                && mBrowserControlsStateProvider != null
                && isSandiumPageAndControlsSupported(tab, mBrowserControlsStateProvider);
    }

    private void clearSandiumUnderlapBeforeInsetsBypass() {
        if (!mSandiumScrollUnderStatusBar) return;
        mSandiumScrollUnderStatusBar = false;
        mConsumeTopInset = false;
        mEdgeToEdgeManager.getEdgeToEdgeSystemBarColorHelper()
                .setSandiumScrollUnderStatusBar(false);
        mInsetObserver.updateSandiumTopInsetForEdgeToEdge(0);
        int layoutType = mLayoutManager == null ? LayoutType.NONE
                : mLayoutManager.getActiveLayoutType();
        for (var observer : mTopInsetObservers) {
            observer.onToEdgeChange(mSystemInsets.top, false, layoutType);
        }
        // The untouched incoming insets will restore root padding in the unified layout.
    }

    private void refreshSandiumUnderlap() {
        if (mInsetObserver != null
                && shouldSandiumUnderlap(mCurrentTab) != mSandiumScrollUnderStatusBar) {
            mInsetObserver.retriggerOnApplyWindowInsets();
        }
    }

    @Override
    public void onControlsPositionChanged(int controlsPosition) {
        refreshSandiumUnderlap();
    }
""")
        s=replace(s,'                    public void onContentViewScrollingStateChanged(boolean scrolling) {', """                    public void onUrlUpdated(Tab tab) {
                        refreshSandiumUnderlap();
                    }

                    @Override
                    public void onPageLoadFailed(Tab tab, int errorCode) {
                        refreshSandiumUnderlap();
                    }

                    @Override
                    public void onPageLoadFinished(Tab tab, org.chromium.url.GURL url) {
                        refreshSandiumUnderlap();
                    }

                    @Override
                    public void onContentViewScrollingStateChanged(boolean scrolling) {""")
        s=replace(s,'                    public void onCrash(Tab tab) {', """                    public void onCrash(Tab tab) {
                        mSandiumCrashedTab = true;
                        refreshSandiumUnderlap();""")
        s=replace(s,'                    public void onContentChanged(Tab tab) {', """                    public void onContentChanged(Tab tab) {
                        mSandiumCrashedTab = false;""")
        s=replace(s,'        mCurrentTab = tab;\n        mConsumeTopInset', '        mSandiumCrashedTab = false;\n        mCurrentTab = tab;\n        mConsumeTopInset')
        s=replace(s,'        if (EdgeToEdgeUtils.supportsEnableTopEdgeToEdge(tab)) {',
            '        if (shouldSandiumUnderlap(tab)) return true;\n        if (EdgeToEdgeUtils.supportsEnableTopEdgeToEdge(tab)) {')
        s=replace(s,'        updateBrowserControlsVisibility(\n                mBottomControlsHeight > 0 && bottomOffset < mBottomControlsHeight);', """        updateBrowserControlsVisibility(
                mBottomControlsHeight > 0 && bottomOffset < mBottomControlsHeight);
        refreshSandiumUnderlap();""")
        s=replace(s,'    public void onStartedShowing(int layoutType) {', """    public void onStartedShowing(int layoutType) {
        mSandiumNonBrowsingTransition = layoutType != LayoutType.BROWSING;
        refreshSandiumUnderlap();""")
        s=replace(s,'    public void onFinishedShowing(int layoutType) {', """    public void onFinishedShowing(int layoutType) {
        mSandiumNonBrowsingTransition = layoutType != LayoutType.BROWSING;
        refreshSandiumUnderlap();""")
        for event in ['onEnterFullscreen(Tab tab, FullscreenOptions options)', 'onExitFullscreen(Tab tab)']:
            s=replace(s,'    public void '+event+' {','    public void '+event+' {\n        refreshSandiumUnderlap();')
        s=replace(s,'                && EdgeToEdgeUtils.hasTappableNavigationBar(mActivity.getWindow())) {\n            return windowInsets;', '                && EdgeToEdgeUtils.hasTappableNavigationBar(mActivity.getWindow())) {\n            clearSandiumUnderlapBeforeInsetsBypass();\n            return windowInsets;')
        s=replace(s,'        Insets originalSystemInsets = mSystemInsets;', """        Insets cutoutInsets = windowInsets.getInsets(WindowInsetsCompat.Type.displayCutout());
        Insets captionInsets = windowInsets.getInsets(WindowInsetsCompat.Type.captionBar());
        if (!cutoutInsets.equals(mSandiumCutoutInsets)
                || !captionInsets.equals(mSandiumCaptionInsets)) {
            mSandiumCutoutInsets = cutoutInsets;
            mSandiumCaptionInsets = captionInsets;
            changedWindowState = true;
        }
        Insets originalSystemInsets = mSystemInsets;""")
        s=replace(s,'        if (mIsEdgelessTopInsetEnabled) {\n            if (mCurrentTab != null', """        boolean sandiumUnderlap = shouldSandiumUnderlap(mCurrentTab);
        boolean wasSandiumUnderlap = mSandiumScrollUnderStatusBar;
        if (wasSandiumUnderlap != sandiumUnderlap) {
            mSandiumScrollUnderStatusBar = sandiumUnderlap;
            changedWindowState = true;
            mEdgeToEdgeManager.getEdgeToEdgeSystemBarColorHelper()
                    .setSandiumScrollUnderStatusBar(sandiumUnderlap);
        }
        if (sandiumUnderlap || wasSandiumUnderlap) {
            mInsetObserver.updateSandiumTopInsetForEdgeToEdge(
                    sandiumUnderlap ? mSystemInsets.top : 0);
        }

        if (mIsEdgelessTopInsetEnabled) {
            if (mCurrentTab != null""")
        s=replace(s,'    public void destroy() {', """    public void destroy() {
        if (mSandiumScrollUnderStatusBar) {
            mEdgeToEdgeManager.getEdgeToEdgeSystemBarColorHelper()
                    .setSandiumScrollUnderStatusBar(false);
            if (mInsetObserver != null) mInsetObserver.updateSandiumTopInsetForEdgeToEdge(0);
        }""")
    return s

def apply(root, enabled=True):
    pending=[]
    for name,path in FILES.items():
        p=root/path
        old=p.read_text()
        new = transform(name,old)
        if not enabled:
            new = new.replace("SANDIUM_TOP_UNDERLAP_EXPERIMENT = true;", "SANDIUM_TOP_UNDERLAP_EXPERIMENT = false;")
        pending.append((p,new))
    for p,text in pending: p.write_text(text)

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('src',type=Path)
    ap.add_argument('--disable', action='store_true', help='Keep instrumentation but restore stock feature routing')
    args=ap.parse_args()
    apply(args.src, enabled=not args.disable)
    print('SANDIUM_STATUS_UNDERLAP=' + ('DISABLED' if args.disable else 'EXPERIMENTAL'))
