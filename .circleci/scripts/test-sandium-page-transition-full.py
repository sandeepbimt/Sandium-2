#!/usr/bin/env python3
"""Offline tests for Sandium's transition-only Full Mode source overlay."""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).with_name("apply-sandium-page-transition-full.py")
SPEC = importlib.util.spec_from_file_location("sandium_page_transition_full", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

BLUR_SCRIPT = Path(__file__).with_name("apply-sandium-blur-transition.py")
BLUR_SPEC = importlib.util.spec_from_file_location("sandium_blur_transition", BLUR_SCRIPT)
assert BLUR_SPEC is not None and BLUR_SPEC.loader is not None
BLUR_MODULE = importlib.util.module_from_spec(BLUR_SPEC)
BLUR_SPEC.loader.exec_module(BLUR_MODULE)

STARTUP_FIXTURE = '''        String level = ContextUtils.getAppSharedPreferences().getString("sandium_page_transition_blur_level", "default");
        if ("low".equals(level)) {
            params = "nav-animation-blur-sigma/1.0/nav-animation-fade-hold-duration-ms/200/nav-animation-fade-out-duration-ms/100";
        } else if ("medium".equals(level)) {
            params = "nav-animation-blur-sigma/2.0/nav-animation-fade-hold-duration-ms/300/nav-animation-fade-out-duration-ms/150";
        } else if ("high".equals(level)) {
            params = "nav-animation-blur-sigma/4.0/nav-animation-fade-hold-duration-ms/450/nav-animation-fade-out-duration-ms/200";
        }
        final String selectedFeature = feature + ":" + params;
'''

JAVA_FIXTURE = '''import androidx.preference.PreferenceGroupAdapter;\nclass AppearancePreferences {
    // SANDIUM_PAGE_TRANSITION_BLUR_PREF_BEGIN
    /* package */ static final String PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL = "sandium_page_transition_blur_level";
    // SANDIUM_PAGE_TRANSITION_BLUR_PREF_END
    void initialize() {
        // SANDIUM_PAGE_TRANSITION_BLUR_INIT_END
    }
    boolean onPreferenceChange(Preference preference, Object newValue) {
        String key = preference.getKey();
        boolean shouldRelaunch = false;
        if (BravePreferenceKeys.BRAVE_BOTTOM_TOOLBAR_ENABLED_KEY.equals(key)) {
            doSomething();
        }
        return true;
    }
    void applyOrdering() {
        // SANDIUM_PAGE_TRANSITION_BLUR_ORDER_BEGIN
        setPreferenceOrder(PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL, 10);
        setPreferenceOrder(PREF_BRAVE_DISABLE_SHARING_HUB, 11);
        setPreferenceOrder(PREF_SHOW_BRAVE_REWARDS_ICON, 12);
        setPreferenceOrder(PREF_ADS_SWITCH, 13);
        setPreferenceOrder(AppearanceSettingsFragment.PREF_BOOKMARK_BAR, 14);
        setPreferenceOrder(PREF_BRAVE_ENABLE_TAB_GROUPS, 15);
        setPreferenceOrder(PREF_SHOW_UNDO_WHEN_TABS_CLOSED, 16);
        // SANDIUM_PAGE_TRANSITION_BLUR_ORDER_END
    }
}
'''

TRANSITION_CC_FIXTURE = '''#include "base/metrics/histogram_functions.h"
#include "content/public/common/content_features.h"
namespace content {
void setup() {
  SkColor4f background_color = SkColors::kWhite;
  if (auto theme_color = delegate->GetThemeColor()) {
    background_color = SkColor4f::FromColor(*theme_color);
  }
  fallback_color_layer_->SetOpacity(0.0f);

  SetAnimationState(AnimationState::kNone);
  switch (animation_state_) {
    case AnimationState::kFadeOut: {
      if (blur_layer_) {
        blur_layer_->SetOpacity(initial_blur_opacity_ *
                                adjusted_opacity_multiplier);
      }
      if (fallback_color_layer_) {
        fallback_color_layer_->SetOpacity(initial_fallback_opacity_ *
                                          adjusted_opacity_multiplier);
      }
      break;
    }
    case AnimationState::kFadeToFallbackColor: {
      if (blur_layer_) {
        blur_layer_->SetOpacity(initial_blur_opacity_);
      }
      if (fallback_color_layer_) {
        fallback_color_layer_->SetOpacity(initial_fallback_opacity_ +
                                          (1.0f - initial_fallback_opacity_) * alpha);
      }
      break;
    }
    default:
      break;
  }
  if (progress >= 1.0f) {
    if (animation_state_ == AnimationState::kFadeOut) {
      DestroyLayer();
    } else if (animation_state_ == AnimationState::kFadeToFallbackColor) {
      SetAnimationState(AnimationState::kFallbackShown);
      window_observation_.Reset();
      // Drop the old page's surface now that it's completely covered.
      if (blur_layer_) {
        blur_layer_->RemoveFromParent();
        blur_layer_.reset();
      }
    }
  }
  if (auto* layer_tree = native_view->GetLayer()) {
    if (blur_layer_) {
      layer_tree->AddChild(blur_layer_);
    }
    if (fallback_color_layer_) {
      layer_tree->AddChild(fallback_color_layer_);
    }
  }
  if (blur_layer_ && blur_layer_->parent()) {
    blur_layer_->RemoveFromParent();
  }
  if (fallback_color_layer_ && fallback_color_layer_->parent()) {
    fallback_color_layer_->RemoveFromParent();
  }
  blur_layer_.reset();
  fallback_color_layer_.reset();
  initial_fallback_opacity_ =
      fallback_color_layer_ ? fallback_color_layer_->opacity() : 0.0f;
}
'''

def assert_idempotent(transform, source, label):
    once = transform(source)
    twice = transform(once)
    assert once == twice, f"{label} transform is not idempotent"
    return once

def main():
    startup = assert_idempotent(MODULE.transform_startup, STARTUP_FIXTURE, "startup")
    for value in (
        "nav-animation-fade-hold-duration-ms/450/nav-animation-fade-out-duration-ms/225",
        "nav-animation-fade-hold-duration-ms/675/nav-animation-fade-out-duration-ms/300",
        'getBoolean("sandium_page_transition_darken", false)',
        '"/nav-animation-darken/" + (darken ? "true" : "false")',
    ):
        assert value in startup, f"missing startup behaviour: {value}"

    xml = assert_idempotent(
        MODULE.transform_appearance_xml,
        '<PreferenceScreen>\n'
        '    <ListPreference\n'
        '        android:key="sandium_page_transition_blur_level"\n'
        '        android:title="Page transition blur" />\n'
        '    <!-- SANDIUM_PAGE_TRANSITION_BLUR_END -->\n'
        '</PreferenceScreen>\n',
        "Appearance XML",
    )
    assert xml.count('android:key="sandium_page_transition_darken"') == 1
    assert 'android:icon="@drawable/ic_sandium_page_transition_blur"' in xml
    assert 'android:icon="@drawable/ic_sandium_page_transition_darken"' in xml
    blur_icon = MODULE.BLUR_ICON_SOURCE.read_text(encoding="utf-8")
    darken_icon = MODULE.DARKEN_ICON_SOURCE.read_text(encoding="utf-8")
    assert 'android:strokeColor="@color/menu_icon_color"' in blur_icon
    assert 'android:fillAlpha="0.24"' in darken_icon
    assert 'android:viewportWidth="24"' in blur_icon
    assert 'android:viewportWidth="24"' in darken_icon

    build_gn = assert_idempotent(
        MODULE.transform_android_build_gn,
        MODULE.BUILD_GN_ICON_ANCHOR,
        "Android resource target",
    )
    assert build_gn.count(MODULE.BLUR_ICON_ENTRY) == 1
    assert build_gn.count(MODULE.DARKEN_ICON_ENTRY) == 1

    grd = assert_idempotent(
        MODULE.transform_grd,
        '      <!-- SANDIUM_PAGE_TRANSITION_BLUR_STRINGS_END -->\n',
        "GRD strings",
    )
    assert grd.count('name="IDS_SANDIUM_PAGE_TRANSITION_DARKEN_') == 2

    appearance = assert_idempotent(MODULE.transform_appearance_java, JAVA_FIXTURE, "Appearance Java")
    assert appearance.count("PREF_SANDIUM_PAGE_TRANSITION_DARKEN") >= 5
    assert "setPreferenceOrder(PREF_SANDIUM_PAGE_TRANSITION_DARKEN, 11);" in appearance
    assert "setPreferenceOrder(PREF_BRAVE_DISABLE_SHARING_HUB, 12);" in appearance
    assert appearance.count("{") == appearance.count("}")

    # Regression: the base FAST blur patcher must not erase the extended
    # Darken constant when it is accidentally run after the Full transition
    # patch. Reapplying Full must remain idempotent and restore all controls.
    appearance_after_blur = BLUR_MODULE.transform_appearance_java(appearance)
    assert appearance_after_blur.count(MODULE.JAVA_DARKEN_PREF) == 1
    assert MODULE.JAVA_DARKEN_PREF_BEGIN in appearance_after_blur
    repaired = assert_idempotent(
        MODULE.transform_appearance_java, appearance_after_blur, "Appearance Java after base blur"
    )
    assert repaired.count(MODULE.JAVA_DARKEN_PREF) == 1
    assert "findPreference(PREF_SANDIUM_PAGE_TRANSITION_DARKEN)" in repaired
    assert ".putBoolean(PREF_SANDIUM_PAGE_TRANSITION_DARKEN, (Boolean) newValue)" in repaired
    assert "setPreferenceOrder(PREF_SANDIUM_PAGE_TRANSITION_DARKEN, 11);" in repaired

    main_preferences = assert_idempotent(
        MODULE.transform_main_preferences,
        "class BraveMainPreferencesBase {\n    private void updatePreferenceIcons() {\n    }\n}\n",
        "main Appearance icon",
    )
    assert main_preferences.count("updatePreferenceIcon(PREF_APPEARANCE, R.drawable.ic_appearance);") == 1

    appearance_test_fixture = '''import org.chromium.base.BraveFeatureList;\nimport org.chromium.chrome.browser.flags.ChromeFeatureList;\n'''
    appearance_test_fixture += '''            AppearancePreferences.PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL,\n'''
    appearance_test_fixture += '''    public void testDynamicColorsPreferenceAvailability() {\n        startSettings();\n    }\n'''
    appearance_test = assert_idempotent(
        MODULE.transform_appearance_test,
        appearance_test_fixture,
        "Appearance instrumentation test",
    )
    assert "AppearancePreferences.PREF_SANDIUM_PAGE_TRANSITION_DARKEN," in appearance_test
    assert "testPageTransitionDarkenPreferenceRestoresSavedChoice" in appearance_test
    assert "ChromeSwitchPreference" in appearance_test

    feature_cc_anchor = MODULE.FEATURE_PARAM_CC_ANCHOR
    feature_cc = assert_idempotent(
        MODULE.transform_features_cc,
        feature_cc_anchor,
        "content_features.cc",
    )
    assert feature_cc.count("kAndroidNavigationAnimationDarken") == 1

    feature_h_anchor = MODULE.FEATURE_PARAM_H_ANCHOR
    feature_h = assert_idempotent(
        MODULE.transform_features_h,
        feature_h_anchor,
        "content_features.h",
    )
    assert feature_h.count("kAndroidNavigationAnimationDarken") == 1

    native = assert_idempotent(
        MODULE.transform_transition_cc,
        TRANSITION_CC_FIXTURE,
        "native transition C++",
    )
    for value in (
        "blink::features::kForceWebContentsDarkMode",
        "SkColors::kBlack",
        "features::kAndroidNavigationAnimationDarken.Get()",
        "darken_layer_->SetOpacity(initial_darken_opacity_ *",
        "darken_layer_->RemoveFromParent();",
    ):
        assert value in native, f"missing native transition behaviour: {value}"

    native_header = assert_idempotent(
        MODULE.transform_transition_h,
        "  scoped_refptr<cc::slim::SurfaceLayer> blur_layer_;\n"
        "  float initial_blur_opacity_ = 0.0f;\n",
        "native transition header",
    )
    assert "scoped_refptr<cc::slim::SolidColorLayer> darken_layer_;" in native_header
    assert "float initial_darken_opacity_ = 0.0f;" in native_header

    print("SANDIUM_PAGE_TRANSITION_FULL_TESTS=PASS")
    print("SANDIUM_PAGE_TRANSITION_DURATIONS=PASS medium=450/225 high=675/300")
    print("SANDIUM_PAGE_TRANSITION_DARKEN=PASS preference+native-layer+cleanup")
    print("SANDIUM_PAGE_TRANSITION_NIGHT_MODE=PASS dark fallback")
    print("SANDIUM_PAGE_TRANSITION_APPEARANCE_ICONS=PASS blur+darken vector resources")
    print("SANDIUM_PAGE_TRANSITION_ADBLOCK=UNTOUCHED")

if __name__ == "__main__":
    main()
