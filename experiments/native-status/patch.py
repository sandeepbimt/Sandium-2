#!/usr/bin/env python3
"""Unwired native wallpaper status-underlay candidate; never enabled by shipping CI."""
_recorded_operations = None

def once(s, old, new):
    if _recorded_operations is not None: _recorded_operations.append((old, new))
    if new in s: return s
    if s.count(old) != 1: raise ValueError('Pinned native status anchor drift: '+old[:70])
    return s.replace(old,new,1)

def page(s):
    s = once(s, '        mBottomSheetController = bottomSheetController;', '''        mBottomSheetController = bottomSheetController;
        if (SANDIUM_NATIVE_STATUS_CANDIDATE) {
            mSandiumNativeTopInsetProvider = topInsetProvider;
            topInsetProvider.addObserver(mSandiumNativeTopInsetObserver);
        }''')
    return once(s, '    public void updateSearchProvider() {', '''    // Candidate remains disabled until native compilation and device validation.
    private static final boolean SANDIUM_NATIVE_STATUS_CANDIDATE =
            org.chromium.chrome.browser.ui.edge_to_edge.EdgeToEdgeUtils.isSandiumNativeStatusEnabled();
    private @Nullable TopInsetProvider mSandiumNativeTopInsetProvider;
    private final TopInsetProvider.Observer mSandiumNativeTopInsetObserver = this::onToEdgeChange;

    @Override
    public void destroy() {
        if (mSandiumNativeTopInsetProvider != null) {
            mSandiumNativeTopInsetProvider.removeObserver(mSandiumNativeTopInsetObserver);
            mSandiumNativeTopInsetProvider = null;
        }
        super.destroy();
    }

    @Override
    public boolean supportsEdgeToEdgeOnTop() {
        if (!SANDIUM_NATIVE_STATUS_CANDIDATE) return super.supportsEdgeToEdgeOnTop();
        if (mNewTabPageLayout == null) return false;
        var config = mNewTabPageLayout.getResources().getConfiguration();
        return android.os.Build.VERSION.SDK_INT >= 35
                && org.chromium.chrome.browser.ui.edge_to_edge.EdgeToEdgeUtils
                        .isEdgelessTopInsetEnabled()
                && config.smallestScreenWidthDp < 600
                && config.orientation == android.content.res.Configuration.ORIENTATION_PORTRAIT;
    }

    @Override
    void onToEdgeChange(int systemTopInset, boolean consumeTopInset, int layoutType) {
        // Stock coordinator restores FOREGROUND padding as the parent consumes the inset.
        super.onToEdgeChange(systemTopInset, consumeTopInset, layoutType);
        if (mNewTabPageLayout instanceof BraveNewTabPageLayout layout) {
            layout.setSandiumNativeStatusInset(consumeTopInset && supportsEdgeToEdgeOnTop()
                    ? systemTopInset : 0);
        }
    }

    public void updateSearchProvider() {''')

def layout(s):
    s = once(s, 'int currentWidth = mBgImageView.getMeasuredWidth();',
             'int currentWidth = mSandiumNativeStatusInset > 0 ? getWidth() : mBgImageView.getMeasuredWidth();')
    s = once(s, 'int currentHeight = mBgImageView.getMeasuredHeight();',
             'int currentHeight = mSandiumNativeStatusInset > 0 ? getHeight() : mBgImageView.getMeasuredHeight();')
    s = once(s, '                        mBgImageView.setImageBitmap(bgWallpaper);',
             '                        mBgImageView.setImageBitmap(bgWallpaper);\n                        invalidate(); // Root wallpaper paint observes the same async result.')
    return once(s, '    private @Nullable ImageView mBgImageView;', '''    private @Nullable ImageView mBgImageView;
    private int mSandiumNativeStatusInset;

    void setSandiumNativeStatusInset(int inset) {
        inset = Math.max(0, inset);
        if (mSandiumNativeStatusInset == inset) return;
        mSandiumNativeStatusInset = inset;
        if (mBgImageViewOnGlobalLayoutListener != null) {
            // Reuse the existing cancellable worker and focal-point cropping for root size.
            mBgImageViewOnGlobalLayoutListener.onGlobalLayout();
        }
        invalidate();
    }

    private boolean sandiumDrawsWallpaperUnderStatus() {
        ImageView imageView = mBgImageView;
        if (mSandiumNativeStatusInset <= 0 || imageView == null
                || imageView.getVisibility() != View.VISIBLE) return false;
        android.graphics.drawable.Drawable image = imageView.getDrawable();
        return image != null && image.getIntrinsicWidth() > 0 && image.getIntrinsicHeight() > 0
                && getWidth() > 0 && getHeight() > 0;
    }

    @Override
    protected void dispatchDraw(android.graphics.Canvas canvas) {
        if (mSandiumNativeStatusInset > 0) {
            // Background-only paint, never translate/reparent/resize the foreground tree.
            // No image yet: use the native screen's backing, not a white launch surface.
            canvas.drawColor(org.chromium.chrome.browser.ui.theme.ChromeSemanticColorUtils
                    .getHomeSurfaceBackgroundColor(getContext()));
            ImageView imageView = mBgImageView;
            android.graphics.drawable.Drawable image =
                    imageView == null ? null : imageView.getDrawable();
            if (sandiumDrawsWallpaperUnderStatus() && image != null && imageView != null) {
                int save = imageView.getAlpha() < 1f
                        ? canvas.saveLayerAlpha(0, 0, getWidth(), getHeight(),
                                Math.round(255 * imageView.getAlpha())) : canvas.save();
                canvas.clipRect(0, 0, getWidth(), getHeight());
                // The existing worker prepares root-sized pixels using its focal point.
                // Preserve the ImageView matrix, alpha/filter and drawable bounds exactly;
                // do not center-crop the already-cropped wallpaper a second time.
                canvas.concat(imageView.getImageMatrix());
                image.draw(canvas);
                canvas.restoreToCount(save);
            }
        }
        super.dispatchDraw(canvas);

    }

    @Override
    protected boolean drawChild(android.graphics.Canvas canvas, View child, long drawingTime) {
        // Draw the wallpaper once at the root, including its padding. Foreground still uses
        // normal layout, input, accessibility and safe insets. No bitmap copies/sampling.
        if (child == mBgImageView && sandiumDrawsWallpaperUnderStatus()) return true;
        return super.drawChild(canvas, child, drawingTime);
    }
''')


def chromium(name, s):
    """Compose AFTER shipping status patch; candidate remains false in Utils."""
    if name == 'EdgeToEdgeBaseLayout.java':
        s = once(s, '    private boolean isSandiumNativeSettings() {', """    // Test-only: existing unified root ownership only, never opt a new activity into E2E.
    private static final boolean SANDIUM_NATIVE_SCREEN_TEST_CANDIDATE = false;

    private boolean isSandiumAuditedNativeScreen(android.content.Context context) {
        if (!SANDIUM_NATIVE_SCREEN_TEST_CANDIDATE || android.os.Build.VERSION.SDK_INT < 35) {
            return false;
        }
        String name = context.getClass().getSimpleName();
        return "BookmarkActivity".equals(name) || "BraveBookmarkActivity".equals(name)
                || "HistoryActivity".equals(name) || "WelcomeOnboardingActivity".equals(name);
    }

    private boolean isSandiumNativeSettings() {""")
        return once(s, '|| "SettingsActivity".equals(context.getClass().getSimpleName()));',
                    '|| "SettingsActivity".equals(context.getClass().getSimpleName())\n'
                    '                        || isSandiumAuditedNativeScreen(context));')
    if name == 'EdgeToEdgeUtils.java':
        s = once(s, '    public static boolean isEdgelessTopInsetEnabled() {', """    private static final boolean SANDIUM_NATIVE_STATUS_CANDIDATE = false;

    public static boolean isSandiumNativeStatusEnabled() {
        return SANDIUM_NATIVE_STATUS_CANDIDATE && Build.VERSION.SDK_INT >= 35
                && EdgeToEdgeFieldTrialImpl.getEverywhereOverrides().isEnabledForManufacturerVersion()
                && !DeviceInfo.isAutomotive();
    }

    private static final boolean SANDIUM_NATIVE_SCREEN_TEST_CANDIDATE = false;

    public static boolean isSandiumNativeSecondaryScreenEnabled(android.content.Context context) {
        return SANDIUM_NATIVE_SCREEN_TEST_CANDIDATE && isSandiumNativeStatusEnabled()
                && !org.chromium.ui.base.DeviceFormFactor.isNonMultiDisplayContextOnTablet(context);
    }

    public static boolean isEdgelessTopInsetEnabled() {""")
        return once(s, '                || isSandiumTopUnderlapExperimentEnabled();',
                    '                || isSandiumTopUnderlapExperimentEnabled()\n'
                    '                || (isSandiumNativeStatusEnabled() && Build.VERSION.SDK_INT >= 35);')
    if name == 'EdgeToEdgeControllerCreator.java':
        s = once(s, '                || !EdgeToEdgeUtils.isEdgeToEdgeEverywhereEnabled()\n',
                 '                || !(EdgeToEdgeUtils.isEdgeToEdgeEverywhereEnabled()\n'
                 '                        || (EdgeToEdgeUtils.isSandiumNativeStatusEnabled()\n'
                 '                                && android.os.Build.VERSION.SDK_INT >= 35))\n')
        return once(s, 'if (!EdgeToEdgeUtils.isSandiumTopUnderlapExperimentEnabled()\n',
                    'if (!(EdgeToEdgeUtils.isSandiumTopUnderlapExperimentEnabled()\n'
                    '                || (EdgeToEdgeUtils.isSandiumNativeStatusEnabled()\n'
                    '                        && android.os.Build.VERSION.SDK_INT >= 35))\n')
    if name == 'InsetObserver.java':
        return once(s, '    private int mSandiumTopInsetForEdgeToEdge;', '''    private int mSandiumTopInsetForEdgeToEdge;
    private int mSandiumNativeStatusPaintHeight;
    private final ObserverList<Runnable> mSandiumNativeStatusPaintObservers = new ObserverList<>();

    public void addSandiumNativeStatusPaintObserver(Runnable observer) {
        mSandiumNativeStatusPaintObservers.addObserver(observer);
    }

    public void removeSandiumNativeStatusPaintObserver(Runnable observer) {
        mSandiumNativeStatusPaintObservers.removeObserver(observer);
    }

    public int getSandiumNativeStatusPaintHeight() { return mSandiumNativeStatusPaintHeight; }

    public void setSandiumNativeStatusPaintHeight(int height) {
        // Paint metadata only: never changes CSS safe area or dispatches new insets.
        height = Math.max(0, height);
        if (mSandiumNativeStatusPaintHeight == height) return;
        mSandiumNativeStatusPaintHeight = height;
        for (Runnable observer : mSandiumNativeStatusPaintObservers) observer.run();
    }''')
    if name == 'EdgeToEdgeLayoutCoordinator.java':
        s = once(s, '    private final Context mContext;', '''    private final Context mContext;
    private final Runnable mSandiumNativePaintChanged = this::updateSandiumNativePaint;

    private void updateSandiumNativePaint() {
        if (mView == null || mInsetObserver == null) return;
        mView.setSandiumTopProtectionHeight(Math.max(
                mInsetObserver.getSandiumTopInsetForEdgeToEdge(),
                mInsetObserver.getSandiumNativeStatusPaintHeight()));
    }''')
        s = once(s, '        mInsetObserver = insetObserver;', '''        mInsetObserver = insetObserver;
        if (mInsetObserver != null) {
            mInsetObserver.addSandiumNativeStatusPaintObserver(mSandiumNativePaintChanged);
        }''')
        s = once(s, '            mInsetObserver.removeInsetsConsumer(this);', '''            mInsetObserver.removeSandiumNativeStatusPaintObserver(mSandiumNativePaintChanged);
            mInsetObserver.removeInsetsConsumer(this);''')
        return once(s, '                : mInsetObserver.getSandiumTopInsetForEdgeToEdge());',
                    '                : Math.max(mInsetObserver.getSandiumTopInsetForEdgeToEdge(),\n'
                    '                        mInsetObserver.getSandiumNativeStatusPaintHeight()));')
    if name == 'EdgeToEdgeSystemBarColorHelper.java':
        s = once(s, '    private boolean mSandiumScrollUnderStatusBar;', '''    private boolean mSandiumScrollUnderStatusBar;
    private boolean mSandiumNativeStatusProtection;

    public void setSandiumNativeStatusProtection(boolean active) {
        if (mSandiumNativeStatusProtection == active) return;
        mSandiumRestoringStatusBar = mSandiumNativeStatusProtection && !active;
        mSandiumNativeStatusProtection = active;
        updateStatusBarColor();
        mSandiumRestoringStatusBar = false;
    }''')
        s = once(s, 'mSandiumScrollUnderStatusBar ? 0x00000000 : mStatusBarColor;',
                 '(mSandiumScrollUnderStatusBar || mSandiumNativeStatusProtection)\n                ? 0x00000000 : mStatusBarColor;')
        s = once(s, 'if (mForceLightStatusBarColor || mSandiumScrollUnderStatusBar\n                || (delegateHelper != null && delegateHelper.hasSandiumStatusProtection())) {',
                 'if (mForceLightStatusBarColor || mSandiumScrollUnderStatusBar\n                || mSandiumNativeStatusProtection\n                || (delegateHelper != null && delegateHelper.hasSandiumStatusProtection())) {')
        s = once(s, '                if (mForceLightStatusBarColor) {',
                 '                if (mForceLightStatusBarColor || mSandiumNativeStatusProtection) {')
        return once(s, 'return mCanColorStatusBarColor || mSandiumScrollUnderStatusBar || mSandiumRestoringStatusBar;',
                    'return mCanColorStatusBarColor || mSandiumScrollUnderStatusBar\n                || mSandiumNativeStatusProtection || mSandiumRestoringStatusBar;')
    if name == 'EdgeToEdgeControllerImpl.java':
        s = once(s, '    private boolean mSandiumScrollUnderStatusBar;', '''    private boolean mSandiumScrollUnderStatusBar;
    private boolean mSandiumNativeStatusProtection;
    private @Nullable android.view.View mSandiumLegacyProtectionHost;
    private @Nullable SandiumLegacyNativeProtection mSandiumLegacyProtection;

    private final class SandiumLegacyNativeProtection extends android.graphics.drawable.Drawable {
        private final android.graphics.Paint mProtection = new android.graphics.Paint();
        private final android.graphics.Paint mBacking = new android.graphics.Paint();
        private int mHeight;

        void update(int width, int height) {
            setBounds(0, 0, width, height);
            if (height != mHeight) {
                mHeight = height;
                mProtection.setShader(new android.graphics.LinearGradient(0, 0, 0, height,
                        new int[] {0xE6000000, 0x99000000, 0x00000000},
                        new float[] {0f, 0.67f, 1f}, android.graphics.Shader.TileMode.CLAMP));
            }
            mBacking.setColor(org.chromium.chrome.browser.ui.theme.ChromeSemanticColorUtils
                    .getHomeSurfaceBackgroundColor(mActivity));
            invalidateSelf();
        }

        @Override
        public void draw(android.graphics.Canvas canvas) {
            var page = mCurrentTab == null ? null : mCurrentTab.getNativePage();
            var view = page == null ? null : page.getView();
            // Pending native page: never reveal an unrelated window's white backing.
            if (view == null || !view.isAttachedToWindow() || !view.isShown()
                    || view.getAlpha() == 0f) canvas.drawRect(getBounds(), mBacking);
            canvas.drawRect(getBounds(), mProtection);
        }

        @Override
        public void setAlpha(int alpha) { mProtection.setAlpha(alpha); invalidateSelf(); }
        @Override
        public void setColorFilter(@Nullable android.graphics.ColorFilter filter) {
            mProtection.setColorFilter(filter); invalidateSelf();
        }
        @Override
        public int getOpacity() { return android.graphics.PixelFormat.TRANSLUCENT; }
    }

    private void updateSandiumLegacyProtection(boolean active) {
        if (!active) {
            if (mSandiumLegacyProtectionHost != null && mSandiumLegacyProtection != null) {
                mSandiumLegacyProtectionHost.getOverlay().remove(mSandiumLegacyProtection);
            }
            mSandiumLegacyProtectionHost = null;
            mSandiumLegacyProtection = null;
            return;
        }
        android.view.View host = mActivity.getWindow().getDecorView();
        if (mSandiumLegacyProtection == null) {
            mSandiumLegacyProtection = new SandiumLegacyNativeProtection();
            mSandiumLegacyProtectionHost = host;
            host.getOverlay().add(mSandiumLegacyProtection);
        }
        int width = host.getWidth() > 0 ? host.getWidth()
                : mActivity.getResources().getDisplayMetrics().widthPixels;
        mSandiumLegacyProtection.update(width, mSystemInsets.top);
    }

    private boolean shouldSandiumNativeStatus(@Nullable Tab tab) {
        if (!EdgeToEdgeUtils.isSandiumNativeStatusEnabled()
                || android.os.Build.VERSION.SDK_INT < 35
                || !EdgeToEdgeUtils.isRegularNtp(tab)
                || !"ChromeTabbedActivity".equals(mActivity.getClass().getSimpleName())
                || mActivity.isInMultiWindowMode() || mActivity.isInPictureInPictureMode()) return false;
        var config = mActivity.getResources().getConfiguration();
        if (config.smallestScreenWidthDp >= 600
                || config.orientation != android.content.res.Configuration.ORIENTATION_PORTRAIT
                || mStatusIndicatorVisible || mSandiumNonBrowsingTransition || mSandiumCrashedTab
                || mFullscreenManager == null || mFullscreenManager.getPersistentFullscreenMode()
                || mLayoutManager == null || mLayoutManager.getActiveLayoutType() != LayoutType.BROWSING
                || (mKeyboardInsets != null && mKeyboardInsets.bottom > 0)
                || EdgeToEdgeUtils.hasTappableNavigationBar(mActivity.getWindow())) return false;
        return isSandiumTopGeometrySupported(mSystemInsets, mSandiumCutoutInsets, mSandiumCaptionInsets);
    }

    private void setSandiumNativeStatusProtection(boolean active) {
        mSandiumNativeStatusProtection = active;
        updateSandiumLegacyProtection(active && !mDisablePaddingRootView);
        mEdgeToEdgeManager.getEdgeToEdgeSystemBarColorHelper()
                .setSandiumNativeStatusProtection(active);
        if (mInsetObserver != null) {
            mInsetObserver.setSandiumNativeStatusPaintHeight(active ? mSystemInsets.top : 0);
        }
    }''')
        s = once(s, '        if (shouldSandiumUnderlap(tab)) return true;',
                 '        if (EdgeToEdgeUtils.isSandiumNativeStatusEnabled()\n'
                 '                && EdgeToEdgeUtils.isRegularNtp(tab)) return shouldSandiumNativeStatus(tab);\n'
                 '        if (shouldSandiumUnderlap(tab)) return true;')
        s = once(s, '        boolean sandiumUnderlap = shouldSandiumUnderlap(mCurrentTab);', '''        boolean sandiumNativeStatus = shouldSandiumNativeStatus(mCurrentTab);
        if (sandiumNativeStatus != mSandiumNativeStatusProtection) changedWindowState = true;
        setSandiumNativeStatusProtection(sandiumNativeStatus);
        boolean sandiumUnderlap = shouldSandiumUnderlap(mCurrentTab);''')
        s = once(s, '    private void clearSandiumUnderlapBeforeInsetsBypass() {',
                 '    private void clearSandiumUnderlapBeforeInsetsBypass() {\n'
                 '        setSandiumNativeStatusProtection(false);')
        s = once(s, '    public void destroy() {',
                 '    public void destroy() {\n        setSandiumNativeStatusProtection(false);')
        s = once(s, 'mEdgeToEdgeManager.setContentFitsWindowInsets(!isDrawingToEdge());',
                 'mEdgeToEdgeManager.setContentFitsWindowInsets(\n'
                 '                    !(isDrawingToEdge() || mSandiumNativeStatusProtection));')
        return once(s, '&& shouldSandiumUnderlap(mCurrentTab) != mSandiumScrollUnderStatusBar)',
                    '&& (shouldSandiumUnderlap(mCurrentTab) != mSandiumScrollUnderStatusBar\n'
                    '                        || shouldSandiumNativeStatus(mCurrentTab) != mSandiumNativeStatusProtection))')
    return s


NATIVE_MARKERS = {
    'EdgeToEdgeBaseLayout.java': 'SANDIUM_NATIVE_SCREEN_TEST_CANDIDATE',
    'EdgeToEdgeUtils.java': '    private static final boolean SANDIUM_NATIVE_STATUS_CANDIDATE',
    'InsetObserver.java': '    private int mSandiumNativeStatusPaintHeight;',
    'EdgeToEdgeControllerCreator.java': 'EdgeToEdgeUtils.isSandiumNativeStatusEnabled()',
    'EdgeToEdgeLayoutCoordinator.java': 'mInsetObserver.getSandiumNativeStatusPaintHeight()',
    'EdgeToEdgeSystemBarColorHelper.java': '    private boolean mSandiumNativeStatusProtection;',
    'EdgeToEdgeControllerImpl.java': '    private boolean mSandiumNativeStatusProtection;',
}

def undo_chromium(name, source):
    """Exact checkpoint reversal before replaying the shipping status patch."""
    if name not in NATIVE_MARKERS or NATIVE_MARKERS[name] not in source: return source
    global _recorded_operations
    operations = []
    _recorded_operations = operations
    try:
        if chromium(name, source) != source:
            raise ValueError('Partial native status checkpoint: ' + name)
    finally:
        _recorded_operations = None
    for old, new in reversed(operations):
        if source.count(new) != 1: raise ValueError('Native checkpoint drift: ' + name)
        source = source.replace(new, old, 1)
    return source


def settings_activity(s):
    """Legacy Settings status-only paint; retain its existing bottom/IME owner."""
    s = once(s, '    @Override\n    protected boolean shouldDrawEdgeToEdgeOnCreate() {', '''    private @Nullable android.view.View mSandiumStatusProtectionHost;
    private @Nullable SandiumSettingsStatusProtection mSandiumStatusProtection;

    private final android.view.ViewTreeObserver.OnPreDrawListener mSandiumStatusBeforeDraw =
            this::sandiumPrepareStatusBeforeDraw;

    private boolean sandiumPrepareStatusBeforeDraw() {
        android.view.View decor = getWindow().getDecorView();
        WindowInsetsCompat insets = ViewCompat.getRootWindowInsets(decor);
        if (insets != null && getEdgeToEdgeManager() != null) {
            sandiumUpdateSettingsStatusProtection(insets);
            decor.getViewTreeObserver().removeOnPreDrawListener(mSandiumStatusBeforeDraw);
        }
        return true;
    }

    private boolean sandiumUseLegacySettingsProtection() {
        return EdgeToEdgeUtils.isSandiumNativeStatusEnabled()
                && !EdgeToEdgeUtils.isEdgeToEdgeEverywhereEnabled()
                && !org.chromium.ui.base.DeviceFormFactor.isNonMultiDisplayContextOnTablet(this);
    }

    @Override
    protected boolean canColorStatusBarWithEdgeToEdgeHelper() {
        return sandiumUseLegacySettingsProtection() || super.canColorStatusBarWithEdgeToEdgeHelper();
    }

    @Override
    protected boolean canSetTransparentStatusBarWithoutDelegate() {
        return sandiumUseLegacySettingsProtection() || super.canSetTransparentStatusBarWithoutDelegate();
    }

    private static final class SandiumSettingsStatusProtection
            extends android.graphics.drawable.Drawable {
        private final android.graphics.Paint mBacking = new android.graphics.Paint();
        private final android.graphics.Paint mProtection = new android.graphics.Paint();
        private int mHeight;

        void update(int width, int height, int color) {
            setBounds(0, 0, width, height);
            mBacking.setColor(color);
            if (mHeight != height) {
                mHeight = height;
                mProtection.setShader(new android.graphics.LinearGradient(0, 0, 0, height,
                        new int[] {0xE6000000, 0x99000000, 0x00000000},
                        new float[] {0f, 0.67f, 1f}, android.graphics.Shader.TileMode.CLAMP));
            }
            invalidateSelf();
        }

        @Override
        public void draw(android.graphics.Canvas canvas) {
            canvas.drawRect(getBounds(), mBacking);
            canvas.drawRect(getBounds(), mProtection);
        }
        @Override
        public void setAlpha(int alpha) { mProtection.setAlpha(alpha); invalidateSelf(); }
        @Override
        public void setColorFilter(@Nullable android.graphics.ColorFilter filter) {
            mProtection.setColorFilter(filter); invalidateSelf();
        }
        @Override
        public int getOpacity() { return android.graphics.PixelFormat.TRANSLUCENT; }
    }

    private void sandiumClearSettingsStatusProtection() {
        boolean wasActive = mSandiumStatusProtection != null;
        if (mSandiumStatusProtectionHost != null && mSandiumStatusProtection != null) {
            mSandiumStatusProtectionHost.getOverlay().remove(mSandiumStatusProtection);
        }
        mSandiumStatusProtectionHost = null;
        mSandiumStatusProtection = null;
        if (wasActive && getEdgeToEdgeManager() != null) {
            assumeNonNull(getEdgeToEdgeManager()).getEdgeToEdgeSystemBarColorHelper()
                    .setStatusBarColor(sandiumSettingsBackground());
        }
    }

    private void sandiumUpdateSettingsStatusProtection(WindowInsetsCompat insets) {
        int height = insets.isVisible(WindowInsetsCompat.Type.statusBars())
                ? insets.getInsets(WindowInsetsCompat.Type.statusBars()).top : 0;
        if (!sandiumUseLegacySettingsProtection() || height <= 0) {
            sandiumClearSettingsStatusProtection();
            return;
        }
        android.view.View host = getWindow().getDecorView();
        if (mSandiumStatusProtection == null) {
            mSandiumStatusProtection = new SandiumSettingsStatusProtection();
            mSandiumStatusProtectionHost = host;
            host.getOverlay().add(mSandiumStatusProtection);
        }
        int width = host.getWidth() > 0 ? host.getWidth() : getResources().getDisplayMetrics().widthPixels;
        mSandiumStatusProtection.update(width, height, sandiumSettingsBackground());
        assumeNonNull(getEdgeToEdgeManager()).getEdgeToEdgeSystemBarColorHelper()
                .setStatusBarColor(android.graphics.Color.TRANSPARENT, true);
    }

    @Override
    protected boolean shouldDrawEdgeToEdgeOnCreate() {''')
    s = once(s, '    protected void onCreate(@Nullable Bundle savedInstanceState) {',
             '    protected void onCreate(@Nullable Bundle savedInstanceState) {\n'
             '        if (sandiumUseLegacySettingsProtection()) {\n'
             '            getWindow().getDecorView().getViewTreeObserver()\n'
             '                    .addOnPreDrawListener(mSandiumStatusBeforeDraw);\n'
             '        }')
    s = once(s, '    protected void onDestroy() {',
             '    protected void onDestroy() {\n'
             '        getWindow().getDecorView().getViewTreeObserver()\n'
             '                .removeOnPreDrawListener(mSandiumStatusBeforeDraw);\n'
             '        sandiumClearSettingsStatusProtection();')
    return once(s, '        if (rootWindowInsets == null) rootWindowInsets = windowInsets;',
                '        if (rootWindowInsets == null) rootWindowInsets = windowInsets;\n'
                '        sandiumUpdateSettingsStatusProtection(rootWindowInsets);')
