#!/usr/bin/env python3
"""Offline regression tests for Sandium's two-state Brave Shields overlay."""
from __future__ import annotations

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "apply-sandium-shields-two-state.py"
SPEC = importlib.util.spec_from_file_location("sandium_shields_two_state", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

def twice(transform, source, label):
    once = transform(source)
    again = transform(once)
    assert once == again, f"{label}: transform is not idempotent"
    return once

array_fixture = '''<resources>
    <string-array name="blockTrackersAdsTexts">
        <item>@string/block_trackers_ads_option_1</item>
        <item>@string/block_trackers_ads_option_2</item>
        <item>@string/block_trackers_ads_option_3</item>
    </string-array>
</resources>
'''
array = twice(MODULE.transform_array_xml, array_fixture, "global option array")
assert array.count("<item>") == 2
assert "@string/sandium_trackers_ads_on" in array
assert "@string/sandium_trackers_ads_off" in array
assert "block_trackers_ads_option_2" not in array

privacy_xml_fixture = '''<PreferenceScreen>
        <org.chromium.chrome.browser.settings.BraveDialogPreference
            android:key="block_trackers_ads"
            android:title="@string/block_trackers_ads_title"
            app:dialog_subtitle="@string/block_trackers_ads_summary"
            app:dialog_entries="@array/blockTrackersAdsTexts"
            app:dialog_default_index="1"
            />
</PreferenceScreen>
'''
privacy_xml = twice(MODULE.transform_privacy_xml, privacy_xml_fixture, "global dialog")
assert 'app:dialog_default_index="0"' in privacy_xml

layout_fixture = '''<LinearLayout>
                <!-- Option 1: Aggressive -->
                <View android:id="@+id/trackers_aggressive_option" android:text="@string/block_trackers_ads_option_1" />
                <View />
                <!-- Option 2: Standard -->
                <LinearLayout android:id="@+id/trackers_standard_option">
                    <RadioButton android:id="@+id/trackers_standard_radio" />
                </LinearLayout>
                <View />
                <!-- Option 3: Allow -->
                <LinearLayout android:id="@+id/trackers_allow_option" android:text="@string/block_trackers_ads_option_3">
                    <RadioButton android:id="@+id/trackers_allow_radio" />
                </LinearLayout>
</LinearLayout>
'''
layout = twice(MODULE.transform_site_layout, layout_fixture, "site options")
assert "trackers_standard_option" not in layout
assert "trackers_standard_radio" not in layout
assert "trackers_aggressive_option" in layout and "trackers_allow_option" in layout
assert 'android:text="@string/sandium_trackers_ads_on"' in layout
assert 'android:text="@string/sandium_trackers_ads_off"' in layout

site_fixture = '''class Panel {
    private void setupTrackersAdsPanel(View panel) {
        oldThreeOptionImplementation();
    }

    private void setTrackersAdsSetting(String value) {
        save(value);
    }
}
'''
site = twice(MODULE.transform_site_panel, site_fixture, "site panel")
assert "trackers_standard_radio" not in site
assert "trackers_standard_option" not in site
assert "BraveShieldsContentSettings.BLOCK_RESOURCE" in site
assert "BraveShieldsContentSettings.ALLOW_RESOURCE" in site
assert "setChecked(isOn)" in site and "setChecked(!isOn)" in site

dialog_fixture = '''class Dialog {
                                switch ((int) mNewValue) {
                                    case 0:
                                        BraveShieldsContentSettings.setShieldsValue(
                                                ProfileManager.getLastUsedRegularProfile(),
                                                "",
                                                BraveShieldsContentSettings
                                                        .RESOURCE_IDENTIFIER_TRACKERS,
                                                BraveShieldsContentSettings.BLOCK_RESOURCE,
                                                false);
                                        break;
                                    case 1:
                                        BraveShieldsContentSettings.setShieldsValue(
                                                ProfileManager.getLastUsedRegularProfile(),
                                                "",
                                                BraveShieldsContentSettings
                                                        .RESOURCE_IDENTIFIER_TRACKERS,
                                                BraveShieldsContentSettings.DEFAULT,
                                                false);
                                        break;
                                    default:
                                        BraveShieldsContentSettings.setShieldsValue(
                                                ProfileManager.getLastUsedRegularProfile(),
                                                "",
                                                BraveShieldsContentSettings
                                                        .RESOURCE_IDENTIFIER_TRACKERS,
                                                BraveShieldsContentSettings.ALLOW_RESOURCE,
                                                false);
                                        break;
                                }
}
'''
dialog = twice(MODULE.transform_dialog_fragment, dialog_fixture, "global mapping")
assert "if ((int) mNewValue == 0)" in dialog
assert "setTrackersPref(" in dialog
assert "RESOURCE_IDENTIFIER_TRACKERS" not in dialog
assert "BraveShieldsContentSettings.DEFAULT" not in dialog

legacy_fixture = '''void getSetting() {
            if (settings.equals(BLOCK_THIRDPARTY_RESOURCE)) {
                settings = DEFAULT;
            }
}
'''
legacy = twice(MODULE.transform_shields_content_settings, legacy_fixture, "legacy migration")
assert "settings.equals(BLOCK_THIRDPARTY_RESOURCE) || settings.equals(DEFAULT)" in legacy
assert "setShieldsValue(profile, host, RESOURCE_IDENTIFIER_TRACKERS, BLOCK_RESOURCE, false)" in legacy
assert "settings = BLOCK_RESOURCE;" in legacy

native_fixture = '''using CosmeticFilteringSetting = traits::BraveShieldsSetting<
    /*content_settings_type=*/ContentSettingsType::BRAVE_COSMETIC_FILTERING,
    /*SettingType=*/ControlType,
    /*default_value=*/ControlType::BLOCK_THIRD_PARTY>;
'''
native = twice(MODULE.transform_native_default, native_fixture, "native default")
assert "default_value=*/ControlType::BLOCK>" in native
assert "ControlType::BLOCK_THIRD_PARTY" not in native

native_test_fixture = '''    EXPECT_EQ(brave_shields::ControlType::BLOCK_THIRD_PARTY, initial_value);
    EXPECT_EQ(brave_shields::ControlType::BLOCK_THIRD_PARTY,
              brave_shields::CosmeticFilteringSetting::kDefaultValue);
'''
native_test = twice(MODULE.transform_native_default_test, native_test_fixture, "native test")
assert "ControlType::BLOCK, initial_value" in native_test

privacy_source = (SCRIPT.read_text(encoding="utf-8"))
assert "SANDIUM_SHIELDS_TWO_STATE_GLOBAL_CHANGE_BEGIN" in privacy_source
assert "SANDIUM_SHIELDS_TWO_STATE_GLOBAL_INIT_BEGIN" in privacy_source
assert "SANDIUM_SHIELDS_TWO_STATE_SEARCH_SUMMARY_BEGIN" in privacy_source
assert "SANDIUM_SHIELDS_TWO_STATE_DIALOG_MAPPING_BEGIN" in privacy_source
assert "R.string.sandium_trackers_ads_on" in privacy_source
assert "R.string.sandium_trackers_ads_off" in privacy_source

print("SANDIUM_SHIELDS_TWO_STATE_UNIT_TEST=PASS global=On/Off site=On/Off default=Aggressive migration=Standard-to-On idempotent=true")
