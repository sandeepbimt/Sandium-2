#!/usr/bin/env python3
"""Sandium native Android baseline palette; does not alter websites or theme preference."""
import argparse
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ACCENT = '#E6F4E8'
BACKGROUND = '#1B1F21'
CARD = '#292E31'
ON_ACCENT = '#18231B'
LIGHT_GREEN = '#365B40'
COMMON = {
    # Chromium's default dark controls, primary text and filled buttons use tone80.
    'baseline_primary_80': ACCENT,
    'baseline_primary_20': ON_ACCENT,
    # Keep readable green text/controls on light surfaces instead of pale-on-white.
    'baseline_primary_40': LIGHT_GREEN,
    'baseline_primary_90': '#D2E9D7',
    'baseline_primary_10': '#102518',
    'gm3_baseline_surface_dark': BACKGROUND,
    'gm3_baseline_surface_container_lowest_dark': '#15191B',
    'gm3_baseline_surface_container_low_dark': '#22272A',
    'gm3_baseline_surface_container_dark': CARD,
    'gm3_baseline_surface_container_high_dark': '#303639',
    'gm3_baseline_surface_container_highest_dark': '#383F42',
    'gm3_baseline_surface_tint_dark': ACCENT,
    'toolbar_background_primary_dark': BACKGROUND,
}
NIGHT = {
    'schemes_primary': ACCENT,
    'schemes_on_primary': ON_ACCENT,
    'schemes_surface_container_lowest': BACKGROUND,
    'schemes_surface_container': CARD,
    'schemes_surface_container_highest': '#383F42',
    'schemes_on_surface': '#EFF2EF',
    'schemes_on_surface_variant': '#C4CCC7',
    'schemes_outline_variant': '#59635E',
    'button_background': ACCENT,
    'button_background_10': '#19E6F4E8',
    'text_on_primary': ON_ACCENT,
    'text_interactive': ACCENT,
    'icon_interactive': ACCENT,
    'brave_link': ACCENT,
    'brave_text_button_color': ACCENT,
    'brave_button_pressed': '#CADBCE',
    'container_background': BACKGROUND,
    'onboarding_bg_color': BACKGROUND,
    'onboarding_card_bg_color': CARD,
    'toolbar_background_color_for_ntp': BACKGROUND,
    'location_bar_background_color_for_ntp': CARD,
    'dialog_bg_color_dark_baseline': BACKGROUND,
    'divider_interactive': '#A8C4AD',
    'semantic_text_interactive': ACCENT,
    'semantic_divider_interactive': '#A8C4AD',
}
LIGHT = {
    'schemes_primary': LIGHT_GREEN,
    'schemes_on_primary': '#FFFFFF',
    'button_background': LIGHT_GREEN,
    'button_background_10': '#19365B40',
    'brave_text_button_color': LIGHT_GREEN,
    'brave_button_pressed': '#284931',
    'text_interactive': LIGHT_GREEN,
    'icon_interactive': LIGHT_GREEN,
    'brave_link': LIGHT_GREEN,
}
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
    print(f'SANDIUM_NATIVE_THEME=PASS files={count} default=charcoal-pale-green explicit_theme_choices=preserved')
