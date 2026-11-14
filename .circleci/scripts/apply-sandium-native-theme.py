#!/usr/bin/env python3
"""Sandium native Android baseline palette; does not alter websites or theme preference."""
import argparse
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ACCENT = '#F5F5F5'
BACKGROUND = '#000000'
CARD = '#212121'
ON_ACCENT = '#171717'
LIGHT_PRIMARY = '#333333'
COMMON = {
    # Chromium's default dark controls, primary text and filled buttons use tone80.
    'baseline_primary_80': ACCENT,
    'baseline_primary_20': ON_ACCENT,
    # Keep readable neutral text/controls on light surfaces instead of pale-on-white.
    'baseline_primary_40': LIGHT_PRIMARY,
    'baseline_primary_90': '#E5E5E5',
    'baseline_primary_10': '#171717',
    'gm3_baseline_surface_dark': BACKGROUND,
    'gm3_baseline_surface_container_lowest_dark': '#000000',
    'gm3_baseline_surface_container_low_dark': '#171717',
    'gm3_baseline_surface_container_dark': CARD,
    'gm3_baseline_surface_container_high_dark': '#303030',
    'gm3_baseline_surface_container_highest_dark': '#383838',
    'gm3_baseline_surface_tint_dark': ACCENT,
    'toolbar_background_primary_dark': BACKGROUND,
}
NIGHT = {
    'schemes_primary': ACCENT,
    'schemes_on_primary': ON_ACCENT,
    'schemes_surface_container_lowest': BACKGROUND,
    'schemes_surface_container': CARD,
    'schemes_surface_container_highest': '#383838',
    'schemes_on_surface': '#FAFAFA',
    'schemes_on_surface_variant': '#BDBDBD',
    'schemes_outline_variant': '#454545',
    'button_background': ACCENT,
    'button_background_10': '#19F5F5F5',
    'text_on_primary': ON_ACCENT,
    'text_interactive': ACCENT,
    'icon_interactive': ACCENT,
    'brave_link': ACCENT,
    'brave_text_button_color': ACCENT,
    'brave_button_pressed': '#D6D6D6',
    'container_background': BACKGROUND,
    'onboarding_bg_color': BACKGROUND,
    'onboarding_card_bg_color': CARD,
    'toolbar_background_color_for_ntp': BACKGROUND,
    'location_bar_background_color_for_ntp': CARD,
    'dialog_bg_color_dark_baseline': BACKGROUND,
    'divider_interactive': '#454545',
    'semantic_text_interactive': ACCENT,
    'semantic_divider_interactive': '#454545',
}
LIGHT = {
    'schemes_primary': LIGHT_PRIMARY,
    'schemes_on_primary': '#FFFFFF',
    'button_background': LIGHT_PRIMARY,
    'button_background_10': '#19333333',
    'brave_text_button_color': LIGHT_PRIMARY,
    'brave_button_pressed': '#1F1F1F',
    'text_interactive': LIGHT_PRIMARY,
    'icon_interactive': LIGHT_PRIMARY,
    'brave_link': LIGHT_PRIMARY,
}
# Fill the baseline palette families used by Chromium Settings/preferences,
# dialogs and controls. Keep error/security/private-mode token families untouched.
# These are neutral tonal values, not a global replacement of every hex literal.
for tone, value in {
    0: '000000', 10: '171717', 20: '303030', 30: '474747', 40: '616161',
    50: '797979', 60: '919191', 70: 'ABABAB', 80: 'C6C6C6',
    90: 'E2E2E2', 95: 'F1F1F1', 99: 'FCFCFC',
}.items():
    COMMON[f'baseline_neutral_{tone}'] = '#' + value
for tone, value in {30: '474747', 50: '797979', 60: '919191', 80: 'C6C6C6', 90: 'E2E2E2'}.items():
    COMMON[f'baseline_neutral_variant_{tone}'] = '#' + value
for tone, value in {30: '474747', 50: '797979', 60: '919191', 70: 'ABABAB', 95: 'F1F1F1'}.items():
    COMMON[f'baseline_primary_{tone}'] = '#' + value
for family, tones in {
    'secondary': {10: '171717', 25: '3B3B3B', 30: '474747', 35: '545454',
                  40: '616161', 50: '797979', 60: '919191', 70: 'ABABAB',
                  80: 'C6C6C6', 90: 'E2E2E2', 95: 'F1F1F1'},
    'tertiary': {10: '171717', 30: '474747', 40: '616161', 80: 'C6C6C6', 90: 'E2E2E2'},
}.items():
    for tone, value in tones.items():
        COMMON[f'baseline_{family}_{tone}'] = '#' + value
COMMON.update({
    'gm3_baseline_surface_tint_light': '#333333',
    'gm3_baseline_surface_container_low_light': '#F7F7F7',
    'gm3_baseline_surface_container_light': '#F3F3F3',
    'gm3_baseline_surface_container_high_light': '#EEEEEE',
    'gm3_baseline_surface_container_highest_light': '#E8E8E8',
})
# Explicit Brave settings/subpage colors otherwise bypass Chromium theme attrs.
# Status colors (warnings, errors, stats categories, Shields counters) stay semantic.
for name in (
    'menu_icon_color', 'url_text_primary', 'text_primary', 'onboarding_text_color',
    'scan_qr_code_text_color', 'set_default_text_color', 'shield_text_color',
    'shield_toggle_button_tint', 'filter_title_color',
    'add_custom_filter_text_input_hint_color', 'bookmark_import_export_dialog_title_color',
):
    NIGHT[name] = '#FAFAFA'
    LIGHT[name] = '#202020'
for name in (
    'text_secondary', 'brave_theme_subtitle_text', 'brave_theme_hint_text',
    'filter_summary_color', 'add_custom_filter_edit_text_hint_color',
    'add_custom_filter_summary_color', 'add_custom_filter_tint_color',
    'bookmark_menu_text_color', 'bookmark_import_export_dialog_secondary_color',
):
    NIGHT[name] = '#BDBDBD'
    LIGHT[name] = '#616161'
for name in (
    'scan_qr_code_bg_color', 'set_default_bottom_sheet_bg_color',
    'bookmark_import_export_toast_bg_color',
):
    NIGHT[name] = BACKGROUND
    LIGHT[name] = '#FFFFFF'
for name in ('brave_sync_bg_secondary_color', 'bookmark_menu_bg_color',
             'notification_rationale_dialog_card_bg_color'):
    NIGHT[name] = CARD
    LIGHT[name] = '#F3F3F3'
NIGHT['bookmark_import_export_dialog_button_color'] = ACCENT
LIGHT['bookmark_import_export_dialog_button_color'] = LIGHT_PRIMARY
NIGHT['text_tertiary'] = '#A0A0A0'
LIGHT['text_tertiary'] = '#616161'

NIGHT.update({
    'card_background_solid': CARD,
    'toolbar_text_box_bg_color': '#303030',
})
LIGHT.update({
    'schemes_on_surface': '#202020',
    'schemes_on_surface_variant': '#616161',
    'schemes_outline_variant': '#BDBDBD',
    'schemes_surface_container': '#F3F3F3',
    'schemes_surface_container_lowest': '#FFFFFF',
    'schemes_surface_container_highest': '#E8E8E8',
    'card_background_solid': '#F3F3F3',
    'toolbar_text_box_bg_color': '#F3F3F3',
})

DYNAMIC = 'browser/ui/android/theme/java/src/org/chromium/chrome/browser/theme/BraveDynamicColors.java'
OLD_DEFAULT = 'BravePreferenceKeys.BRAVE_ANDROID_DYNAMIC_COLORS_ENABLED,\n                        getCachedDefaultFlag().isEnabled());'
NEW_DEFAULT = 'BravePreferenceKeys.BRAVE_ANDROID_DYNAMIC_COLORS_ENABLED,\n                        false); // Sandium baseline; explicit user choice still wins.'

def recolor(text, mapping):
    ET.fromstring(text)
    for name, value in mapping.items():
        pattern = r'(<color\s+name="' + re.escape(name) + r'"[^>]*>)[^<]*(</color>)'
        matches = list(re.finditer(pattern, text))
        if len(matches) > 1:
            raise ValueError('duplicate color: ' + name)
        if matches:
            text = re.sub(pattern, lambda m: m[1] + value + m[2], text)
        else:
            # Existing Brave color overlay has precedence over Chromium resources.
            text = text.replace('</resources>', f'    <color name="{name}">{value}</color>\n</resources>')
    ET.fromstring(text)
    return text

SETTINGS = 'android/java/org/chromium/chrome/browser/settings/BraveSettingsActivity.java'

def settings_motion(source):
    """Fade newly created app-owned settings content, never scroll/model updates."""
    old = '                    view.post(() -> onSettingsFragmentViewReady(fragment, view));'
    new = """                    // SANDIUM_SETTINGS_MOTION: platform Animator honors duration scale.
                    // Nested fragments belong to their parent transition, not a second fade.
                    if (fragment.getParentFragment() == null
                            && android.animation.ValueAnimator.areAnimatorsEnabled()) {
                        view.setAlpha(0f);
                        view.post(() -> {
                            if (fragment.getView() == view && view.isAttachedToWindow()
                                    && !isFinishing() && !isDestroyed()
                                    && android.animation.ValueAnimator.areAnimatorsEnabled()) {
                                view.animate().alpha(1f).setDuration(120).setStartDelay(0)
                                        .setInterpolator(new android.view.animation.LinearInterpolator())
                                        .start();
                            } else {
                                view.setAlpha(1f);
                            }
                        });
                    }
                    view.post(() -> onSettingsFragmentViewReady(fragment, view));"""
    if new in source:
        return source
    if source.count(old) != 1:
        raise ValueError('Pinned Settings motion callback mismatch')
    return source.replace(old, new, 1)

def apply(root):
    paths = {
        root / 'android/java/res/values/brave_colors.xml': {**COMMON, **LIGHT},
        root / 'android/java/res/values-night/brave_colors.xml': NIGHT,
    }
    result = {p: recolor(p.read_text(), colors) for p, colors in paths.items()}
    java = root / DYNAMIC
    source = java.read_text()
    if OLD_DEFAULT in source:
        source = source.replace(OLD_DEFAULT, NEW_DEFAULT)
    elif NEW_DEFAULT not in source:
        raise ValueError('unexpected dynamic-color default implementation')
    # Avoid misleading upstream comments after the intentional default change.
    source = source.replace('An\n     * unset preference uses the cached remotely controlled default.',
                            'An\n     * unset preference uses the Sandium baseline palette.')
    source = source.replace('Returns the persisted user preference or the cached default when it is unset.',
                            'Returns the persisted user preference, or the Sandium baseline when unset.')
    result[java] = source
    settings = root / SETTINGS
    result[settings] = settings_motion(settings.read_text())
    test = root / 'browser/ui/android/theme/junit/src/org/chromium/chrome/browser/theme/BraveDynamicColorsTest.java'
    test_source = test.read_text()
    old = """public void testIsDynamicColorsEnabled_defaultEnabled_userPreferenceUnset_returnsTrue() {
        assertTrue(BraveDynamicColors.isDynamicColorsEnabled());
    }"""
    new = """public void testIsDynamicColorsEnabled_sandiumDefault_userPreferenceUnset_returnsFalse() {
        assertFalse(BraveDynamicColors.isDynamicColorsEnabled());
    }"""
    if old in test_source:
        test_source = test_source.replace(old, new)
    elif new not in test_source:
        raise ValueError('unexpected default-palette test implementation')
    result[test] = test_source
    # Validate every file before writing any of them.
    for p, content in result.items():
        p.write_text(content)
    return len(result)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('brave_root', type=Path)
    args = parser.parse_args()
    count = apply(args.brave_root)
    print(f'SANDIUM_NATIVE_THEME=PASS files={count} default=neutral-charcoal explicit_theme_choices=preserved')
