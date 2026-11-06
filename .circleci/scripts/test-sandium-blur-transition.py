#!/usr/bin/env python3
"""Offline self-tests for the four-level Sandium page-transition blur setting."""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).with_name("apply-sandium-blur-transition.py")
SPEC = importlib.util.spec_from_file_location("sandium_blur_overlay", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

STARTUP_FIXTURE = """import org.chromium.base.CommandLineInitUtil;
import org.chromium.base.ContextUtils;
import org.chromium.base.PathUtils;
class SplitCompatApplication {
    void attachBaseContext() {
        if (isBrowserProcess) {
            CommandLineInitUtil.initCommandLine(
                    COMMAND_LINE_FILE, SplitCompatApplication::shouldUseDebugFlags);
            PathUtils.setPrivateDataDirectorySuffix(PRIVATE_DATA_DIRECTORY_SUFFIX);
        }
    }
    @Override
    public void onCreate() {}
    @Override
    public void onCreate() {
        super.onCreate();
    }
}
"""
XML_FIXTURE = """<PreferenceScreen>
    <org.chromium.components.browser_ui.settings.ChromeSwitchPreference
        android:key="brave_night_mode_enabled_key"
        android:icon="@drawable/ic_theme_dark"
        android:title="@string/night_mode_enable"
        android:summary="@string/night_mode_summary" />
</PreferenceScreen>
"""
JAVA_FIXTURE = """package org.chromium.chrome.browser.settings;
import androidx.preference.Preference;
import androidx.preference.PreferenceGroupAdapter;
import org.chromium.base.BravePreferenceKeys;
import org.chromium.base.ContextUtils;
class AppearancePreferences {
    /* package */ static final String PREF_BRAVE_NIGHT_MODE_ENABLED =
            "brave_night_mode_enabled_key";
    void onActivityCreated() {
        Preference nightModeEnabled = findPreference(PREF_BRAVE_NIGHT_MODE_ENABLED);
        if (nightModeEnabled instanceof ChromeSwitchPreference) {
            ((ChromeSwitchPreference) nightModeEnabled)
                    .setChecked(ChromeFeatureList.isEnabled(
                            BraveFeatureList.FORCE_WEB_CONTENTS_DARK_MODE));
        }
        Preference enableBottomToolbar = findPreference("bottom");
    }
    boolean onPreferenceChange(Preference preference, Object newValue) {
        String key = preference.getKey();
        boolean shouldRelaunch = false;
        if (BravePreferenceKeys.BRAVE_BOTTOM_TOOLBAR_ENABLED_KEY.equals(key)) {
            doSomething();
        }
        if (shouldRelaunch) BraveRelaunchUtils.askForRelaunch(getActivity());
        return true;
    }
    private static boolean isSharingHubEnabled() {}
    private void applyOrdering() {
        setPreferenceOrder(PREF_BRAVE_NIGHT_MODE_ENABLED, 9);
        setPreferenceOrder(PREF_BRAVE_DISABLE_SHARING_HUB, 10);
        setPreferenceOrder(PREF_SHOW_BRAVE_REWARDS_ICON, 11);
        setPreferenceOrder(PREF_ADS_SWITCH, 12);
        setPreferenceOrder(AppearanceSettingsFragment.PREF_BOOKMARK_BAR, 13);
        setPreferenceOrder(PREF_BRAVE_ENABLE_TAB_GROUPS, 14);
        setPreferenceOrder(PREF_SHOW_UNDO_WHEN_TABS_CLOSED, 15);
    }
}
"""
GRD_FIXTURE = """<grit>
      <message name="IDS_NIGHT_MODE_SUMMARY" desc="Summary for Night Mode, which forces web content into dark mode.">
        Force dark mode for web content
      </message>
</grit>
"""
TEST_FIXTURE = """import androidx.preference.Preference;
import org.chromium.base.BravePreferenceKeys;
class BraveAppearancePreferencesTest {
    void order() {
        final String[] sortedPrefKeys = {
            AppearancePreferences.PREF_BRAVE_NIGHT_MODE_ENABLED,
        };
    }
    @Test
    @SmallTest
    public void testDynamicColorsPreferenceAvailability() {}
}
"""

def main():
    startup = MODULE.transform_chromium_startup(STARTUP_FIXTURE)
    assert startup == MODULE.transform_chromium_startup(startup), "startup overlay must be idempotent"
    assert startup.index("CommandLineInitUtil.initCommandLine") < startup.index(
        "enableSandiumNavigationBlurTransition();"
    ) < startup.index("PathUtils.setPrivateDataDirectorySuffix")
    for snippet in (
        '"default"',
        '"low"',
        '"medium"',
        '"high"',
        "nav-animation-blur-sigma/1.0",
        "nav-animation-blur-sigma/2.0",
        "nav-animation-blur-sigma/4.0",
        'getSwitchValue("disable-features", "")',
        'appendSwitchWithValue("enable-features"',
    ):
        assert snippet in startup, f"missing startup mapping: {snippet}"

    xml = MODULE.transform_appearance_xml(XML_FIXTURE)
    assert xml == MODULE.transform_appearance_xml(xml), "XML overlay must be idempotent"
    assert 'androidx.preference.ListPreference' in xml and MODULE.PREF_KEY in xml

    java = MODULE.transform_appearance_java(JAVA_FIXTURE)
    assert java == MODULE.transform_appearance_java(java), "Appearance Java overlay must be idempotent"
    for snippet in (
        "setEntries(",
        'new CharSequence[] {"default", "low", "medium", "high"}',
        "getSandiumPageTransitionBlurLevel()",
        ".commit()",
        "BraveRelaunchUtils.askForRelaunch(getActivity());",
        "PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL, 10",
    ):
        assert snippet in java, f"missing settings wiring: {snippet}"

    grd = MODULE.transform_grd(GRD_FIXTURE)
    assert grd == MODULE.transform_grd(grd), "GRD overlay must be idempotent"
    assert grd.count('name="IDS_SANDIUM_PAGE_TRANSITION_BLUR_') == 6

    appearance_test = MODULE.transform_appearance_test(TEST_FIXTURE)
    assert appearance_test == MODULE.transform_appearance_test(appearance_test)
    assert "testPageTransitionBlurHasFourLevelsAndRestoresSavedChoice" in appearance_test
    assert appearance_test.count("PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL") >= 1

    # Incomplete marker sets and changed anchors must fail closed.
    try:
        MODULE.replace_marked(
            MODULE.XML_BEGIN + "\n",
            MODULE.XML_BEGIN,
            MODULE.XML_END,
            MODULE.XML_BLOCK,
            MODULE.XML_ANCHOR,
            "partial-marker-test",
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("partial marker set was accepted")

    try:
        MODULE.transform_appearance_xml(XML_FIXTURE.replace(MODULE.XML_ANCHOR, "", 1))
    except RuntimeError:
        pass
    else:
        raise AssertionError("missing exact XML anchor was accepted")

    print("SANDIUM_BLUR_FOUR_LEVEL_TESTS=PASS")

if __name__ == "__main__":
    main()
