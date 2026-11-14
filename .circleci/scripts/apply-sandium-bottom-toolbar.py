#!/usr/bin/env python3
"""Pinned native phone-toolbar overlay; no synthetic URL field or clipboard access.
Apply after Brave patches and existing Sandium UI overlays. Not a CI trigger.
"""
import argparse
import re
from pathlib import Path
import subprocess

PIN = 'd331de35ca8ab1358c7a17e4bd41627d55eaef51'
BRAVE_PIN = '44a84b1f89d9a35287289d6a3d493e362f5a5123'
BASE = 'chrome/browser/ui/android/toolbar/'
PHONE = BASE+'java/src/org/chromium/chrome/browser/toolbar/top/ToolbarPhone.java'
PREF = BASE+'java/src/org/chromium/chrome/browser/toolbar/settings/AddressBarPreference.java'
BRAVE = 'android/java/org/chromium/chrome/browser/toolbar/top/BraveToolbarLayoutImpl.java'
MARKER = 'SANDIUM_NATIVE_BOTTOM_TOOLBAR_V1'


def once(s, old, new):
    if s.count(old) != 1:
        raise ValueError('Pinned toolbar anchor changed: '+old[:100])
    return s.replace(old, new, 1)


def body(s, signature, replacement):
    start = s.index(signature)
    begin = s.index('{', start)
    depth = 1
    end = begin + 1
    while depth:
        depth += (s[end] == '{') - (s[end] == '}')
        end += 1
    return s[:begin+1]+'\n'+replacement+'\n    '+s[end-1:]


def phone(s):
    if MARKER in s: return s
    s = once(s, '    private ImageView mHomeButton;', '''    // SANDIUM_NATIVE_BOTTOM_TOOLBAR_V1: retain native start-slot geometry/focus animation.
    // The old home slot now navigates forward; no second URL widget is introduced.
    private ImageView mHomeButton;''')
    s = once(s, '        mTrackerSupplier = trackerSupplier;\n        mBackButtonCoordinator = backButtonCoordinator;', '''        mTrackerSupplier = trackerSupplier;
        mBackButtonCoordinator = backButtonCoordinator;
        mHomeButton.setImageResource(R.drawable.sandium_toolbar_forward);
        mHomeButton.setContentDescription(getContext().getString(R.string.sandium_toolbar_forward));
        mHomeButton.setTooltipText(getContext().getString(R.string.sandium_toolbar_forward));
        mHomeButton.setOnLongClickListener(null);
        ((org.chromium.ui.widget.ChromeImageButton) mHomeButton).setClickCallback(
                (metaState, buttonState) -> tabController.forward());
        homeButtonCoordinator.setHasSpaceToShow(true);''')
    s = body(s, '    private boolean shouldShowBackButtonOutside()', '        return false; // Android system Back remains unchanged.')
    s = once(s, '''        boolean hideHomeButton =
                !mIsHomeButtonEnabled
                        || showBackButtonOutside
                        || (shouldModifyToolbarButtons
                                && !ToolbarVariationUtils.shouldHomeButtonBeAtStartOfToolbar());''', '''        ((org.chromium.chrome.browser.toolbar.home_button.HomeButton) mHomeButton)
                .setHasSpaceToShow(true);
        boolean hideHomeButton = false; // Forward owns the start slot independent of Home prefs.''')
    s = once(s, '            getTabSwitcherButtonCoordinator().setHasSpaceToShow(!shouldModifyToolbarButtons);', '            getTabSwitcherButtonCoordinator().setHasSpaceToShow(true);')
    s = once(s, '    private ImageView mHomeButton;', """    private ImageView mHomeButton;
    private @Nullable org.chromium.chrome.browser.tab.Tab mSandiumObservedTab;
    private final org.chromium.chrome.browser.tab.TabObserver mSandiumNavigationObserver =
            new org.chromium.chrome.browser.tab.TabObserver() {
                @Override
                public void onNavigationStateChanged() { updateSandiumForwardState(); }
                @Override
                public void onDidFinishNavigationInPrimaryMainFrame(
                        org.chromium.chrome.browser.tab.Tab tab,
                        org.chromium.content_public.browser.NavigationHandle navigation) {
                    updateSandiumForwardState();
                }
                @Override
                public void onDestroyed(org.chromium.chrome.browser.tab.Tab tab) {
                    if (mSandiumObservedTab == tab) mSandiumObservedTab = null;
                    updateSandiumForwardState();
                }
                @Override
                public void onNavigationEntriesDeleted(org.chromium.chrome.browser.tab.Tab tab) {
                    updateSandiumForwardState();
                }
            };

    private void observeSandiumForwardTab() {
        var tab = getToolbarDataProvider().getTab();
        if (mSandiumObservedTab != tab) {
            if (mSandiumObservedTab != null) mSandiumObservedTab.removeObserver(mSandiumNavigationObserver);
            mSandiumObservedTab = tab;
            if (tab != null) tab.addObserver(mSandiumNavigationObserver);
        }
        updateSandiumForwardState();
    }

    private void updateSandiumForwardState() {
        boolean canForward = mSandiumObservedTab != null && mSandiumObservedTab.canGoForward();
        mHomeButton.setEnabled(canForward);
        mHomeButton.setImageAlpha(canForward ? 255 : 97);
    }
""")
    s = once(s, '        getToolbarDataProvider().addToolbarDataProviderObserver(this);',
                '        getToolbarDataProvider().addToolbarDataProviderObserver(this);\n        observeSandiumForwardTab();')
    s = once(s, '    public void onTabOrModelChanged() {',
                '    public void onTabOrModelChanged() {\n        observeSandiumForwardTab();')
    s = once(s, '    public void destroy() {', """    public void destroy() {
        if (mSandiumObservedTab != null) {
            mSandiumObservedTab.removeObserver(mSandiumNavigationObserver);
            mSandiumObservedTab = null;
        }""")
    # Preserve real text/content geometry, but visually enclose the existing trailing Shields row.
    s = once(s, '        onLocationBarBackgroundViewBoundsChanged();\n    }', '''        // Brave's real Shields row precedes the new-tab slot. Extend paint only, never URL
        // touch/edit bounds; native focus expansion hides the row and retains its clear/go controls.
        View shields = findViewById(R.id.sandium_shields_row);
        if (shields != null) {
            int extension = Math.round(shields.getWidth()
                    * (1f - getExpansionFractionForVisualState(visualState)));
            if (LocalizationUtils.isLayoutRtl()) out.left -= extension;
            else out.right += extension;
        }
        onLocationBarBackgroundViewBoundsChanged();
    }''')
    s = body(s, '    protected void updateOptionalButton(@Nullable ButtonData buttonData)', '        hideOptionalButton(); // Fixed phone row; all actions remain in the app menu.')
    return s


def preference(s):
    if MARKER in s: return s
    return once(s, '    public static @ToolbarPositionAndSource int computeToolbarPositionAndSource() {', '''    @SuppressWarnings("UseSharedPreferencesManagerFromChromeCheck")
    public static @ToolbarPositionAndSource int computeToolbarPositionAndSource() {
        // SANDIUM_NATIVE_BOTTOM_TOOLBAR_V1: one-time migration, before layout inflation.
        // Use native placement/controller and preserve its tablet, keyboard and rotation safeguards.
        android.content.SharedPreferences sandium = org.chromium.base.ContextUtils
                .getApplicationContext().getSharedPreferences("sandium-toolbar", Context.MODE_PRIVATE);
        if (!org.chromium.ui.base.DeviceFormFactor.isNonMultiDisplayContextOnTablet(
                    org.chromium.base.ContextUtils.getApplicationContext())
                && !sandium.getBoolean("bottom-native-v1", false)) {
            // Before native startup, render bottom but do not mark migration complete. Existing
            // LocalStatePrefs must not later restore a stale TOP choice from the old build.
            if (LocalStatePrefs.get() == null) return ToolbarPositionAndSource.BOTTOM_SETTINGS;
            setToolbarPositionAndSource(ToolbarPositionAndSource.BOTTOM_SETTINGS);
            sandium.edit().putBoolean("bottom-native-v1", true).apply();
        }''')


def brave(s):
    if MARKER in s: return s
    return once(s, '''        BraveMenuButtonCoordinator.setMenuFromBottom(
                isMenuButtonOnBottomControls() || isMenuOnBottomWithBottomAddressBar());''', '''        // SANDIUM_NATIVE_BOTTOM_TOOLBAR_V1: native action dispatch preserves incognito policy.
        View sandiumNewTab = findViewById(R.id.sandium_new_tab);
        if (sandiumNewTab != null) {
            // Phone row is intentionally fixed. Keep these feature views alive for their native
            // lifecycle but give them no toolbar space; feature/menu policies are not changed.
            for (View extra : new View[] {mWalletLayout, mRewardsLayout, mYouTubePipLayout}) {
                if (extra == null) continue;
                android.view.ViewGroup.LayoutParams params = extra.getLayoutParams();
                params.width = 0;
                params.height = 0;
                extra.setLayoutParams(params);
                extra.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS);
            }
            sandiumNewTab.setOnClickListener(v -> {
                try {
                    BraveActivity.getBraveActivity().getMenuOrKeyboardActionController()
                            .onMenuOrKeyboardAction(isIncognito()
                                    ? R.id.new_incognito_tab_menu_id : R.id.new_tab_menu_id,
                                    false, null, null);
                } catch (BraveActivity.BraveActivityNotFoundException e) {
                    Log.e(TAG, "New tab action without browser activity", e);
                }
            });
        }
        BraveMenuButtonCoordinator.setMenuFromBottom(
                isMenuButtonOnBottomControls() || isMenuOnBottomWithBottomAddressBar());''')


def layout(s):
    if MARKER in s: return s
    if s.count('@layout/brave_toolbar') != 1:
        raise ValueError('Apply after pinned Brave toolbar patch')
    pattern = r'(<include layout="@layout/brave_toolbar"[\s\S]*?/>)'
    matches = re.findall(pattern, s)
    if len(matches) != 1: raise ValueError('Expected one complete Brave toolbar include')
    s = s.replace(matches[0], '<FrameLayout android:id="@+id/sandium_shields_row" '
                  'android:layout_width="wrap_content" android:layout_height="wrap_content">\n'
                  + matches[0] + '\n        </FrameLayout>', 1)
    return once(s, '        <ViewStub\n            android:id="@+id/optional_button_stub"', '''        <!-- SANDIUM_NATIVE_BOTTOM_TOOLBAR_V1 -->
        <org.chromium.ui.widget.ChromeImageButton
            android:id="@+id/sandium_new_tab"
            style="@style/ToolbarHoverableButton"
            android:layout_width="48dp"
            android:layout_height="48dp"
            android:src="@drawable/sandium_toolbar_add"
            android:contentDescription="@string/sandium_toolbar_new_tab"
            android:tooltipText="@string/sandium_toolbar_new_tab"
            app:tint="@color/default_icon_color_tint_list" />

        <ViewStub
            android:id="@+id/optional_button_stub"''')


def menu(s):
    if '@drawable/sandium_toolbar_menu' in s: return s
    return once(s, '@drawable/ic_more_vert_24dp', '@drawable/sandium_toolbar_menu')


def commandline(s):
    if 'SANDIUM_SINGLE_TOOLBAR_FEATURES_V1' in s: return s
    return once(s, '        CommandLine.getInstance().appendSwitchesAndArguments(args);', """        CommandLine.getInstance().appendSwitchesAndArguments(args);
        // SANDIUM_SINGLE_TOOLBAR_FEATURES_V1: the native bottom-address toolbar is the single
        // navigation row. The separate experimental AndroidBottomBar must not add a second row.
        String sandiumDisabled = CommandLine.getInstance().getSwitchValue("disable-features", "");
        StringBuilder sandiumDisabledFeatures = new StringBuilder(sandiumDisabled);
        if (sandiumDisabledFeatures.length() > 0) sandiumDisabledFeatures.append(',');
        sandiumDisabledFeatures.append("AndroidBottomBar");
        CommandLine.getInstance().appendSwitchWithValue(
                "disable-features", sandiumDisabledFeatures.toString());""")


def resources():
    paths = {
        'forward': 'M5,12 L19,12 M13,6 L19,12 L13,18',
        'add': 'M12,5 L12,19 M5,12 L19,12',
        'menu': 'M4,6 L20,6 M4,12 L20,12 M4,18 L20,18',
    }
    result = {}
    for name, path in paths.items():
        result['java/res/drawable/sandium_toolbar_'+name+'.xml'] = f'''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24"
    android:autoMirrored="{'true' if name == 'forward' else 'false'}">
    <path android:pathData="{path}" android:strokeColor="#FFFFFFFF" android:strokeWidth="1.8"
        android:strokeLineCap="round" android:strokeLineJoin="round" android:fillColor="#00000000" />
</vector>
'''
    result['java/res/values/sandium_toolbar.xml'] = '''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="sandium_toolbar_forward">Forward</string>
    <string name="sandium_toolbar_new_tab">New tab</string>
</resources>
'''
    return result


def build(s):
    if 'sandium_toolbar_forward.xml' in s: return s
    entries = ''.join('    "'+p+'",\n' for p in resources())
    return once(s, '    "java/res/layout/toolbar_phone.xml",', entries+'    "java/res/layout/toolbar_phone.xml",')


def apply(src, core):
    if subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip() != PIN:
        raise ValueError('Unexpected Chromium pin')
    if subprocess.check_output(['git','-C',str(core),'rev-parse','HEAD'],text=True).strip() != BRAVE_PIN:
        raise ValueError('Unexpected Brave pin')
    changes = [(src/PHONE,phone), (src/PREF,preference), (core/BRAVE,brave),
               (src/BASE/'java/res/layout/toolbar_phone.xml',layout),
               (src/BASE/'java/res/layout/menu_button.xml',menu), (src/BASE/'BUILD.gn',build),
               (core/'android/java/org/chromium/base/BraveCommandLineInitUtil.java',commandline)]
    # Calculate every transformation first: changed upstream anchors fail before any writes.
    output = [(p,fn(p.read_text())) for p,fn in changes]
    output += [(src/BASE/p,text) for p,text in resources().items()]
    for p,text in output:
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(text)

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--src',type=Path,required=True)
    parser.add_argument('--core',type=Path,required=True)
    args=parser.parse_args()
    apply(args.src,args.core)
