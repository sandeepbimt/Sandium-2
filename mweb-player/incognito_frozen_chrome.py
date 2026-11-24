"""Extend the frozen phone chrome to RawS private NTP and HTTP(S), not its data owners."""
from glue import once

M = 'chrome/browser/ui/android/appmenu/'
MI = M + 'internal/java/src/org/chromium/chrome/browser/ui/appmenu/'
MP = M + 'java/src/org/chromium/chrome/browser/ui/appmenu/'
HANDLER = MI + 'AppMenuHandlerImpl.java'
MENU = MI + 'AppMenu.java'
PAGED = MI + 'SandiumPagedMenu.java'
PROPERTIES = MP + 'AppMenuPropertiesDelegate.java'
TABBED = ('chrome/android/java/src/org/chromium/chrome/browser/tabbed_mode/'
          'TabbedAppMenuPropertiesDelegate.java')
TOOLBAR = ('chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/'
           'toolbar/top/ToolbarPhone.java')
NTP_DIR = 'chrome/android/java/src/org/chromium/chrome/browser/ntp/'
NTP_PAGE = NTP_DIR + 'IncognitoNewTabPage.java'
NTP_VIEW = NTP_DIR + 'IncognitoNewTabPageView.java'
TRACKED = {
    NTP_PAGE: 'f6cb21f2e62d3a671c7544da3abd6563c01e146c8396532e7ab20fc465af0ab2',
    NTP_VIEW: 'adbaa027b6a773aa99c098f3e165e710520ce80ddf10e0f9dc1834b70695e45a',
}
O = 'chrome/browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/'
LOCATION_PHONE = O + 'LocationBarPhone.java'
STATUS = O + 'status/StatusCoordinator.java'
OWNERS = {
    LOCATION_PHONE: '94f4bc91d2338fb21f2a87c905a419b7e06731462229ae7aef0ca50b32549d7d',
    STATUS: '3e37460e660e38ac48501ec25361f61a66e364e40fbf4e9ec44939fe16414002',
    TABBED: 'b8d4324fc2c3ccdffa5f0fe8a0613d836f26bb137b33714b5ebc18bd03822607',
    PROPERTIES: '47986f9b7fa95be1f7dcf371137229de6b8ed7d55fa85a1194785f6b5bb3a658',
    HANDLER: 'a3f8cbeca889eb163c64eae62b9c5a7aad164fe896e54acd868524bc7268d88a',
    MENU: '97437fc124b3ca906e2e654c07ca2811f6fc194a90b4fdd6a514a16799703b62',
    PAGED: '5a6a424fe5a8c8660b0c01c8cf40617c9a673bd35f3ab25115d1a0578a0589b9',
    TOOLBAR: '830dc2f46b9f349faed77d9f822ed3dc02df6d531e49522d8fcd413deb40bc98',
}


def transform(path, raw):
    s = raw.decode()
    def edit(old, new):
        nonlocal s
        s = once(s, old, new)
    if path == TABBED:
        edit('''    @Override
    public MVCListAdapter.ModelList buildMenuModelList() {''', '''    @Override
    public boolean supportsRawSPrivateMenu() {
        var tab = mActivityTabProvider.get();
        return "io.github.sandeepbimt.raws".equals(mContext.getPackageName())
                && tab != null && !tab.isDestroyed() && tab.isIncognito()
                && isIncognitoShowing() && !isIncognitoReauthShowing()
                && getMenuGroup() == MenuGroup.PAGE_MENU;
    }

    @Override
    public MVCListAdapter.ModelList buildMenuModelList() {''')
        edit('''        if (shouldShowIconRow() || (supportsRawSMenuEditor()
                && mContext.getResources().getConfiguration().smallestScreenWidthDp < 600)) {''',
             '''        if (shouldShowIconRow() || ((supportsRawSMenuEditor() || supportsRawSPrivateMenu())
                && mContext.getResources().getConfiguration().smallestScreenWidthDp < 600)) {''')
    elif path == PROPERTIES:
        edit('''    default boolean supportsRawSMenuEditor() { return false; }
''', '''    default boolean supportsRawSMenuEditor() { return false; }

    /** A read-only layout over the current private tab's native actions, not the editor. */
    default boolean supportsRawSPrivateMenu() { return false; }
''')
    elif path == HANDLER:
        edit('''        boolean useSandiumMenu = rawSMenuEligible() && mModelList != null;
        mAppMenu.setSandiumModels(
                useSandiumMenu ? mModelList : null, mDelegate.isRawSRecentTabsMenu());''',
             '''        boolean readOnlyPrivateMenu = mDelegate.supportsRawSPrivateMenu()
                && mContext.getResources().getConfiguration().smallestScreenWidthDp < 600;
        boolean useSandiumMenu = (rawSMenuEligible() || readOnlyPrivateMenu) && mModelList != null;
        mAppMenu.setSandiumModels(
                useSandiumMenu ? mModelList : null, mDelegate.isRawSRecentTabsMenu(),
                readOnlyPrivateMenu);''')
    elif path == MENU:
        edit('''    private boolean mSandiumRecentTabs;
    void setSandiumModels(org.chromium.ui.modelutil.MVCListAdapter.@Nullable ModelList models,
            boolean recentTabs) {
        mSandiumModels = models;
        mSandiumRecentTabs = recentTabs;
    }''', '''    private boolean mSandiumRecentTabs;
    private boolean mSandiumReadOnlyPrivateMenu;

    void setSandiumModels(org.chromium.ui.modelutil.MVCListAdapter.@Nullable ModelList models,
            boolean recentTabs, boolean readOnlyPrivateMenu) {
        mSandiumModels = models;
        mSandiumRecentTabs = recentTabs;
        mSandiumReadOnlyPrivateMenu = readOnlyPrivateMenu;
    }''')
        edit('''                    mSandiumRecentTabs = false;''',
             '''                    mSandiumRecentTabs = false;
                    mSandiumReadOnlyPrivateMenu = false;''')
        edit('''            SandiumPagedMenu menu = new SandiumPagedMenu(context, mSandiumModels, contentView, mListView, mSandiumRecentTabs);''',
             '''            SandiumPagedMenu menu = new SandiumPagedMenu(
                    context, mSandiumModels, contentView, mListView, mSandiumRecentTabs,
                    mSandiumReadOnlyPrivateMenu);''')
    elif path == PAGED:
        edit('import android.content.Context;','import android.content.Context;\nimport android.content.res.Configuration;')
        edit('''    private final boolean mRecentTabs;''',
             '''    private final boolean mRecentTabs;
    private final boolean mReadOnlyPrivateMenu;''')
        edit('''    SandiumPagedMenu(Context context, ModelList models, View nativeContent, ListView nativeList, boolean recentTabs) {
        super(context);
        mPreferences = new RawSParityMenuPreferences(context, recentTabs);
        mRecentTabs = recentTabs;
        mGroupColor = context.getColor(R.color.sandium_menu_group_surface);
        mPanelColor = shieldsMatchedPanel(context);
        mTextColor = context.getColor(R.color.sandium_menu_on_surface);
        mSecondaryTextColor = context.getColor(R.color.sandium_menu_on_surface_variant);
        mDividerColor = context.getColor(R.color.sandium_menu_outline_variant);
        mAccentColor = context.getColor(R.color.sandium_menu_accent);''',
             '''    SandiumPagedMenu(Context context, ModelList models, View nativeContent,
            ListView nativeList, boolean recentTabs, boolean readOnlyPrivateMenu) {
        super(context);
        // This is an app-wide layout containing action IDs only; private mode never edits it.
        mPreferences = new RawSParityMenuPreferences(context, recentTabs);
        mRecentTabs = recentTabs;
        mReadOnlyPrivateMenu = readOnlyPrivateMenu;
        Context palette = context;
        if (readOnlyPrivateMenu) {
            Configuration dark = new Configuration();
            dark.uiMode = Configuration.UI_MODE_NIGHT_YES;
            palette = context.createConfigurationContext(dark);
        }
        mGroupColor = palette.getColor(R.color.sandium_menu_group_surface);
        mPanelColor = readOnlyPrivateMenu
                ? palette.getColor(R.color.sandium_menu_surface_container)
                : shieldsMatchedPanel(context);
        mTextColor = palette.getColor(R.color.sandium_menu_on_surface);
        mSecondaryTextColor = palette.getColor(R.color.sandium_menu_on_surface_variant);
        mDividerColor = palette.getColor(R.color.sandium_menu_outline_variant);
        mAccentColor = palette.getColor(R.color.sandium_menu_accent);''')
        edit('''        if (mDraft == null || mWriteInFlight) return;
        SandiumMenuState snapshot''', '''        if (mReadOnlyPrivateMenu || mDraft == null || mWriteInFlight) return;
        SandiumMenuState snapshot''')
        edit('''            if (mUncataloguedNativeRow >= 0) {''',
             '''            if (mReadOnlyPrivateMenu || mUncataloguedNativeRow >= 0) {''')
        edit('''                } else {
                    heading.addView(new View(getContext()), new LinearLayout.LayoutParams(dp(64), 1));
                }
                TextView title''', '''                } else if (!mReadOnlyPrivateMenu) {
                    heading.addView(new View(getContext()), new LinearLayout.LayoutParams(dp(64), 1));
                }
                TextView title''')
        edit('''                TextView editAction = button(s(R.string.sandium_menu_edit),''',
             '''                if (!mReadOnlyPrivateMenu) {
                    TextView editAction = button(s(R.string.sandium_menu_edit),''')
        edit('''                        s(R.string.sandium_menu_edit_description),
                        () -> { mDraft = mSaved.copy(); render(); });
                editAction.setMinWidth(dp(64));
                LinearLayout.LayoutParams editParams = new LinearLayout.LayoutParams(dp(64), dp(48));
                heading.addView(editAction, editParams);''',
             '''                            s(R.string.sandium_menu_edit_description),
                            () -> { mDraft = mSaved.copy(); render(); });
                    editAction.setMinWidth(dp(64));
                    LinearLayout.LayoutParams editParams =
                            new LinearLayout.LayoutParams(dp(64), dp(48));
                    heading.addView(editAction, editParams);
                }''')
        edit('''                tile.setOnLongClickListener(v -> { mDraft = mSaved.copy(); render(); return true; });''',
             '''                if (!mReadOnlyPrivateMenu) {
                    tile.setOnLongClickListener(v -> {
                        mDraft = mSaved.copy(); render(); return true;
                    });
                }''')
    elif path == LOCATION_PHONE:
        edit('''    public void setRawSUnifiedRowMode(boolean shared, boolean home) {
        if (mRawSUnifiedRow''', '''    public void setRawSUnifiedRowMode(boolean shared, boolean home) {
        // This callback can repeat when a regular and private web tab have the same row mode.
        if (mStatusCoordinator != null) {
            mStatusCoordinator.setRawSPrivateBadgeVisible(shared
                    && mLocationBarDataProvider != null
                    && mLocationBarDataProvider.isIncognitoBranded());
        }
        if (mRawSUnifiedRow''')
        edit('''        statusCoordinator.setRawSNativeHome(mRawSNativeHome);''',
             '''        statusCoordinator.setRawSNativeHome(mRawSNativeHome);
        statusCoordinator.setRawSPrivateBadgeVisible(
                mRawSUnifiedRow && locationBarDataProvider.isIncognitoBranded());''')
    elif path == STATUS:
        edit('''    public void setRawSNativeHome(boolean home) {''',
             '''    /** Shows the native private badge beside, never instead of, the location/status icon. */
    public void setRawSPrivateBadgeVisible(boolean visible) {
        mModel.set(StatusProperties.INCOGNITO_BADGE_VISIBLE, visible);
    }

    public void setRawSNativeHome(boolean home) {''')
    elif path == NTP_PAGE:
        edit('import android.graphics.Canvas;', 'import android.graphics.Canvas;\nimport android.graphics.Color;')
        edit('import org.chromium.chrome.browser.ui.edge_to_edge.EdgeToEdgeController;',
             'import org.chromium.chrome.browser.ui.bottombar.BottomBarConfigUtils;\n'
             'import org.chromium.chrome.browser.ui.edge_to_edge.EdgeToEdgeController;')
        edit('''        mIncognitoNtpBackgroundColor = context.getColor(R.color.ntp_bg_incognito);''',
             '''        boolean showRawSPrivateHome = mProfile.isIncognitoBranded()
                && BottomBarConfigUtils.shouldUseRawSUnifiedPhoneToolbar(context);
        mIncognitoNtpBackgroundColor = showRawSPrivateHome
                ? Color.BLACK : context.getColor(R.color.ntp_bg_incognito);''')
        edit('''                incognitoNewTabPageManager, mContextMenuManager, navigationDelegate);
''', '''                incognitoNewTabPageManager, mContextMenuManager, navigationDelegate);
        if (showRawSPrivateHome) mIncognitoNewTabPageView.showRawSPrivateHome();
''')
    elif path == NTP_VIEW:
        edit('import android.graphics.Canvas;', 'import android.graphics.Canvas;\nimport android.graphics.Color;')
        edit('import android.view.View;', 'import android.view.Gravity;\nimport android.view.View;')
        edit('import android.widget.FrameLayout;',
             'import android.widget.FrameLayout;\nimport android.widget.ImageView;')
        edit('''    @Override
    public void onAttachedToWindow() {''', '''    void showRawSPrivateHome() {
        setBackgroundColor(Color.BLACK);
        // Keep Chromium's ScrollView/padding target, but remove its pixels, focus and actions.
        mScrollView.setVisibility(View.INVISIBLE);
        mFadingShadowBottom.setVisibility(View.GONE);
        mScrollView.setOnScrollChangeListener(null);

        ImageView logo = new ImageView(getContext());
        logo.setImageResource(R.drawable.raws_frozen_shields_mark);
        logo.setScaleType(ImageView.ScaleType.FIT_CENTER);
        logo.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        int size = Math.round(72 * getResources().getDisplayMetrics().density);
        addView(logo, new FrameLayout.LayoutParams(size, size, Gravity.CENTER));
    }

    @Override
    public void onAttachedToWindow() {''')
    elif path == TOOLBAR:
        edit('''                    if (tab != mRawSPageObservedTab || tab.isNativePage()) return;''',
             '''                    if (tab != mRawSPageObservedTab || tab.isNativePage()
                            || tab.isOffTheRecord()) {
                        return;
                    }''')
        edit('''                || mIsToolbarUiRefactorEnabled
                || isIncognitoBranded()
                || mBrowserControlsStateProvider == null''',
             '''                || mIsToolbarUiRefactorEnabled
                || (isIncognitoBranded()
                        && ChromeFeatureList.sToolbarPhoneAnimationRefactor.isEnabled())
                || mBrowserControlsStateProvider == null''')
        edit('''        if (tab.isNativePage()) return isRawSUnifiedNativeHome(tab);
        return UrlUtilities.isHttpOrHttps(tab.getUrl());''',
             '''        if (tab.isOffTheRecord() != isIncognito()
                || (tab.isOffTheRecord() && !isIncognitoBranded())) {
            return false;
        }
        if (tab.isNativePage()) {
            return isRawSUnifiedNativeHome(tab) || isRawSUnifiedPrivateNtp(tab);
        }
        return UrlUtilities.isHttpOrHttps(tab.getUrl());''')
        edit('''        return nativePage != null && !isLocationBarShownInNtp()''',
             '''        return !tab.isOffTheRecord() && nativePage != null && !isLocationBarShownInNtp()''')
        edit('''    private boolean canGoRawSForward() {''', '''    private boolean isRawSUnifiedPrivateNtp(Tab tab) {
        // Keep the actual private NTP and the native status/omnibox. Only join its outer chrome.
        return tab.isOffTheRecord() && isIncognitoBranded() && !isLocationBarShownInNtp()
                && BottomBarConfigUtils.isNtp(tab);
    }

    private boolean canGoRawSForward() {''')
        edit('''        int fallback = mToolbarBackground.getColor();
        if (tab.isNativePage()) {''',
             '''        int fallback = mToolbarBackground.getColor();
        // Don't record/sample private pages or borrow a regular document's last observed color.
        if (tab.isOffTheRecord()) return fallback | 0xff000000;
        if (tab.isNativePage()) {''')
        edit('''                        && !(mRawSPageActionsActive && mVisualState == VisualState.BRAND_COLOR))''',
             '''                        && !(mRawSPageActionsActive && (mVisualState == VisualState.BRAND_COLOR
                                || mVisualState == VisualState.INCOGNITO)))''')
        edit('''                || (!mRawSPageActionsActive && getToolbarDataProvider().isUsingBrandColor())
                || isIncognitoBranded()
                || !isLocationBarCurrentlyShown()''',
             '''                || (!mRawSPageActionsActive && getToolbarDataProvider().isUsingBrandColor())
                || (isIncognitoBranded() && (!mRawSPageActionsActive || !canUseRawSPageActions()))
                || !isLocationBarCurrentlyShown()''')
        edit('''            if (tab == null || tab.isNativePage() || tab.isShowingErrorPage()) return false;
            String scheme = getToolbarDataProvider().getCurrentGurl().getScheme();
            if (!"https".equals(scheme) && !"http".equals(scheme)) return false;''',
             '''            if (tab == null || tab.isShowingErrorPage()) return false;
            if (tab.isNativePage()) {
                if (!isRawSUnifiedPrivateNtp(tab)) return false;
            } else {
                String scheme = getToolbarDataProvider().getCurrentGurl().getScheme();
                if (!"https".equals(scheme) && !"http".equals(scheme)) return false;
            }''')
    else:
        raise ValueError(path)
    return s.encode()
