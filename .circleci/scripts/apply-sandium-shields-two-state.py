#!/usr/bin/env python3
"""Apply Sandium's two-state Android Shields controls to pinned Brave Core."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

EXPECTED_CORE_TAG = "v1.98.62"
EXPECTED_CORE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"

def replace_once(source: str, old: str, new: str, marker: str, label: str) -> str:
    if marker in source:
        if new not in source:
            raise RuntimeError(f"{label}: marker exists but replacement differs")
        return source
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one source anchor, found {count}")
    return source.replace(old, new, 1)

def replace_region(source: str, start: str, end: str, new: str, marker: str, label: str) -> str:
    if marker in source:
        start_pos = source.find(start)
        end_pos = source.find(end, start_pos + len(start))
        if start_pos < 0 or end_pos < 0 or marker not in source[start_pos:end_pos]:
            raise RuntimeError(f"{label}: applied marker is outside the expected source region")
        current = source[start_pos:end_pos]
        if new.rstrip() not in current:
            raise RuntimeError(f"{label}: applied region does not match expected replacement")
        return source
    if source.count(start) != 1 or source.count(end) != 1:
        raise RuntimeError(f"{label}: expected unique region anchors")
    start_pos = source.index(start)
    end_pos = source.index(end, start_pos + len(start))
    if end_pos <= start_pos:
        raise RuntimeError(f"{label}: reversed region anchors")
    return source[:start_pos] + new.rstrip() + "\n\n" + source[end_pos:]

def read(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"missing pinned source file: {path}")
    return path.read_text(encoding="utf-8")

def write(path: Path, transform, label: str) -> None:
    before = read(path)
    after = transform(before)
    if after != before:
        path.write_text(after, encoding="utf-8")
    if read(path) != after:
        raise RuntimeError(f"{label}: write verification failed")
    print(f"SANDIUM_SHIELDS_TWO_STATE_{label}=PASS")

def transform_array_xml(source: str) -> str:
    old = (
        '    <string-array name="blockTrackersAdsTexts">\n'
        '        <item>@string/block_trackers_ads_option_1</item>\n'
        '        <item>@string/block_trackers_ads_option_2</item>\n'
        '        <item>@string/block_trackers_ads_option_3</item>\n'
        '    </string-array>'
    )
    new = (
        '    <!-- SANDIUM_SHIELDS_TWO_STATE_OPTIONS_BEGIN -->\n'
        '    <string name="sandium_trackers_ads_on">On</string>\n'
        '    <string name="sandium_trackers_ads_off">Off</string>\n'
        '    <string-array name="blockTrackersAdsTexts">\n'
        '        <item>@string/sandium_trackers_ads_on</item>\n'
        '        <item>@string/sandium_trackers_ads_off</item>\n'
        '    </string-array>\n'
        '    <!-- SANDIUM_SHIELDS_TWO_STATE_OPTIONS_END -->'
    )
    return replace_once(source, old, new, "SANDIUM_SHIELDS_TWO_STATE_OPTIONS_BEGIN",
                        "Global Shields On/Off option array")

def transform_privacy_xml(source: str) -> str:
    old = (
        '        <org.chromium.chrome.browser.settings.BraveDialogPreference\n'
        '            android:key="block_trackers_ads"\n'
        '            android:title="@string/block_trackers_ads_title"\n'
        '            app:dialog_subtitle="@string/block_trackers_ads_summary"\n'
        '            app:dialog_entries="@array/blockTrackersAdsTexts"\n'
        '            app:dialog_default_index="1"\n'
        '            />'
    )
    new = (
        '        <!-- SANDIUM_SHIELDS_TWO_STATE_GLOBAL_DIALOG_BEGIN -->\n'
        '        <org.chromium.chrome.browser.settings.BraveDialogPreference\n'
        '            android:key="block_trackers_ads"\n'
        '            android:title="@string/block_trackers_ads_title"\n'
        '            app:dialog_subtitle="@string/block_trackers_ads_summary"\n'
        '            app:dialog_entries="@array/blockTrackersAdsTexts"\n'
        '            app:dialog_default_index="0" />\n'
        '        <!-- SANDIUM_SHIELDS_TWO_STATE_GLOBAL_DIALOG_END -->'
    )
    return replace_once(source, old, new, "SANDIUM_SHIELDS_TWO_STATE_GLOBAL_DIALOG_BEGIN",
                        "Global Shields dialog default On")

def transform_site_layout(source: str) -> str:
    start = "                <!-- Option 2: Standard -->"
    end = "                <!-- Option 3: Allow -->"
    marker = "SANDIUM_SHIELDS_TWO_STATE_SITE_OPTIONS_BEGIN"
    if marker in source:
        if "trackers_standard_option" in source or "trackers_standard_radio" in source:
            raise RuntimeError("Site Shields panel: Standard row remains after transformation")
        if 'android:text="@string/sandium_trackers_ads_on"' not in source or 'android:text="@string/sandium_trackers_ads_off"' not in source:
            raise RuntimeError("Site Shields panel: On/Off labels are missing")
        return source
    if source.count(start) != 1 or source.count(end) != 1:
        raise RuntimeError("Site Shields panel: expected Standard and Allow option anchors")
    a, b = source.index(start), source.index(end)
    if b <= a:
        raise RuntimeError("Site Shields panel: invalid option order")
    source = source[:a] + "                <!-- SANDIUM_SHIELDS_TWO_STATE_SITE_OPTIONS_BEGIN -->\n" + source[b:]
    source = replace_once(
        source,
        'android:text="@string/block_trackers_ads_option_1"',
        'android:text="@string/sandium_trackers_ads_on"',
        "SANDIUM_SITE_ON_LABEL",
        "Site Shields On label",
    )
    return replace_once(
        source,
        'android:text="@string/block_trackers_ads_option_3"',
        'android:text="@string/sandium_trackers_ads_off"',
        "SANDIUM_SITE_OFF_LABEL",
        "Site Shields Off label",
    )

def transform_site_panel(source: str) -> str:
    start = "    private void setupTrackersAdsPanel(View panel) {"
    end = "    private void setTrackersAdsSetting(String value) {"
    new = '''    private void setupTrackersAdsPanel(View panel) {
        // SANDIUM_SHIELDS_TWO_STATE_SITE_BEGIN
        if (mUrl == null || mProfile == null) return;

        ImageView backButton = panel.findViewById(R.id.trackers_back_button);
        if (backButton != null) {
            backButton.setOnClickListener(v -> showMainPanel());
        }

        AppCompatRadioButton onRadio = panel.findViewById(R.id.trackers_aggressive_radio);
        AppCompatRadioButton offRadio = panel.findViewById(R.id.trackers_allow_radio);

        String currentSetting =
                BraveShieldsContentSettings.getShieldsValue(
                        mProfile,
                        mUrl.getSpec(),
                        BraveShieldsContentSettings.RESOURCE_IDENTIFIER_TRACKERS);
        boolean isOn = !BraveShieldsContentSettings.ALLOW_RESOURCE.equals(currentSetting);
        if (onRadio != null) onRadio.setChecked(isOn);
        if (offRadio != null) offRadio.setChecked(!isOn);

        View onOption = panel.findViewById(R.id.trackers_aggressive_option);
        View offOption = panel.findViewById(R.id.trackers_allow_option);

        if (onOption != null && onRadio != null && offRadio != null) {
            onOption.setOnClickListener(
                    v -> {
                        onRadio.setChecked(true);
                        offRadio.setChecked(false);
                        setTrackersAdsSetting(BraveShieldsContentSettings.BLOCK_RESOURCE);
                    });
        }

        if (offOption != null && onRadio != null && offRadio != null) {
            offOption.setOnClickListener(
                    v -> {
                        offRadio.setChecked(true);
                        onRadio.setChecked(false);
                        setTrackersAdsSetting(BraveShieldsContentSettings.ALLOW_RESOURCE);
                    });
        }
        // SANDIUM_SHIELDS_TWO_STATE_SITE_END
    }

'''
    return replace_region(source, start, end, new, "SANDIUM_SHIELDS_TWO_STATE_SITE_BEGIN",
                          "Per-site Shields On/Off panel")

def transform_dialog_fragment(source: str) -> str:
    old = (
        '                                switch ((int) mNewValue) {\n'
        '                                    case 0:\n'
        '                                        BraveShieldsContentSettings.setShieldsValue(\n'
        '                                                ProfileManager.getLastUsedRegularProfile(),\n'
        '                                                "",\n'
        '                                                BraveShieldsContentSettings\n'
        '                                                        .RESOURCE_IDENTIFIER_TRACKERS,\n'
        '                                                BraveShieldsContentSettings.BLOCK_RESOURCE,\n'
        '                                                false);\n'
        '                                        break;\n'
        '                                    case 1:\n'
        '                                        BraveShieldsContentSettings.setShieldsValue(\n'
        '                                                ProfileManager.getLastUsedRegularProfile(),\n'
        '                                                "",\n'
        '                                                BraveShieldsContentSettings\n'
        '                                                        .RESOURCE_IDENTIFIER_TRACKERS,\n'
        '                                                BraveShieldsContentSettings.DEFAULT,\n'
        '                                                false);\n'
        '                                        break;\n'
        '                                    default:\n'
        '                                        BraveShieldsContentSettings.setShieldsValue(\n'
        '                                                ProfileManager.getLastUsedRegularProfile(),\n'
        '                                                "",\n'
        '                                                BraveShieldsContentSettings\n'
        '                                                        .RESOURCE_IDENTIFIER_TRACKERS,\n'
        '                                                BraveShieldsContentSettings.ALLOW_RESOURCE,\n'
        '                                                false);\n'
        '                                        break;\n'
        '                                }'
    )
    new = (
        '                                // SANDIUM_SHIELDS_TWO_STATE_DIALOG_MAPPING_BEGIN\n'
        '                                if ((int) mNewValue == 0) {\n'
        '                                    BraveShieldsContentSettings.setTrackersPref(\n'
        '                                            BraveShieldsContentSettings.BLOCK_RESOURCE);\n'
        '                                } else {\n'
        '                                    BraveShieldsContentSettings.setTrackersPref(\n'
        '                                            BraveShieldsContentSettings.ALLOW_RESOURCE);\n'
        '                                }\n'
        '                                // SANDIUM_SHIELDS_TWO_STATE_DIALOG_MAPPING_END'
    )
    return replace_once(source, old, new, "SANDIUM_SHIELDS_TWO_STATE_DIALOG_MAPPING_BEGIN",
                        "Global Shields dialog On/Off mapping")

def transform_shields_content_settings(source: str) -> str:
    old = (
        '            if (settings.equals(BLOCK_THIRDPARTY_RESOURCE)) {\n'
        '                settings = DEFAULT;\n'
        '            }'
    )
    new = (
        '            // SANDIUM_SHIELDS_TWO_STATE_LEGACY_MIGRATION_BEGIN\n'
        '            if (settings.equals(BLOCK_THIRDPARTY_RESOURCE) || settings.equals(DEFAULT)) {\n'
        '                // Standard was removed; migrate legacy global and site values to On.\n'
        '                setShieldsValue(profile, host, RESOURCE_IDENTIFIER_TRACKERS, BLOCK_RESOURCE, false);\n'
        '                settings = BLOCK_RESOURCE;\n'
        '            }\n'
        '            // SANDIUM_SHIELDS_TWO_STATE_LEGACY_MIGRATION_END'
    )
    return replace_once(source, old, new, "SANDIUM_SHIELDS_TWO_STATE_LEGACY_MIGRATION_BEGIN",
                        "Legacy Standard-to-On migration")

def transform_privacy_settings(source: str) -> str:
    old_change = (
        '        } else if (PREF_BLOCK_TRACKERS_ADS.equals(key)) {\n'
        '            if (newValue instanceof String) {\n'
        '                final String newStringValue = String.valueOf(newValue);\n'
        '                switch (newStringValue) {\n'
        '                    case BraveShieldsContentSettings.BLOCK_RESOURCE:\n'
        '                        BraveShieldsContentSettings.setTrackersPref(newStringValue);\n'
        '                        mAdsTrakersBlockPref.setSummary(getActivity().getResources().getString(\n'
        '                                R.string.block_trackers_ads_option_1));\n'
        '                        mAdsTrakersBlockPref.setCheckedIndex(0);\n'
        '                        break;\n'
        '                    case BraveShieldsContentSettings.DEFAULT:\n'
        '                        BraveShieldsContentSettings.setTrackersPref(newStringValue);\n'
        '                        mAdsTrakersBlockPref.setSummary(getActivity().getResources().getString(\n'
        '                                R.string.block_trackers_ads_option_2));\n'
        '                        mAdsTrakersBlockPref.setCheckedIndex(1);\n'
        '                        break;\n'
        '                    default:\n'
        '                        BraveShieldsContentSettings.setTrackersPref(\n'
        '                                BraveShieldsContentSettings.ALLOW_RESOURCE);\n'
        '                        mAdsTrakersBlockPref.setSummary(getActivity().getResources().getString(\n'
        '                                R.string.block_trackers_ads_option_3));\n'
        '                        mAdsTrakersBlockPref.setCheckedIndex(2);\n'
        '                        break;\n'
        '                }\n'
        '            }\n'
        '        }'
    )
    new_change = (
        '        } else if (PREF_BLOCK_TRACKERS_ADS.equals(key)) {\n'
        '            // SANDIUM_SHIELDS_TWO_STATE_GLOBAL_CHANGE_BEGIN\n'
        '            if (newValue instanceof String) {\n'
        '                String selected = String.valueOf(newValue);\n'
        '                boolean isOn = !BraveShieldsContentSettings.ALLOW_RESOURCE.equals(selected);\n'
        '                String storedValue = isOn ? BraveShieldsContentSettings.BLOCK_RESOURCE\n'
        '                                           : BraveShieldsContentSettings.ALLOW_RESOURCE;\n'
        '                BraveShieldsContentSettings.setTrackersPref(storedValue);\n'
        '                mAdsTrakersBlockPref.setSummary(getActivity().getResources().getString(\n'
        '                        isOn ? R.string.sandium_trackers_ads_on : R.string.sandium_trackers_ads_off));\n'
        '                mAdsTrakersBlockPref.setCheckedIndex(isOn ? 0 : 1);\n'
        '            }\n'
        '            // SANDIUM_SHIELDS_TWO_STATE_GLOBAL_CHANGE_END\n'
        '        }'
    )
    source = replace_once(source, old_change, new_change, "SANDIUM_SHIELDS_TWO_STATE_GLOBAL_CHANGE_BEGIN",
                          "Global Shields preference listener")

    old_init = (
        '        if (blockAdTrackersPref.equals(BraveShieldsContentSettings.BLOCK_RESOURCE)) {\n'
        '            mAdsTrakersBlockPref.setCheckedIndex(0);\n'
        '            mAdsTrakersBlockPref.setSummary(\n'
        '                    getActivity().getResources().getString(R.string.block_trackers_ads_option_1));\n'
        '        } else if (blockAdTrackersPref.equals(BraveShieldsContentSettings.DEFAULT)) {\n'
        '            mAdsTrakersBlockPref.setCheckedIndex(1);\n'
        '            mAdsTrakersBlockPref.setSummary(\n'
        '                    getActivity().getResources().getString(R.string.block_trackers_ads_option_2));\n'
        '        } else if (blockAdTrackersPref.equals(BraveShieldsContentSettings.ALLOW_RESOURCE)) {\n'
        '            mAdsTrakersBlockPref.setCheckedIndex(2);\n'
        '            mAdsTrakersBlockPref.setSummary(\n'
        '                    getActivity().getResources().getString(R.string.block_trackers_ads_option_3));\n'
        '        }'
    )
    new_init = (
        '        // SANDIUM_SHIELDS_TWO_STATE_GLOBAL_INIT_BEGIN\n'
        '        boolean trackersOn = !BraveShieldsContentSettings.ALLOW_RESOURCE.equals(blockAdTrackersPref);\n'
        '        mAdsTrakersBlockPref.setCheckedIndex(trackersOn ? 0 : 1);\n'
        '        mAdsTrakersBlockPref.setSummary(\n'
        '                getActivity().getResources().getString(\n'
        '                        trackersOn ? R.string.sandium_trackers_ads_on : R.string.sandium_trackers_ads_off));'
    )
    new_init += '\n        // SANDIUM_SHIELDS_TWO_STATE_GLOBAL_INIT_END'
    source = replace_once(source, old_init, new_init, "SANDIUM_SHIELDS_TWO_STATE_GLOBAL_INIT_BEGIN",
                          "Global Shields current-state summary")

    old_search = (
        '                    int trackersSummaryId = R.string.block_trackers_ads_option_2;\n'
        '                    if (trackersPref.equals(BraveShieldsContentSettings.BLOCK_RESOURCE)) {\n'
        '                        trackersSummaryId = R.string.block_trackers_ads_option_1;\n'
        '                    } else if (trackersPref.equals(BraveShieldsContentSettings.ALLOW_RESOURCE)) {\n'
        '                        trackersSummaryId = R.string.block_trackers_ads_option_3;\n'
        '                    }'
    )
    new_search = (
        '                    // SANDIUM_SHIELDS_TWO_STATE_SEARCH_SUMMARY_BEGIN\n'
        '                    int trackersSummaryId = trackersPref.equals(BraveShieldsContentSettings.ALLOW_RESOURCE)\n'
        '                            ? R.string.sandium_trackers_ads_off\n'
        '                            : R.string.sandium_trackers_ads_on;\n'
        '                    // SANDIUM_SHIELDS_TWO_STATE_SEARCH_SUMMARY_END'
    )
    return replace_once(source, old_search, new_search, "SANDIUM_SHIELDS_TWO_STATE_SEARCH_SUMMARY_BEGIN",
                        "Global Shields search summary")

def transform_native_default(source: str) -> str:
    old = (
        'using CosmeticFilteringSetting = traits::BraveShieldsSetting<\n'
        '    /*content_settings_type=*/ContentSettingsType::BRAVE_COSMETIC_FILTERING,\n'
        '    /*SettingType=*/ControlType,\n'
        '    /*default_value=*/ControlType::BLOCK_THIRD_PARTY>;'
    )
    new = (
        'using CosmeticFilteringSetting = traits::BraveShieldsSetting<\n'
        '    /*content_settings_type=*/ContentSettingsType::BRAVE_COSMETIC_FILTERING,\n'
        '    /*SettingType=*/ControlType,\n'
        '    /*default_value=*/ControlType::BLOCK>;  // Sandium: On/Aggressive is the default.'
    )
    return replace_once(source, old, new, "Sandium: On/Aggressive is the default.",
                        "Native Shields default On")

def transform_native_default_test(source: str) -> str:
    old = (
        '    EXPECT_EQ(brave_shields::ControlType::BLOCK_THIRD_PARTY, initial_value);\n'
        '    EXPECT_EQ(brave_shields::ControlType::BLOCK_THIRD_PARTY,\n'
        '              brave_shields::CosmeticFilteringSetting::kDefaultValue);'
    )
    new = (
        '    // Sandium Shields aggressive default\n'
        '    EXPECT_EQ(brave_shields::ControlType::BLOCK, initial_value);\n'
        '    EXPECT_EQ(brave_shields::ControlType::BLOCK,\n'
        '              brave_shields::CosmeticFilteringSetting::kDefaultValue);'
    )
    return replace_once(source, old, new, "Sandium Shields aggressive default",
                        "Native Shields default test expectation")

def verify(core: Path) -> None:
    array = read(core / "android/java/brave-res/values/array.xml")
    layout = read(core / "android/java/brave-res/layout/brave_trackers_ads_panel.xml")
    unified = read(core / "android/java/org/chromium/chrome/browser/shields/BraveUnifiedPanelHandler.java")
    privacy = read(core / "android/java/org/chromium/chrome/browser/privacy/settings/BravePrivacySettings.java")
    content = read(core / "android/java/org/chromium/chrome/browser/preferences/website/BraveShieldsContentSettings.java")
    dialog = read(core / "android/java/org/chromium/chrome/browser/settings/BravePreferenceDialogFragment.java")
    native = read(core / "components/brave_shields/core/common/brave_shields_settings_values.h")
    checks = {
        "two global entries": array.count("@string/sandium_trackers_ads_on") == 1 and array.count("@string/sandium_trackers_ads_off") == 1,
        "no Standard site row": "trackers_standard_option" not in layout and "trackers_standard_radio" not in layout,
        "site labels are On/Off": 'android:text="@string/sandium_trackers_ads_on"' in layout and 'android:text="@string/sandium_trackers_ads_off"' in layout,
        "site On/Off maps Aggressive/Allow": "BraveShieldsContentSettings.BLOCK_RESOURCE" in unified and "BraveShieldsContentSettings.ALLOW_RESOURCE" in unified,
        "no Standard site control": "trackers_standard_radio" not in unified and "trackers_standard_option" not in unified,
        "global two-state indices": "setCheckedIndex(isOn ? 0 : 1)" in privacy,
        "legacy settings migrate to On": "settings.equals(BLOCK_THIRDPARTY_RESOURCE) || settings.equals(DEFAULT)" in content,
        "global option index 1 is Allow": "SANDIUM_SHIELDS_TWO_STATE_DIALOG_MAPPING_BEGIN" in dialog and "ALLOW_RESOURCE" in dialog,
        "native default aggressive": "default_value=*/ControlType::BLOCK>" in native,
    }
    failures = [name for name, ok in checks.items() if not ok]
    if failures:
        raise RuntimeError("Two-state Shields verification failed: " + ", ".join(failures))
    print("SANDIUM_SHIELDS_TWO_STATE_VERIFY=PASS global=On/Off site=On/Off default=Aggressive legacy_standard=migrated")

def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply-sandium-shields-two-state.py <brave-core-dir>")
    core = Path(sys.argv[1]).resolve()
    if not core.is_dir():
        raise SystemExit(f"Brave Core directory does not exist: {core}")
    tag = subprocess.run(["git", "-C", str(core), "describe", "--tags", "--exact-match"],
                         check=True, capture_output=True, text=True).stdout.strip()
    sha = subprocess.run(["git", "-C", str(core), "rev-parse", "HEAD"],
                         check=True, capture_output=True, text=True).stdout.strip()
    if tag != EXPECTED_CORE_TAG or sha != EXPECTED_CORE_SHA:
        raise SystemExit(f"SANDIUM_SHIELDS_PIN=FAIL expected={EXPECTED_CORE_TAG}@{EXPECTED_CORE_SHA} actual={tag}@{sha}")
    print(f"SANDIUM_SHIELDS_PIN=PASS {tag}@{sha}")

    write(core / "android/java/brave-res/values/array.xml", transform_array_xml, "GLOBAL_OPTIONS")
    write(core / "android/java/brave-res/xml/brave_privacy_preferences.xml", transform_privacy_xml, "GLOBAL_DIALOG")
    write(core / "android/java/brave-res/layout/brave_trackers_ads_panel.xml", transform_site_layout, "SITE_OPTIONS")
    write(core / "android/java/org/chromium/chrome/browser/shields/BraveUnifiedPanelHandler.java", transform_site_panel, "SITE_PANEL")
    write(core / "android/java/org/chromium/chrome/browser/settings/BravePreferenceDialogFragment.java", transform_dialog_fragment, "GLOBAL_DIALOG_MAPPING")
    write(core / "android/java/org/chromium/chrome/browser/privacy/settings/BravePrivacySettings.java", transform_privacy_settings, "GLOBAL_SETTINGS")
    write(core / "android/java/org/chromium/chrome/browser/preferences/website/BraveShieldsContentSettings.java", transform_shields_content_settings, "LEGACY_MIGRATION")
    write(core / "components/brave_shields/core/common/brave_shields_settings_values.h", transform_native_default, "NATIVE_DEFAULT")
    write(core / "browser/content_settings/brave_content_settings_registry_unittest.cc", transform_native_default_test, "NATIVE_TEST")
    verify(core)

if __name__ == "__main__":
    main()
