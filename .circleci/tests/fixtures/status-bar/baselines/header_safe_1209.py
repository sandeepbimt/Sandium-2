#!/usr/bin/env python3
"""EXPERIMENTAL stable Android16 web underlap. Native compile/device validation required.
See docs/STATUS_BAR_RESEARCH.md before integration.
"""
import argparse
import hashlib
from pathlib import Path

FILES = {
 'TransitiveTopInsetProvider.java': 'chrome/browser/ui/android/edge_to_edge/java/src/org/chromium/chrome/browser/ui/edge_to_edge/TransitiveTopInsetProvider.java',
 'TopControlsStackerUnitTest.java': 'chrome/browser/browser_controls/android/java/src/org/chromium/chrome/browser/browser_controls/TopControlsStackerUnitTest.java',
 'TopControlsStacker.java': 'chrome/browser/browser_controls/android/java/src/org/chromium/chrome/browser/browser_controls/TopControlsStacker.java',
 'BrowserControlsStateProvider.java': 'chrome/browser/browser_controls/android/java/src/org/chromium/chrome/browser/browser_controls/BrowserControlsStateProvider.java',
 'BrowserControlsSizer.java': 'chrome/browser/browser_controls/android/java/src/org/chromium/chrome/browser/browser_controls/BrowserControlsSizer.java',
 'BrowserControlsManager.java': 'chrome/android/java/src/org/chromium/chrome/browser/fullscreen/BrowserControlsManager.java',
 'TopInsetProvider.java': 'chrome/browser/ui/android/edge_to_edge/java/src/org/chromium/chrome/browser/ui/edge_to_edge/TopInsetProvider.java',

 'ToolbarPositionController.java': 'chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/ToolbarPositionController.java',
 'EdgeToEdgeControllerCreator.java': 'chrome/browser/ui/android/edge_to_edge/java/src/org/chromium/chrome/browser/ui/edge_to_edge/EdgeToEdgeControllerCreator.java',
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


# Scroll-away header reservation: native controls own the offset, never website CSS
# or per-scroll Android translation. Keep reversible exact anchors for checkpoints.
SPACER_PATCHES = {'EdgeToEdgeBaseLayout.java': [('new android.graphics.LinearGradient(0, 0, 0, height * 1.5f,',
                                'new android.graphics.LinearGradient(0, 0, 0, height,'),
                               ('canvas.drawRect(0, 0, getWidth(), mSandiumTopProtectionHeight * 1.5f,',
                                'canvas.drawRect(0, 0, getWidth(), mSandiumTopProtectionHeight,')],
 'TopInsetProvider.java': [('public interface TopInsetProvider extends Destroyable {',
                            'public interface TopInsetProvider extends Destroyable {\n'
                            '    /** Sandium ordinary-web underlap only; native edge-to-edge pages do not own a '
                            'spacer. */\n'
                            '    default boolean isSandiumWebUnderlapActive() { return false; }\n')],
 'BrowserControlsStateProvider.java': [('public interface BrowserControlsStateProvider {',
                                        'public interface BrowserControlsStateProvider {\n'
                                        "    /** Height owned by Sandium's registered scroll-away status layer, "
                                        'not other controls. */\n'
                                        '    default int getSandiumStatusSpacerHeight() { return 0; }\n')],
 'BrowserControlsSizer.java': [('public interface BrowserControlsSizer extends BrowserControlsVisibilityManager {',
                                'public interface BrowserControlsSizer extends BrowserControlsVisibilityManager '
                                '{\n'
                                '    /** Metadata only. TopControlsStacker remains the sole writer of aggregate '
                                'height. */\n'
                                '    default void setSandiumStatusSpacerHeight(int height) {}\n')],
 'BrowserControlsManager.java': [('    @Override\n'
                                  '    public void setTopControlsHeight(int topControlsHeight, int '
                                  'topControlsMinHeight) {',
                                  '    private int mSandiumStatusSpacerHeight;\n'
                                  '\n'
                                  '    @Override\n'
                                  '    public int getSandiumStatusSpacerHeight() { return '
                                  'mSandiumStatusSpacerHeight; }\n'
                                  '\n'
                                  '    @Override\n'
                                  '    public void setSandiumStatusSpacerHeight(int height) {\n'
                                  '        mSandiumStatusSpacerHeight = Math.max(0, height);\n'
                                  '    }\n'
                                  '\n'
                                  '    @Override\n'
                                  '    public void setTopControlsHeight(int topControlsHeight, int '
                                  'topControlsMinHeight) {')],
 'EdgeToEdgeControllerImpl.java': [('    private boolean mSandiumScrollUnderStatusBar;',
                                    '    private boolean mSandiumScrollUnderStatusBar;\n'
                                    '\n'
                                    '    @Override\n'
                                    '    public boolean isSandiumWebUnderlapActive() {\n'
                                    '        return mSandiumScrollUnderStatusBar;\n'
                                    '    }\n'),
                                   ('&& controls.getTopControlsHeight() == 0',
                                    '&& controls.getTopControlsHeight() == '
                                    'controls.getSandiumStatusSpacerHeight()\n'
                                    '                && controls.getTopControlsMinHeight() == 0')],
 'ToolbarPositionController.java': [("        // Exits early if the top padding doesn't need adjusting.\n"
                                     '        if (NtpCustomizationUtils.shouldSkipTopInsetsChange(',
                                     '        // A bottom toolbar never owns status padding. Register a separate '
                                     'native\n'
                                     '        // scroll-away top layer so the header starts below the status bar '
                                     'at origin.\n'
                                     '        boolean sandiumSpacer = consumeTopInset\n'
                                     '                && mTopInsetProvider.isSandiumWebUnderlapActive()\n'
                                     '                && layoutType == LayoutType.BROWSING\n'
                                     '                && mBrowserControlsSizer.getControlsPosition() == '
                                     'ControlsPosition.BOTTOM;\n'
                                     '        mTopControlsStacker.setSandiumStatusSpacerHeight(sandiumSpacer ? '
                                     'systemTopInset : 0);\n'
                                     '        if (mBrowserControlsSizer.getControlsPosition() == '
                                     'ControlsPosition.BOTTOM) {\n'
                                     '            consumeTopInset = false;\n'
                                     '        }\n'
                                     "        // Exits early if the top padding doesn't need adjusting.\n"
                                     '        if (NtpCustomizationUtils.shouldSkipTopInsetsChange('),
                                    ('    public void destroy() {',
                                     '    public void destroy() {\n'
                                     '        mTopControlsStacker.setSandiumStatusSpacerHeight(0);')],
 'TopControlsStacker.java': [('    @IntDef({\n        TopControlType.STATUS_INDICATOR,',
                              '    @IntDef({\n'
                              '        TopControlType.SANDIUM_STATUS_SPACER,\n'
                              '        TopControlType.STATUS_INDICATOR,'),
                             ('        int STATUS_INDICATOR = 0;',
                              '        int SANDIUM_STATUS_SPACER = 7;\n        int STATUS_INDICATOR = 0;'),
                             ('                TopControlType.STATUS_INDICATOR,',
                              '                TopControlType.SANDIUM_STATUS_SPACER,\n'
                              '                TopControlType.STATUS_INDICATOR,'),
                             ('    private int mTotalHeight;',
                              '    private int mSandiumStatusSpacerHeight;\n'
                              '    private boolean mSandiumDestroyed;\n'
                              '\n'
                              '    /** Updates only our registered layer. Existing native layers keep ownership '
                              'of their sizes. */\n'
                              '    public void setSandiumStatusSpacerHeight(int height) {\n'
                              '        if (mSandiumDestroyed) return;\n'
                              '        height = Math.max(0, height);\n'
                              '        if (height == mSandiumStatusSpacerHeight) return;\n'
                              '        mSandiumStatusSpacerHeight = height;\n'
                              '        requestLayerUpdateSync(false);\n'
                              '    }\n'
                              '\n'
                              '    private int mTotalHeight;'),
                             ('        mControls = new HashMap<>();',
                              '        mControls = new HashMap<>();\n'
                              '        mControls.put(TopControlType.SANDIUM_STATUS_SPACER, new TopControlLayer() '
                              '{\n'
                              '            @Override\n'
                              '            public int getTopControlType() { return '
                              'TopControlType.SANDIUM_STATUS_SPACER; }\n'
                              '            @Override\n'
                              '            public int getTopControlHeight() { return mSandiumStatusSpacerHeight; '
                              '}\n'
                              '            @Override\n'
                              '            public int getTopControlVisibility() {\n'
                              '                return mSandiumStatusSpacerHeight > 0\n'
                              '                        ? TopControlVisibility.VISIBLE : '
                              'TopControlVisibility.HIDDEN;\n'
                              '            }\n'
                              '        });'),
                             ('    private void updateTopControlsHeight(boolean requireAnimations) {',
                              '    private void updateTopControlsHeight(boolean requireAnimations) {\n'
                              '        // Publish ownership before the aggregate-height observer callbacks.\n'
                              '        '
                              'mBrowserControlsSizer.setSandiumStatusSpacerHeight(mSandiumStatusSpacerHeight);'),
                             ('    public void destroy() {',
                              '    public void destroy() {\n'
                              '        mSandiumDestroyed = true;\n'
                              '        mBrowserControlsSizer.setSandiumStatusSpacerHeight(0);'),
                             ('            case TopControlType.STATUS_INDICATOR:',
                              '            case TopControlType.SANDIUM_STATUS_SPACER:\n'
                              '                return "SANDIUM_STATUS_SPACER";\n'
                              '            case TopControlType.STATUS_INDICATOR:')]}

# A final underlap notification must clear our layer even when native HUB defers its
# usual top-inset callbacks. An absent tab must also release only our reservation.
SPACER_PATCHES['EdgeToEdgeControllerImpl.java'].append((
    '                    mCurrentTab != null || activeLayoutType != LayoutType.HUB;',
    '                    wasSandiumUnderlap || mCurrentTab != null || activeLayoutType != LayoutType.HUB;'))
SPACER_PATCHES['ToolbarPositionController.java'].append((
    '                && layoutType != LayoutType.TOOLBAR_SWIPE) {\n            return false;',
    '                && layoutType != LayoutType.TOOLBAR_SWIPE) {\n            mTopControlsStacker.setSandiumStatusSpacerHeight(0);\n            return false;'))

SPACER_PATCHES['TopControlsStackerUnitTest.java'] = [(
    '    @Test\n    public void testAddRemoveControl() {',
    '    @Test\n    public void testSandiumSpacerPreservesOtherLayersAndZeroMinimum() {\n        TestLayer toolbar = TestLayer.toolbarLayer();\n        mTopControlsStacker.addControl(toolbar);\n        mTopControlsStacker.setSandiumStatusSpacerHeight(24);\n        assertControlsHeight(124, 0);\n        verify(mBrowserControlsSizer).setSandiumStatusSpacerHeight(24);\n        mTopControlsStacker.setSandiumStatusSpacerHeight(0);\n        assertControlsHeight(100, 0);\n        verify(mBrowserControlsSizer, atLeastOnce()).setSandiumStatusSpacerHeight(0);\n    }\n\n    @Test\n    public void testSandiumSpacerIgnoresUpdatesAfterDestroy() {\n        mTopControlsStacker.setSandiumStatusSpacerHeight(24);\n        mTopControlsStacker.destroy();\n        reset(mBrowserControlsSizer);\n        mTopControlsStacker.setSandiumStatusSpacerHeight(60);\n        verify(mBrowserControlsSizer, never()).setTopControlsHeight(60, 0);\n        verify(mBrowserControlsSizer, never()).setSandiumStatusSpacerHeight(60);\n    }\n\n    @Test\n    public void testAddRemoveControl() {')]

SPACER_PATCHES['TransitiveTopInsetProvider.java'] = [(
    '    @Override\n    public void addObserver(TopInsetProvider.Observer observer) {',
    '    @Override\n    public boolean isSandiumWebUnderlapActive() {\n        var provider = mTopInsetProviderSupplier.get();\n        return provider != null && provider.isSandiumWebUnderlapActive();\n    }\n\n    @Override\n    public void addObserver(TopInsetProvider.Observer observer) {')]

SPACER_PATCHES['EdgeToEdgeControllerImpl.java'].extend([
    ('    private boolean mSandiumScrollUnderStatusBar;',
     '    private boolean mSandiumScrollUnderStatusBar;\n    private boolean mSandiumStatusDestroyed;'),
    ('        return mSandiumScrollUnderStatusBar;',
     '        return mSandiumScrollUnderStatusBar && !mSandiumStatusDestroyed;'),
    ('    public void destroy() {\n        if (mSandiumScrollUnderStatusBar) {',
     '    public void destroy() {\n        mSandiumStatusDestroyed = true;\n        if (mSandiumScrollUnderStatusBar) {'),
])

def undo_spacer(name, text):
    for old, new in reversed(SPACER_PATCHES.get(name, [])):
        if new in text:
            if text.count(new) != 1: raise RuntimeError('Duplicate scroll-away spacer anchor')
            text = text.replace(new, old, 1)
    return text

def apply_spacer(name, text):
    for old, new in SPACER_PATCHES.get(name, []):
        text = replace(text, old, new)
    return text

def transform(name,s):
    s = undo_spacer(name, s)
    # Strip only this exact-version extension before the older whole-block idempotence anchors.
    if name == 'EdgeToEdgeControllerImpl.java' and '    // Constraint/visibility changes do not necessarily move browser controls.' in s:
        start = s.index('    // Constraint/visibility changes do not necessarily move browser controls.')
        end = s.index('    private void refreshSandiumUnderlap() {', start)
        if (s.count('    // Constraint/visibility changes do not necessarily move browser controls.') != 1
                or hashlib.sha256(s[start:end].encode()).hexdigest() != '98322a066b83fcbf0db360805e976586798891e80033c86744d27dc2f3f94846'):
            raise RuntimeError('Unrecognized status eligibility extension')
        s = s[:start] + s[end:]
        s = s.replace('        traceSandiumStatusEligibility(sandiumUnderlap);\n', '')
    # Migrate already-patched checkpoints without duplicating the overlay.
    if name == "EdgeToEdgeBaseLayout.java":
        s = s.replace("new int[] {0xB3000000, 0x99000000, 0x00000000}",
                      "new int[] {0xE6000000, 0x99000000, 0x00000000}")
    if name == "EdgeToEdgeControllerImpl.java":
        s = s.replace('        return controls.getControlsPosition() == BrowserControlsStateProvider.ControlsPosition.TOP\n                && controls.getTopControlsHeight() > 0\n                && controls.getTopControlsMinHeightOffset() == 0\n                && !controls.isVisibilityForced();', '        if (controls.isVisibilityForced() || controls.getTopControlsMinHeightOffset() != 0) {\n            return false;\n        }\n        if (controls.getControlsPosition() == BrowserControlsStateProvider.ControlsPosition.TOP) {\n            return controls.getTopControlsHeight() > 0;\n        }\n        // Native bottom placement removes the entire top toolbar. Decline transitional\n        // or extra top-layer geometry rather than allowing content under native controls.\n        return controls.getControlsPosition() == BrowserControlsStateProvider.ControlsPosition.BOTTOM\n                && controls.getTopControlsHeight() == 0\n                && controls.getBottomControlsHeight() > 0;')
    if name == "EdgeToEdgeControllerTest.java":
        s = s.replace('        when(mBrowserControlsStateProvider.getControlsPosition())\n                .thenReturn(BrowserControlsStateProvider.ControlsPosition.TOP);\n        assertTrue(EdgeToEdgeControllerImpl.isSandiumPageAndControlsSupported(\n                mTab, mBrowserControlsStateProvider));\n    }\n', '        when(mBrowserControlsStateProvider.getTopControlsHeight()).thenReturn(0);\n        // No bottom controls yet: migration must still fail closed.\n        assertFalse(EdgeToEdgeControllerImpl.isSandiumPageAndControlsSupported(\n                mTab, mBrowserControlsStateProvider));\n        when(mBrowserControlsStateProvider.getBottomControlsHeight()).thenReturn(100);\n        assertTrue(EdgeToEdgeControllerImpl.isSandiumPageAndControlsSupported(\n                mTab, mBrowserControlsStateProvider));\n        when(mBrowserControlsStateProvider.getTopControlsHeight()).thenReturn(1);\n        assertFalse(EdgeToEdgeControllerImpl.isSandiumPageAndControlsSupported(\n                mTab, mBrowserControlsStateProvider));\n        when(mBrowserControlsStateProvider.getControlsPosition())\n                .thenReturn(BrowserControlsStateProvider.ControlsPosition.TOP);\n        when(mBrowserControlsStateProvider.getTopControlsHeight()).thenReturn(100);\n        assertTrue(EdgeToEdgeControllerImpl.isSandiumPageAndControlsSupported(\n                mTab, mBrowserControlsStateProvider));\n    }\n')
    if name == "EdgeToEdgeControllerImpl.java" and "public void onTopControlsHeightChanged(" not in s:
        s = s.replace('    @Override\n    public void onControlsPositionChanged(int controlsPosition) {\n        refreshSandiumUnderlap();\n    }\n', '    @Override\n    public void onTopControlsHeightChanged(int topControlsHeight, int topControlsMinHeight) {\n        refreshSandiumUnderlap();\n    }\n\n    @Override\n    public void onControlsPositionChanged(int controlsPosition) {\n        refreshSandiumUnderlap();\n    }\n')
    # Normalize the isolated rollback gate before idempotence checks.
    s=s.replace("SANDIUM_TOP_UNDERLAP_EXPERIMENT = false;", "SANDIUM_TOP_UNDERLAP_EXPERIMENT = true;")
    if name == 'EdgeToEdgeControllerCreator.java':
        s=replace(s, '                && !navigationBarInsets.equals(Insets.NONE)) {',
            '                && (!navigationBarInsets.equals(Insets.NONE)\n'
            '                        || canCreateSandiumHiddenGestureController(activity, insets))) {')
        s=replace(s, '    @SuppressWarnings("NullAway")', """    @VisibleForTesting
    static boolean canCreateSandiumHiddenGestureController(
            Activity activity, WindowInsetsCompat insets) {
        // Hidden gesture hints legitimately have zero navbar height. Require positive
        // gesture evidence, never infer navigation mode merely from absent tappable insets.
        // Creation does not enable underlap: the controller still applies all page,
        // fullscreen, keyboard, cutout, layout and native-screen guards on every update.
        if (!EdgeToEdgeUtils.isSandiumTopUnderlapExperimentEnabled()
                || !EdgeToEdgeUtils.isEdgeToEdgeEverywhereEnabled()
                || !"ChromeTabbedActivity".equals(activity.getClass().getSimpleName())
                || activity.isInMultiWindowMode() || activity.isInPictureInPictureMode()) {
            return false;
        }
        var config = activity.getResources().getConfiguration();
        if (config.smallestScreenWidthDp >= 600
                || config.orientation != android.content.res.Configuration.ORIENTATION_PORTRAIT
                || !EdgeToEdgeUtils.doAllInsetsIndicateGestureNavigation(insets)
                || !insets.getInsets(WindowInsetsCompat.Type.navigationBars()).equals(Insets.NONE)) {
            return false;
        }
        Insets status = insets.getInsets(WindowInsetsCompat.Type.statusBars());
        Insets cutout = insets.getInsets(WindowInsetsCompat.Type.displayCutout());
        boolean supported = insets.isVisible(WindowInsetsCompat.Type.statusBars())
                && status.top > 0 && status.left == 0 && status.right == 0
                && cutout.left == 0 && cutout.right == 0 && cutout.bottom == 0
                && cutout.top <= status.top
                && insets.getInsets(WindowInsetsCompat.Type.captionBar()).equals(Insets.NONE);
        if (org.chromium.base.TraceEvent.enabled()) {
            org.chromium.base.TraceEvent.instant("SandiumHiddenGestureController",
                    "supported=" + supported + ",status=" + status.top);
        }
        return supported;
    }

    @SuppressWarnings("NullAway")""")
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
                        new int[] {0xE6000000, 0x99000000, 0x00000000},
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
        when(mBrowserControlsStateProvider.getTopControlsHeight()).thenReturn(0);
        // No bottom controls yet: migration must still fail closed.
        assertFalse(EdgeToEdgeControllerImpl.isSandiumPageAndControlsSupported(
                mTab, mBrowserControlsStateProvider));
        when(mBrowserControlsStateProvider.getBottomControlsHeight()).thenReturn(100);
        assertTrue(EdgeToEdgeControllerImpl.isSandiumPageAndControlsSupported(
                mTab, mBrowserControlsStateProvider));
        when(mBrowserControlsStateProvider.getTopControlsHeight()).thenReturn(1);
        assertFalse(EdgeToEdgeControllerImpl.isSandiumPageAndControlsSupported(
                mTab, mBrowserControlsStateProvider));
        when(mBrowserControlsStateProvider.getControlsPosition())
                .thenReturn(BrowserControlsStateProvider.ControlsPosition.TOP);
        when(mBrowserControlsStateProvider.getTopControlsHeight()).thenReturn(100);
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
        if (controls.isVisibilityForced() || controls.getTopControlsMinHeightOffset() != 0) {
            return false;
        }
        if (controls.getControlsPosition() == BrowserControlsStateProvider.ControlsPosition.TOP) {
            return controls.getTopControlsHeight() > 0;
        }
        // Native bottom placement removes the entire top toolbar. Decline transitional
        // or extra top-layer geometry rather than allowing content under native controls.
        return controls.getControlsPosition() == BrowserControlsStateProvider.ControlsPosition.BOTTOM
                && controls.getTopControlsHeight() == 0
                && controls.getBottomControlsHeight() > 0;
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
    public void onTopControlsHeightChanged(int topControlsHeight, int topControlsMinHeight) {
        refreshSandiumUnderlap();
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
        s=replace(s,'        mBottomControlsHeight = bottomControlsHeight;',
            '        mBottomControlsHeight = bottomControlsHeight;\n        refreshSandiumUnderlap();')
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
    if name == 'EdgeToEdgeControllerImpl.java':
        s=replace(s, '    private void refreshSandiumUnderlap() {', """    // Constraint/visibility changes do not necessarily move browser controls. Reassess the
    // existing guards even when there is no offset or height callback; never bypass them.
    @Override
    public void onAndroidControlsVisibilityChanged(int visibility) {
        refreshSandiumUnderlap();
    }

    @Override
    public void onOffsetTagsInfoChanged(
            org.chromium.chrome.browser.browser_controls.BrowserControlsOffsetTagsInfo oldInfo,
            org.chromium.chrome.browser.browser_controls.BrowserControlsOffsetTagsInfo newInfo,
            int constraints, boolean shouldUpdateOffsets) {
        refreshSandiumUnderlap();
    }

    private void traceSandiumStatusEligibility(boolean active) {
        if (!org.chromium.base.TraceEvent.enabled()) return;
        var controls = mBrowserControlsStateProvider;
        var config = mActivity.getResources().getConfiguration();
        // Numeric geometry/state only: no URL, title, page pixels or navigation history.
        org.chromium.base.TraceEvent.instant("SandiumStatusEligibility",
                "active=" + active
                + ",sdk=" + android.os.Build.VERSION.SDK_INT
                + ",unified=" + mDisablePaddingRootView
                + ",tabbed=" + "ChromeTabbedActivity".equals(mActivity.getClass().getSimpleName())
                + ",portrait=" + (config.orientation
                        == android.content.res.Configuration.ORIENTATION_PORTRAIT)
                + ",tablet=" + (config.smallestScreenWidthDp >= 600)
                + ",multi=" + mActivity.isInMultiWindowMode()
                + ",pip=" + mActivity.isInPictureInPictureMode()
                + ",tappable=" + EdgeToEdgeUtils.hasTappableNavigationBar(mActivity.getWindow())
                + ",top=" + mSystemInsets.top
                + ",geometry=" + isSandiumTopGeometrySupported(
                        mSystemInsets, mSandiumCutoutInsets, mSandiumCaptionInsets)
                + ",keyboard=" + (mKeyboardInsets != null && mKeyboardInsets.bottom > 0)
                + ",indicator=" + mStatusIndicatorVisible
                + ",transition=" + mSandiumNonBrowsingTransition
                + ",crashed=" + mSandiumCrashedTab
                + ",fullscreen=" + (mFullscreenManager == null
                        || mFullscreenManager.getPersistentFullscreenMode())
                + ",browsing=" + (mLayoutManager != null
                        && mLayoutManager.getActiveLayoutType() == LayoutType.BROWSING)
                + ",pageControls=" + (controls != null
                        && isSandiumPageAndControlsSupported(mCurrentTab, controls))
                + ",forced=" + (controls != null && controls.isVisibilityForced())
                + ",position=" + (controls == null ? -1 : controls.getControlsPosition())
                + ",topHeight=" + (controls == null ? -1 : controls.getTopControlsHeight())
                + ",topMin=" + (controls == null ? -1 : controls.getTopControlsMinHeightOffset())
                + ",bottomHeight=" + (controls == null ? -1 : controls.getBottomControlsHeight()));
    }

    private void refreshSandiumUnderlap() {""")
        s=replace(s, '        boolean sandiumUnderlap = shouldSandiumUnderlap(mCurrentTab);',
            '        boolean sandiumUnderlap = shouldSandiumUnderlap(mCurrentTab);\n'
            '        traceSandiumStatusEligibility(sandiumUnderlap);')
    if name == 'EdgeToEdgeLayoutCoordinator.java':
        s=replace(s, '        // Consume the insets since the root view already adjusted their paddings.', """        if (org.chromium.base.TraceEvent.enabled()) {
            org.chromium.base.TraceEvent.instant("SandiumStatusPaintGeometry",
                    "protection=" + mView.getSandiumTopProtectionHeightForTesting()
                    + ",status=" + statusBarInsets.top + ",padding=" + overallInsets.top);
        }
        // Consume the insets since the root view already adjusted their paddings.""")
    return apply_spacer(name, s)

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
