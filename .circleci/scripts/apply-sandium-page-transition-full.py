#!/usr/bin/env python3
"""Full-mode Sandium page-transition overlay for pinned Brave/Chromium sources.

This deliberately extends the existing, pin-guarded Android blur overlay. It does
not touch Brave Shields, subscriptions, filter data, or any ad-block source.
"""
from pathlib import Path
import subprocess
import sys

BRAVE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
CHROMIUM_SHA = "d331de35ca8ab1358c7a17e4bd41627d55eaef51"
BLUR_PREF_KEY = "sandium_page_transition_blur_level"
DARKEN_PREF_KEY = "sandium_page_transition_darken"
ANDROID_BUILD_GN = Path("android/BUILD.gn")
BLUR_ICON_PATH = Path("android/java/brave-res/drawable/ic_sandium_page_transition_blur.xml")
DARKEN_ICON_PATH = Path("android/java/brave-res/drawable/ic_sandium_page_transition_darken.xml")
REPO_ROOT = Path(__file__).resolve().parents[2]
BLUR_ICON_SOURCE = REPO_ROOT / "brave" / BLUR_ICON_PATH
DARKEN_ICON_SOURCE = REPO_ROOT / "brave" / DARKEN_ICON_PATH
BLUR_ICON_ENTRY = '    "java/brave-res/drawable/ic_sandium_page_transition_blur.xml",\n'
DARKEN_ICON_ENTRY = '    "java/brave-res/drawable/ic_sandium_page_transition_darken.xml",\n'
BUILD_GN_ICON_ANCHOR = '    "java/brave-res/drawable/ic_theme_system.xml",\n'
FEATURE = "AndroidNavigationBlurTransitionAnimation"

STARTUP = Path("chrome/android/java/src/org/chromium/chrome/browser/base/SplitCompatApplication.java")
APPEARANCE_XML = Path("android/java/brave-res/xml/brave_appearance_preferences.xml")
APPEARANCE_JAVA = Path("android/java/org/chromium/chrome/browser/settings/AppearancePreferences.java")
MAIN_PREFERENCES_JAVA = Path("android/java/org/chromium/chrome/browser/settings/BraveMainPreferencesBase.java")
APPEARANCE_TEST = Path("android/javatests/org/chromium/chrome/browser/settings/BraveAppearancePreferencesTest.java")
STRINGS_GRD = Path("browser/ui/android/strings/android_brave_strings.grd")
TRANSITION_CC = Path("content/browser/navigation_transitions/blur_transition_animation_manager.cc")
TRANSITION_H = Path("content/browser/navigation_transitions/blur_transition_animation_manager.h")
FEATURES_CC = Path("content/public/common/content_features.cc")
FEATURES_H = Path("content/public/common/content_features.h")

def replace_once_or_done(source: str, old: str, new: str, label: str) -> str:
    # Check the complete replacement first because many insertions deliberately
    # retain the original anchor text as part of the new block.
    if new in source:
        return source
    count = source.count(old)
    if count == 1:
        return source.replace(old, new, 1)
    raise RuntimeError(f"{label}: expected one old anchor or an already-applied replacement; old_count={count}")

def normalized_lines(value: str) -> str:
    return "\n".join(line.strip() for line in value.splitlines())

def insert_marked_before(source: str, anchor: str, begin: str, end: str, block: str, label: str) -> str:
    begin_count, end_count = source.count(begin), source.count(end)
    if begin_count or end_count:
        if begin_count != 1 or end_count != 1 or source.index(begin) > source.index(end):
            raise RuntimeError(f"{label}: partial, duplicate, or reversed markers")
        marker_start = source.index(begin)
        marker_end = source.index(end) + len(end)
        if normalized_lines(block) not in normalized_lines(source[marker_start:marker_end]):
            raise RuntimeError(f"{label}: marked block contents differ from expected content")
        return source
    if source.count(anchor) != 1:
        raise RuntimeError(f"{label}: expected one insertion anchor; found {source.count(anchor)}")
    return source.replace(anchor, block + anchor, 1)

def transform_startup(source: str) -> str:
    source = replace_once_or_done(
        source,
        "nav-animation-fade-hold-duration-ms/300/nav-animation-fade-out-duration-ms/150",
        "nav-animation-fade-hold-duration-ms/450/nav-animation-fade-out-duration-ms/225",
        "Medium duration +50%",
    )
    source = replace_once_or_done(
        source,
        "nav-animation-fade-hold-duration-ms/450/nav-animation-fade-out-duration-ms/200",
        "nav-animation-fade-hold-duration-ms/675/nav-animation-fade-out-duration-ms/300",
        "High duration +50%",
    )
    level_read = (
        '        String level = ContextUtils.getAppSharedPreferences().getString("sandium_page_transition_blur_level", "default");\n'
    )
    darken_read = (
        '        boolean darken = ContextUtils.getAppSharedPreferences().getBoolean("sandium_page_transition_darken", false);\n'
    )
    source = replace_once_or_done(
        source,
        level_read,
        level_read + darken_read + '        darken = darken && !"default".equals(level);\\n',
        "Read persisted Darken setting before native feature initialization",
    )
    source = replace_once_or_done(
        source,
        '        final String selectedFeature = feature + ":" + params;\n',
        '        final String selectedFeature = feature + ":" + params + "/nav-animation-darken/" + (darken ? "true" : "false");\n',
        "Pass Darken FeatureParam to Chromium",
    )
    checks = {
        "Medium hold 450 ms": "nav-animation-fade-hold-duration-ms/450/nav-animation-fade-out-duration-ms/225",
        "High hold 675 ms": "nav-animation-fade-hold-duration-ms/675/nav-animation-fade-out-duration-ms/300",
        "Darken preference read": darken_read.strip(),
        "Darken native parameter": '"/nav-animation-darken/" + (darken ? "true" : "false")',
    }
    for label, snippet in checks.items():
        if snippet not in source:
            raise RuntimeError(f"Startup transition validation failed: {label}")
    return source

XML_DARKEN_BEGIN = "    <!-- SANDIUM_PAGE_TRANSITION_DARKEN_BEGIN -->"
XML_DARKEN_END = "    <!-- SANDIUM_PAGE_TRANSITION_DARKEN_END -->"
XML_DARKEN_BLOCK = (
    XML_DARKEN_BEGIN + "\n"
    "    <org.chromium.components.browser_ui.settings.ChromeSwitchPreference\n"
    '        android:key="sandium_page_transition_darken"\n'
    '        android:icon="@drawable/ic_sandium_page_transition_darken"\n'
    '        android:persistent="false"\n'
    '        android:title="@string/sandium_page_transition_darken_title"\n'
    '        android:summary="@string/sandium_page_transition_darken_summary" />\n'
    + XML_DARKEN_END + "\n"
)

def transform_appearance_xml(source: str) -> str:
    blur_key = '        android:key="sandium_page_transition_blur_level"\n'
    source = replace_once_or_done(source, blur_key, blur_key + '        android:icon="@drawable/ic_sandium_page_transition_blur"\n', "Page transition blur preference icon")
    source = insert_marked_before(
        source,
        "    <!-- SANDIUM_PAGE_TRANSITION_BLUR_END -->\n",
        XML_DARKEN_BEGIN,
        XML_DARKEN_END,
        XML_DARKEN_BLOCK,
        "Appearance Darken switch XML",
    )
    if source.count('android:key="sandium_page_transition_darken"') != 1:
        raise RuntimeError("Appearance XML must contain exactly one Darken preference")
    return source

GRD_DARKEN_BEGIN = "      <!-- SANDIUM_PAGE_TRANSITION_DARKEN_STRINGS_BEGIN -->"
GRD_DARKEN_END = "      <!-- SANDIUM_PAGE_TRANSITION_DARKEN_STRINGS_END -->"
GRD_DARKEN_BLOCK = (
    GRD_DARKEN_BEGIN + "\n"
    '      <message name="IDS_SANDIUM_PAGE_TRANSITION_DARKEN_TITLE" desc="Title for the page transition darkening switch.">\n'
    "        Darken transition\n"
    "      </message>\n"
    '      <message name="IDS_SANDIUM_PAGE_TRANSITION_DARKEN_SUMMARY" desc="Summary for the page transition darkening switch.">\n'
    "        Dim the outgoing page during the transition\n"
    "      </message>\n"
    + GRD_DARKEN_END + "\n"
)

def transform_grd(source: str) -> str:
    source = insert_marked_before(
        source,
        "      <!-- SANDIUM_PAGE_TRANSITION_BLUR_STRINGS_END -->\n",
        GRD_DARKEN_BEGIN,
        GRD_DARKEN_END,
        GRD_DARKEN_BLOCK,
        "Darken preference strings",
    )
    for name in ("IDS_SANDIUM_PAGE_TRANSITION_DARKEN_TITLE", "IDS_SANDIUM_PAGE_TRANSITION_DARKEN_SUMMARY"):
        if source.count(f'name="{name}"') != 1:
            raise RuntimeError(f"GRD validation failed: {name}")
    return source

JAVA_PREF_BEGIN = "    // SANDIUM_PAGE_TRANSITION_BLUR_PREF_BEGIN"
JAVA_PREF_END = "    // SANDIUM_PAGE_TRANSITION_BLUR_PREF_END"
JAVA_DARKEN_PREF = (
    '    /* package */ static final String PREF_SANDIUM_PAGE_TRANSITION_DARKEN = "sandium_page_transition_darken";'
)

JAVA_INIT_END = "        // SANDIUM_PAGE_TRANSITION_BLUR_INIT_END"
JAVA_DARKEN_INIT_BEGIN = "        // SANDIUM_PAGE_TRANSITION_DARKEN_INIT_BEGIN"
JAVA_DARKEN_INIT_END = "        // SANDIUM_PAGE_TRANSITION_DARKEN_INIT_END"
JAVA_DARKEN_INIT_BLOCK = (
    JAVA_DARKEN_INIT_BEGIN + "\n"
    "        ChromeSwitchPreference pageTransitionDarken =\n"
    "                (ChromeSwitchPreference) findPreference(PREF_SANDIUM_PAGE_TRANSITION_DARKEN);\n"
    "        if (pageTransitionDarken != null) {\n"
    "            String blurLevel = ContextUtils.getAppSharedPreferences()\n"
    "                    .getString(PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL, \"default\");\n"
    "            boolean blurEnabled = !\"default\".equals(blurLevel);\n"
    "            pageTransitionDarken.setEnabled(blurEnabled);\n"
    "            boolean darkenEnabled = blurEnabled && ContextUtils.getAppSharedPreferences()\n"
    "                    .getBoolean(PREF_SANDIUM_PAGE_TRANSITION_DARKEN, false);\n"
    "            pageTransitionDarken.setChecked(darkenEnabled);\n"
    "            if (!blurEnabled) {\n"
    "                ContextUtils.getAppSharedPreferences().edit()\n"
    "                        .putBoolean(PREF_SANDIUM_PAGE_TRANSITION_DARKEN, false).apply();\n"
    "            }\n"
    "            pageTransitionDarken.setOnPreferenceChangeListener(this);\n"
    "        }\n"
    + JAVA_DARKEN_INIT_END + "\n"
)
)

JAVA_CHANGE_ANCHOR = "        if (BravePreferenceKeys.BRAVE_BOTTOM_TOOLBAR_ENABLED_KEY.equals(key)) {\n"
JAVA_DARKEN_CHANGE_BEGIN = "        // SANDIUM_PAGE_TRANSITION_DARKEN_CHANGE_BEGIN"
JAVA_DARKEN_CHANGE_END = "        // SANDIUM_PAGE_TRANSITION_DARKEN_CHANGE_END"
JAVA_DARKEN_CHANGE_BLOCK = (
    JAVA_DARKEN_CHANGE_BEGIN + "\n"
    "        if (PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL.equals(key)) {\n"
    "            if (!(newValue instanceof String)) return false;\n"
    "            boolean blurEnabled = !\"default\".equals(newValue);\n"
    "            Preference darkenPreference = findPreference(PREF_SANDIUM_PAGE_TRANSITION_DARKEN);\n"
    "            if (darkenPreference != null) darkenPreference.setEnabled(blurEnabled);\n"
    "            if (!blurEnabled) {\n"
    "                boolean saved = ContextUtils.getAppSharedPreferences().edit()\n"
    "                        .putBoolean(PREF_SANDIUM_PAGE_TRANSITION_DARKEN, false).commit();\n"
    "                if (!saved) return false;\n"
    "                if (darkenPreference instanceof ChromeSwitchPreference) {\n"
    "                    ((ChromeSwitchPreference) darkenPreference).setChecked(false);\n"
    "                }\n"
    "            }\n"
    "        }\n"
    "        if (PREF_SANDIUM_PAGE_TRANSITION_DARKEN.equals(key)) {\n"
    "            if (!(newValue instanceof Boolean)) return false;\n"
    "            String blurLevel = ContextUtils.getAppSharedPreferences()\n"
    "                    .getString(PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL, \"default\");\n"
    "            if (\"default\".equals(blurLevel) && (Boolean) newValue) return false;\n"
    "            boolean saved = ContextUtils.getAppSharedPreferences().edit()\n"
    "                    .putBoolean(PREF_SANDIUM_PAGE_TRANSITION_DARKEN, (Boolean) newValue)\n"
    "                    .commit();\n"
    "            if (!saved) return false;\n"
    "            shouldRelaunch = true;\n"
    "        }\n"
    + JAVA_DARKEN_CHANGE_END + "\n"
)
)

JAVA_HELPER_ANCHOR = "    // SANDIUM_PAGE_TRANSITION_BLUR_PREF_END\n"
JAVA_ORDER_BEGIN = "        // SANDIUM_PAGE_TRANSITION_BLUR_ORDER_BEGIN"
JAVA_ORDER_END = "        // SANDIUM_PAGE_TRANSITION_BLUR_ORDER_END"

def transform_appearance_java(source: str) -> str:
    if source.count(JAVA_PREF_BEGIN) != 1 or source.count(JAVA_PREF_END) != 1:
        raise RuntimeError("Appearance Java: base blur preference markers missing or duplicated")
    source = insert_marked_before(
        source,
        JAVA_PREF_END + "\n",
        "    // SANDIUM_PAGE_TRANSITION_DARKEN_PREF_BEGIN",
        "    // SANDIUM_PAGE_TRANSITION_DARKEN_PREF_END",
        "    // SANDIUM_PAGE_TRANSITION_DARKEN_PREF_BEGIN\n" + JAVA_DARKEN_PREF + "\n"
        "    // SANDIUM_PAGE_TRANSITION_DARKEN_PREF_END\n",
        "Darken preference key",
    )
    source = insert_marked_before(
        source,
        JAVA_INIT_END + "\n",
        JAVA_DARKEN_INIT_BEGIN,
        JAVA_DARKEN_INIT_END,
        JAVA_DARKEN_INIT_BLOCK,
        "Darken preference initialization",
    )
    source = insert_marked_before(
        source,
        JAVA_CHANGE_ANCHOR,
        JAVA_DARKEN_CHANGE_BEGIN,
        JAVA_DARKEN_CHANGE_END,
        JAVA_DARKEN_CHANGE_BLOCK,
        "Darken preference change handler",
    )
    # Keep the Darken switch immediately after the blur-level selector and shift
    # the remaining Appearance rows down by one unique order slot.
    replacements = (
        ("setPreferenceOrder(PREF_BRAVE_DISABLE_SHARING_HUB, 11);",
         "setPreferenceOrder(PREF_SANDIUM_PAGE_TRANSITION_DARKEN, 11);\n        setPreferenceOrder(PREF_BRAVE_DISABLE_SHARING_HUB, 12);"),
        ("setPreferenceOrder(PREF_SHOW_BRAVE_REWARDS_ICON, 12);", "setPreferenceOrder(PREF_SHOW_BRAVE_REWARDS_ICON, 13);"),
        ("setPreferenceOrder(PREF_ADS_SWITCH, 13);", "setPreferenceOrder(PREF_ADS_SWITCH, 14);"),
        ("setPreferenceOrder(AppearanceSettingsFragment.PREF_BOOKMARK_BAR, 14);", "setPreferenceOrder(AppearanceSettingsFragment.PREF_BOOKMARK_BAR, 15);"),
        ("setPreferenceOrder(PREF_BRAVE_ENABLE_TAB_GROUPS, 15);", "setPreferenceOrder(PREF_BRAVE_ENABLE_TAB_GROUPS, 16);"),
        ("setPreferenceOrder(PREF_SHOW_UNDO_WHEN_TABS_CLOSED, 16);", "setPreferenceOrder(PREF_SHOW_UNDO_WHEN_TABS_CLOSED, 17);"),
    )
    for old, new in replacements:
        source = replace_once_or_done(source, old, new, "Appearance order")
    for snippet in (
        JAVA_DARKEN_PREF,
        "findPreference(PREF_SANDIUM_PAGE_TRANSITION_DARKEN)",
        "pageTransitionDarken.setEnabled(blurEnabled)",
        "if (\\\"default\\\".equals(blurLevel) && (Boolean) newValue) return false;",
        ".getBoolean(PREF_SANDIUM_PAGE_TRANSITION_DARKEN, false)",
        ".putBoolean(PREF_SANDIUM_PAGE_TRANSITION_DARKEN, (Boolean) newValue)",
        "setPreferenceOrder(PREF_SANDIUM_PAGE_TRANSITION_DARKEN, 11);",
    ):
        if snippet not in source:
            raise RuntimeError(f"Appearance Java validation failed: {snippet}")
    return source

MAIN_ICON_BEGIN = "        // SANDIUM_APPEARANCE_ICON_BEGIN"
MAIN_ICON_END = "        // SANDIUM_APPEARANCE_ICON_END"
MAIN_ICON_BLOCK = (
    MAIN_ICON_BEGIN + "\n"
    "        updatePreferenceIcon(PREF_APPEARANCE, R.drawable.ic_appearance);\n"
    + MAIN_ICON_END + "\n"
)

def transform_main_preferences(source: str) -> str:
    begin_count, end_count = source.count(MAIN_ICON_BEGIN), source.count(MAIN_ICON_END)
    if begin_count or end_count:
        if begin_count != 1 or end_count != 1 or source.index(MAIN_ICON_BEGIN) > source.index(MAIN_ICON_END):
            raise RuntimeError("Main Appearance entry icon: malformed markers")
        marker_start = source.index(MAIN_ICON_BEGIN)
        marker_end = source.index(MAIN_ICON_END) + len(MAIN_ICON_END)
        if normalized_lines(MAIN_ICON_BLOCK) not in normalized_lines(source[marker_start:marker_end]):
            raise RuntimeError("Main Appearance entry icon: marked block differs from expected")
    else:
        anchor = "    private void updatePreferenceIcons() {\n"
        if source.count(anchor) != 1:
            raise RuntimeError("Main Appearance entry icon: updater method anchor missing or ambiguous")
        # Insert inside the method body, immediately after its opening brace.
        source = source.replace(anchor, anchor + MAIN_ICON_BLOCK, 1)
    if "updatePreferenceIcon(PREF_APPEARANCE, R.drawable.ic_appearance);" not in source:
        raise RuntimeError("Main Appearance entry icon was not installed")
    return source

def add_import(source: str, line: str, anchor: str, label: str) -> str:
    if source.count(line) == 1:
        return source
    if source.count(line) > 1:
        raise RuntimeError(f"{label}: duplicate import")
    if source.count(anchor) != 1:
        raise RuntimeError(f"{label}: import anchor missing or ambiguous")
    return source.replace(anchor, anchor + line, 1)

TEST_DARKEN_BEGIN = "    // SANDIUM_PAGE_TRANSITION_DARKEN_TEST_BEGIN"
TEST_DARKEN_END = "    // SANDIUM_PAGE_TRANSITION_DARKEN_TEST_END"
TEST_DARKEN_BLOCK = (
    TEST_DARKEN_BEGIN + "\n"
    "    @Test\n"
    "    @SmallTest\n"
    "    public void testPageTransitionDarkenPreferenceRestoresSavedChoice() {\n"
    "        String key = AppearancePreferences.PREF_SANDIUM_PAGE_TRANSITION_DARKEN;\n"
    "        ContextUtils.getAppSharedPreferences().edit().putBoolean(key, true).commit();\n"
    "        startSettings();\n"
    "        Preference preference = mAppearancePreferences.findPreference(key);\n"
    "        Assert.assertNotNull(preference);\n"
    "        Assert.assertTrue(((ChromeSwitchPreference) preference).isChecked());\n"
    "        ContextUtils.getAppSharedPreferences().edit().remove(key).commit();\n"
    "    }\n"
    + TEST_DARKEN_END + "\n"
)

def transform_appearance_test(source: str) -> str:
    source = add_import(source, "import org.chromium.base.ContextUtils;\n",
                        "import org.chromium.base.BraveFeatureList;\n", "Darken test ContextUtils")
    source = add_import(source, "import org.chromium.components.browser_ui.settings.ChromeSwitchPreference;\n",
                        "import org.chromium.chrome.browser.flags.ChromeFeatureList;\n", "Darken test switch preference")
    source = replace_once_or_done(
        source,
        "            AppearancePreferences.PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL,\n",
        "            AppearancePreferences.PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL,\n"
        "            AppearancePreferences.PREF_SANDIUM_PAGE_TRANSITION_DARKEN,\n",
        "Appearance order instrumentation expectation",
    )
    source = insert_marked_before(
        source,
        "    public void testDynamicColorsPreferenceAvailability() {\n",
        TEST_DARKEN_BEGIN,
        TEST_DARKEN_END,
        TEST_DARKEN_BLOCK,
        "Darken preference instrumentation test",
    )
    if source.count("testPageTransitionDarkenPreferenceRestoresSavedChoice") != 1:
        raise RuntimeError("Darken instrumentation test was not added exactly once")
    return source

FEATURE_PARAM_CC_ANCHOR = (
    'const base::FeatureParam<double> kAndroidNavigationAnimationBlurSigma{\n'
    '    &kAndroidNavigationBlurTransitionAnimation, "nav-animation-blur-sigma",\n'
    '    3.0};\n'
)
FEATURE_PARAM_CC_BLOCK = (
    FEATURE_PARAM_CC_ANCHOR
    + 'const base::FeatureParam<bool> kAndroidNavigationAnimationDarken{\n'
    + '    &kAndroidNavigationBlurTransitionAnimation, "nav-animation-darken", false};\n'
)
FEATURE_PARAM_H_ANCHOR = (
    "CONTENT_EXPORT extern const base::FeatureParam<double>\n"
    "    kAndroidNavigationAnimationBlurSigma;\n"
)
FEATURE_PARAM_H_BLOCK = (
    FEATURE_PARAM_H_ANCHOR
    + "CONTENT_EXPORT extern const base::FeatureParam<bool>\n"
    + "    kAndroidNavigationAnimationDarken;\n"
)

def transform_features_cc(source: str) -> str:
    if FEATURE_PARAM_CC_BLOCK not in source:
        if source.count(FEATURE_PARAM_CC_ANCHOR) != 1:
            raise RuntimeError("content_features.cc: navigation blur FeatureParam anchor changed")
        source = source.replace(FEATURE_PARAM_CC_ANCHOR, FEATURE_PARAM_CC_BLOCK, 1)
    if source.count("kAndroidNavigationAnimationDarken") != 1:
        raise RuntimeError("content_features.cc: Darken FeatureParam count mismatch")
    return source

def transform_features_h(source: str) -> str:
    if FEATURE_PARAM_H_BLOCK not in source:
        if source.count(FEATURE_PARAM_H_ANCHOR) != 1:
            raise RuntimeError("content_features.h: navigation blur FeatureParam declaration anchor changed")
        source = source.replace(FEATURE_PARAM_H_ANCHOR, FEATURE_PARAM_H_BLOCK, 1)
    if source.count("kAndroidNavigationAnimationDarken") != 1:
        raise RuntimeError("content_features.h: Darken FeatureParam declaration count mismatch")
    return source

def transform_transition_cc(source: str) -> str:
    source = replace_once_or_done(
        source,
        '#include "base/metrics/histogram_functions.h"\n',
        '#include "base/feature_list.h"\n#include "base/metrics/histogram_functions.h"\n',
        "Transition FeatureList include",
    )
    source = replace_once_or_done(
        source,
        '#include "content/public/common/content_features.h"\n',
        '#include "content/public/common/content_features.h"\n#include "third_party/blink/public/common/features.h"\n',
        "Blink dark-mode feature include",
    )
    fallback_old = (
        "  SkColor4f background_color = SkColors::kWhite;\n"
        "  if (auto theme_color = delegate->GetThemeColor()) {\n"
        "    background_color = SkColor4f::FromColor(*theme_color);\n"
        "  }\n"
    )
    fallback_new = (
        "  SkColor4f background_color = SkColors::kWhite;\n"
        "  if (base::FeatureList::IsEnabled(\n"
        "          blink::features::kForceWebContentsDarkMode)) {\n"
        "    background_color = SkColors::kBlack;\n"
        "  } else if (auto theme_color = delegate->GetThemeColor()) {\n"
        "    background_color = SkColor4f::FromColor(*theme_color);\n"
        "  }\n"
    )
    source = replace_once_or_done(source, fallback_old, fallback_new, "Night Mode-aware transition fallback")
    dark_layer_block = (
        "  if (features::kAndroidNavigationAnimationDarken.Get()) {\n"
        "    darken_layer_ = cc::slim::SolidColorLayer::Create();\n"
        "    darken_layer_->SetIsDrawable(true);\n"
        "    darken_layer_->SetBounds(native_view->GetPhysicalBackingSize());\n"
        "    darken_layer_->SetBackgroundColor(SkColors::kBlack);\n"
        "    darken_layer_->SetOpacity(0.20f);\n"
        "  }\n"
    )
    source = insert_marked_before(
        source,
        "  fallback_color_layer_->SetOpacity(0.0f);\n\n"
        "  SetAnimationState(AnimationState::kNone);\n",
        "  // SANDIUM_DARKEN_LAYER_CREATE_BEGIN",
        "  // SANDIUM_DARKEN_LAYER_CREATE_END",
        "  // SANDIUM_DARKEN_LAYER_CREATE_BEGIN\n" + dark_layer_block + "  // SANDIUM_DARKEN_LAYER_CREATE_END\n",
        "Create Darken compositor layer",
    )
    fade_old = (
        "      if (fallback_color_layer_) {\n"
        "        fallback_color_layer_->SetOpacity(initial_fallback_opacity_ *\n"
        "                                          adjusted_opacity_multiplier);\n"
        "      }\n"
    )
    fade_new = (
        fade_old
        + "      if (darken_layer_) {\n"
        + "        darken_layer_->SetOpacity(initial_darken_opacity_ *\n"
        + "                                  adjusted_opacity_multiplier);\n"
        + "      }\n"
    )
    source = replace_once_or_done(source, fade_old, fade_new, "Fade Darken layer with blur")
    fallback_complete_old = (
        "      SetAnimationState(AnimationState::kFallbackShown);\n"
        "      window_observation_.Reset();\n"
        "      // Drop the old page's surface now that it's completely covered.\n"
    )
    fallback_complete_new = (
        "      SetAnimationState(AnimationState::kFallbackShown);\n"
        "      window_observation_.Reset();\n"
        "      // The fallback is fully opaque; remove the tint before revealing the new page.\n"
        "      if (darken_layer_) {\n"
        "        darken_layer_->SetOpacity(0.0f);\n"
        "        if (darken_layer_->parent()) {\n"
        "          darken_layer_->RemoveFromParent();\n"
        "        }\n"
        "        darken_layer_.reset();\n"
        "      }\n"
        "      // Drop the old page's surface now that it's completely covered.\n"
    )
    source = replace_once_or_done(source, fallback_complete_old, fallback_complete_new, "Remove Darken before revealing destination page")
    show_old = (
        "    if (blur_layer_) {\n"
        "      layer_tree->AddChild(blur_layer_);\n"
        "    }\n"
        "    if (fallback_color_layer_) {\n"
        "      layer_tree->AddChild(fallback_color_layer_);\n"
        "    }\n"
    )
    show_new = (
        "    if (blur_layer_) {\n"
        "      layer_tree->AddChild(blur_layer_);\n"
        "    }\n"
        "    if (darken_layer_) {\n"
        "      layer_tree->AddChild(darken_layer_);\n"
        "    }\n"
        "    if (fallback_color_layer_) {\n"
        "      layer_tree->AddChild(fallback_color_layer_);\n"
        "    }\n"
    )
    source = replace_once_or_done(source, show_old, show_new, "Attach Darken layer above outgoing surface")
    hide_old = (
        "  if (blur_layer_ && blur_layer_->parent()) {\n"
        "    blur_layer_->RemoveFromParent();\n"
        "  }\n"
        "  if (fallback_color_layer_ && fallback_color_layer_->parent()) {\n"
        "    fallback_color_layer_->RemoveFromParent();\n"
        "  }\n"
    )
    hide_new = (
        "  if (blur_layer_ && blur_layer_->parent()) {\n"
        "    blur_layer_->RemoveFromParent();\n"
        "  }\n"
        "  if (darken_layer_ && darken_layer_->parent()) {\n"
        "    darken_layer_->RemoveFromParent();\n"
        "  }\n"
        "  if (fallback_color_layer_ && fallback_color_layer_->parent()) {\n"
        "    fallback_color_layer_->RemoveFromParent();\n"
        "  }\n"
    )
    source = replace_once_or_done(source, hide_old, hide_new, "Remove Darken layer during teardown")
    reset_old = (
        "  blur_layer_.reset();\n"
        "  fallback_color_layer_.reset();\n"
    )
    reset_new = (
        "  blur_layer_.reset();\n"
        "  darken_layer_.reset();\n"
        "  fallback_color_layer_.reset();\n"
    )
    source = replace_once_or_done(source, reset_old, reset_new, "Release Darken layer during teardown")
    state_old = (
        "  initial_fallback_opacity_ =\n"
        "      fallback_color_layer_ ? fallback_color_layer_->opacity() : 0.0f;\n"
    )
    state_new = (
        state_old
        + "  initial_darken_opacity_ =\n"
        + "      darken_layer_ ? darken_layer_->opacity() : 0.0f;\n"
    )
    source = replace_once_or_done(source, state_old, state_new, "Capture Darken opacity between animation phases")
    required = (
        "blink::features::kForceWebContentsDarkMode",
        "SkColors::kBlack",
        "features::kAndroidNavigationAnimationDarken.Get()",
        "initial_darken_opacity_ *",
        "darken_layer_->RemoveFromParent();",
    )
    for snippet in required:
        if snippet not in source:
            raise RuntimeError(f"Native transition C++ validation failed: {snippet}")
    return source

def transform_transition_h(source: str) -> str:
    old = "  scoped_refptr<cc::slim::SurfaceLayer> blur_layer_;\n"
    new = old + "  scoped_refptr<cc::slim::SolidColorLayer> darken_layer_;\n"
    source = replace_once_or_done(source, old, new, "Declare Darken compositor layer")
    old_opacity = "  float initial_blur_opacity_ = 0.0f;\n"
    new_opacity = old_opacity + "  float initial_darken_opacity_ = 0.0f;\n"
    source = replace_once_or_done(source, old_opacity, new_opacity, "Declare Darken opacity state")
    return source


def transform_android_build_gn(source: str) -> str:
    for entry, label in (
        (BLUR_ICON_ENTRY, "blur icon resource"),
        (DARKEN_ICON_ENTRY, "darken icon resource"),
    ):
        if entry not in source:
            source = replace_once_or_done(
                source, BUILD_GN_ICON_ANCHOR, entry + BUILD_GN_ICON_ANCHOR,
                f"android/BUILD.gn {label}",
            )
        if source.count(entry) != 1:
            raise RuntimeError(f"android/BUILD.gn {label}: entry count mismatch")
    return source


def write_icon(path: Path, content: str, label: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise RuntimeError(f"{label}: existing resource differs; refusing overwrite")
        print(f"{label}=ALREADY_PRESENT")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if path.read_text(encoding="utf-8") != content:
        raise RuntimeError(f"{label}: post-write verification failed")
    print(f"{label}=CREATED")


def git_sha(path: Path) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()

def write_transform(path: Path, transform, label: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"{label}: missing file {path}")
    original = path.read_text(encoding="utf-8")
    updated = transform(original)
    if updated != original:
        path.write_text(updated, encoding="utf-8")
        if path.read_text(encoding="utf-8") != updated:
            raise RuntimeError(f"{label}: post-write verification failed")
        print(f"{label}=APPLIED")
    else:
        print(f"{label}=ALREADY_APPLIED")

def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {Path(sys.argv[0]).name} <chromium-src-root>")
    root = Path(sys.argv[1]).resolve()
    core = root / "brave"
    actual_chromium, actual_brave = git_sha(root), git_sha(core)
    if actual_chromium != CHROMIUM_SHA or actual_brave != BRAVE_SHA:
        raise RuntimeError(
            "pinned source mismatch; refusing transition Full Mode overlay: "
            f"chromium={actual_chromium} expected={CHROMIUM_SHA}; "
            f"brave={actual_brave} expected={BRAVE_SHA}"
        )

    # Reuse the proven Android preference/startup transform, then extend it.
    base_overlay = Path(__file__).with_name("apply-sandium-blur-transition.py")
    subprocess.run([sys.executable, str(base_overlay), str(root)], check=True)

    write_transform(root / STARTUP, transform_startup, "SANDIUM_TRANSITION_STARTUP")
    write_icon(core / BLUR_ICON_PATH, BLUR_ICON_SOURCE.read_text(encoding="utf-8"), "SANDIUM_BLUR_ICON")
    write_icon(core / DARKEN_ICON_PATH, DARKEN_ICON_SOURCE.read_text(encoding="utf-8"), "SANDIUM_DARKEN_ICON")
    write_transform(core / ANDROID_BUILD_GN, transform_android_build_gn, "SANDIUM_TRANSITION_ICON_RESOURCES")
    write_transform(core / APPEARANCE_XML, transform_appearance_xml, "SANDIUM_TRANSITION_DARKEN_XML")
    write_transform(core / APPEARANCE_JAVA, transform_appearance_java, "SANDIUM_TRANSITION_DARKEN_JAVA")
    write_transform(core / MAIN_PREFERENCES_JAVA, transform_main_preferences, "SANDIUM_APPEARANCE_ICON")
    write_transform(core / STRINGS_GRD, transform_grd, "SANDIUM_TRANSITION_DARKEN_STRINGS")
    write_transform(core / APPEARANCE_TEST, transform_appearance_test, "SANDIUM_TRANSITION_DARKEN_TEST")
    write_transform(root / FEATURES_CC, transform_features_cc, "SANDIUM_TRANSITION_FEATURE_PARAM_CC")
    write_transform(root / FEATURES_H, transform_features_h, "SANDIUM_TRANSITION_FEATURE_PARAM_H")
    write_transform(root / TRANSITION_CC, transform_transition_cc, "SANDIUM_TRANSITION_NATIVE_CC")
    write_transform(root / TRANSITION_H, transform_transition_h, "SANDIUM_TRANSITION_NATIVE_H")

    print("SANDIUM_TRANSITION_MEDIUM=hold:450ms,fade:225ms (+50%)")
    print("SANDIUM_TRANSITION_HIGH=hold:675ms,fade:300ms (+50%)")
    print("SANDIUM_TRANSITION_DARKEN=default:false; persisted; native compositor layer")
    print("SANDIUM_TRANSITION_NIGHT_MODE_FALLBACK=blink::features::kForceWebContentsDarkMode -> black")
    print("SANDIUM_TRANSITION_APPEARANCE_ICON=ic_appearance")
    print("SANDIUM_TRANSITION_ADBLOCK=UNTOUCHED")
    print("SANDIUM_TRANSITION_FULL_OVERLAY=PASS")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"SANDIUM_TRANSITION_FULL_OVERLAY=FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
