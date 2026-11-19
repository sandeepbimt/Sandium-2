#!/usr/bin/env python3
"""Sandium native Android baseline palette; does not alter websites or theme preference."""
import argparse
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ACCENT = '#198CFF'  # Sampled Oppo ON-track; shared baseline interactive color.
BACKGROUND = '#000000'
CARD = '#1A1A1A'
ON_ACCENT = '#080F18'
LIGHT_PRIMARY = '#365D86'  # Same blue family, readable on light surfaces.
COMMON = {
    # Chromium's default dark controls, primary text and filled buttons use tone80.
    'baseline_primary_80': ACCENT,
    'baseline_primary_20': ON_ACCENT,
    # Keep readable blue text/controls on light surfaces instead of pale-on-white.
    'baseline_primary_40': LIGHT_PRIMARY,
    'baseline_primary_90': '#D5E4F6',
    'baseline_primary_10': '#071C32',
    'gm3_baseline_surface_dark': BACKGROUND,
    'gm3_baseline_surface_container_low_dark': CARD,
    'gm3_baseline_surface_container_dark': CARD,
    'gm3_baseline_surface_container_high_dark': CARD,
    'gm3_baseline_surface_container_highest_dark': '#242424',
    'gm3_baseline_surface_tint_dark': ACCENT,
    'toolbar_background_primary_dark': BACKGROUND,
}
NIGHT = {
    'schemes_primary': ACCENT,
    'schemes_on_primary': ON_ACCENT,
    'schemes_surface_container_lowest': BACKGROUND,
    'schemes_surface_container': CARD,
    'schemes_surface_container_highest': '#242424',
    'schemes_on_surface': '#FAFAFA',
    'schemes_on_surface_variant': '#BDBDBD',
    'schemes_outline_variant': '#454545',
    'button_background': ACCENT,
    'button_background_10': '#19198CFF',
    'text_on_primary': ON_ACCENT,
    'text_interactive': ACCENT,
    'icon_interactive': ACCENT,
    'brave_link': ACCENT,
    'brave_text_button_color': ACCENT,
    'brave_button_pressed': '#8AA8CA',
    'container_background': BACKGROUND,
    'onboarding_bg_color': BACKGROUND,
    'onboarding_card_bg_color': CARD,
    'toolbar_background_color_for_ntp': BACKGROUND,
    'location_bar_background_color_for_ntp': CARD,
    'dialog_bg_color_dark_baseline': CARD,
    'divider_interactive': '#454545',
    'semantic_text_interactive': ACCENT,
    'semantic_divider_interactive': '#454545',
}
LIGHT = {
    'schemes_primary': LIGHT_PRIMARY,
    'schemes_on_primary': '#FFFFFF',
    'button_background': LIGHT_PRIMARY,
    'button_background_10': '#19365D86',
    'brave_text_button_color': LIGHT_PRIMARY,
    'brave_button_pressed': '#254563',
    'text_interactive': LIGHT_PRIMARY,
    'icon_interactive': LIGHT_PRIMARY,
    'brave_link': LIGHT_PRIMARY,
}
# Fill the baseline palette families used by Chromium Settings/preferences,
# dialogs and controls. Keep error/security/private-mode token families untouched.
# These are neutral tonal values, not a global replacement of every hex literal.
for tone, value in {
    0: '000000', 10: '1A1A1A', 20: '242424', 30: '474747', 40: '616161',
    50: '797979', 60: '919191', 70: 'ABABAB', 80: 'C6C6C6',
    90: 'E2E2E2', 95: 'F1F1F1', 99: 'FCFCFC',
}.items():
    COMMON[f'baseline_neutral_{tone}'] = '#' + value
for tone, value in {30: '474747', 50: '797979', 60: '919191', 80: 'C6C6C6', 90: 'E2E2E2'}.items():
    COMMON[f'baseline_neutral_variant_{tone}'] = '#' + value
for tone, value in {30: '254563', 50: '50759E', 60: '198CFF', 70: 'A2BCDC', 95: 'EBF3FF'}.items():
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
    'gm3_baseline_surface_tint_light': LIGHT_PRIMARY,
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
    'filter_title_color',
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
# Explicit Shields control token must not fall back to ordinary body text.
NIGHT['shield_toggle_button_tint'] = ACCENT
LIGHT['shield_toggle_button_tint'] = LIGHT_PRIMARY
NIGHT['bookmark_import_export_dialog_button_color'] = ACCENT
LIGHT['bookmark_import_export_dialog_button_color'] = LIGHT_PRIMARY
NIGHT['text_tertiary'] = '#A0A0A0'
LIGHT['text_tertiary'] = '#616161'

NIGHT.update({
    'card_background_solid': CARD,
    'toolbar_text_box_bg_color': CARD,
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

# Scoped tooltip palette: never recolor primitive_primary globally, which is
# shared with unrelated Brave surfaces. Keep the success shield semantic green.
NIGHT.update({
    'sandium_shields_tooltip_surface': BACKGROUND,
    'sandium_shields_tooltip_group': CARD,
    'sandium_shields_tooltip_text': '#FAFAFA',
    'sandium_shields_tooltip_secondary': '#BDBDBD',
})
LIGHT.update({
    'sandium_shields_tooltip_surface': '#FFFFFF',
    'sandium_shields_tooltip_group': '#F3F3F3',
    'sandium_shields_tooltip_text': '#202020',
    'sandium_shields_tooltip_secondary': '#616161',
})
TOOLTIP_BACKGROUND = 'android/java/brave-res/drawable/shields_tooltip_background.xml'
TOOLTIP_GROUP = 'android/java/brave-res/drawable/shields_tooltip_pill_bg.xml'
TOOLTIP_LAYOUT = 'android/java/brave-res/layout/brave_shields_tooltip_layout.xml'
TOOLTIP_TOOLBAR = 'android/java/org/chromium/chrome/browser/toolbar/top/BraveToolbarLayoutImpl.java'

def tooltip_replace(source, old, new, count=1):
    if source.count(new) == count and old not in source:
        return source
    if source.count(old) != count or new in source:
        raise ValueError('Pinned Shields tooltip style anchor changed: ' + old)
    return source.replace(old, new)

def tooltip_style(source, kind):
    if kind == TOOLTIP_BACKGROUND:
        source = tooltip_replace(source, '@color/primitive_primary_35', '@color/sandium_shields_tooltip_surface')
        source = tooltip_replace(source, 'android:radius="28dp"', 'android:radius="16dp"')
    elif kind == TOOLTIP_GROUP:
        source = tooltip_replace(source, '@color/primitive_primary_40', '@color/sandium_shields_tooltip_group')
        source = tooltip_replace(source, 'android:radius="20dp"', 'android:radius="12dp"')
    elif kind == TOOLTIP_LAYOUT:
        old = 'android:textColor="@color/onboarding_welcome_text_color"'
        primary = 'android:textColor="@color/sandium_shields_tooltip_text"'
        secondary = 'android:textColor="@color/sandium_shields_tooltip_secondary"'
        if source.count(old) == 2 and primary not in source and secondary not in source:
            source = source.replace(old, primary, 1).replace(old, secondary, 1)
        elif old in source or source.count(primary) != 1 or source.count(secondary) != 1:
            raise ValueError('Pinned Shields tooltip text anchors changed')
    elif kind == TOOLTIP_TOOLBAR:
        source = tooltip_replace(source,
            '.arrowColor(\n                                ContextCompat.getColor(getContext(), R.color.primitive_primary_35))',
            '.arrowColor(\n                                ContextCompat.getColor(getContext(), R.color.sandium_shields_tooltip_surface))')
    else:
        raise ValueError('Unknown tooltip input')
    if kind != TOOLTIP_TOOLBAR:
        ET.fromstring(source)
    return source

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

SETTINGS_GROUPS = """    // SANDIUM_OPPO_GROUPS: decoration only; native row binding, ripple, clicks,
    // summaries, switch geometry and accessibility remain owned by Preferences.
    private void sandiumStylePreferenceGroups(Fragment fragment, View fragmentView) {
        if (!(fragment instanceof androidx.preference.PreferenceFragmentCompat)
                || org.chromium.chrome.browser.theme.BraveDynamicColors.isDynamicColorsEnabled()) {
            return;
        }
        RecyclerView list = fragmentView.findViewById(R.id.recycler_view);
        if (list == null || !(list.getAdapter() instanceof androidx.preference.PreferenceGroupAdapter)) {
            return;
        }
        for (int i = 0; i < list.getItemDecorationCount(); i++) {
            if (list.getItemDecorationAt(i) instanceof SandiumPreferenceGroups) return;
        }
        list.addItemDecoration(new SandiumPreferenceGroups(
                getColor(R.color.card_background_solid), getResources().getDisplayMetrics().density));
    }

    private static final class SandiumPreferenceGroups extends RecyclerView.ItemDecoration {
        private final android.graphics.Paint mPaint =
                new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
        private final android.graphics.Path mPath = new android.graphics.Path();
        private final android.graphics.RectF mBounds = new android.graphics.RectF();
        private final float[] mRadii = new float[8];
        private final float mRadius;
        private final int mGutter;
        private final int mGap;

        SandiumPreferenceGroups(int color, float density) {
            mPaint.setColor(color);
            mRadius = 16 * density;
            mGutter = Math.round(12 * density);
            mGap = Math.round(6 * density);
        }

        private static androidx.preference.@Nullable Preference item(RecyclerView parent, int index) {
            if (!(parent.getAdapter() instanceof androidx.preference.PreferenceGroupAdapter adapter)
                    || index < 0 || index >= adapter.getItemCount()) return null;
            return adapter.getItem(index);
        }

        private static boolean ordinary(androidx.preference.@Nullable Preference item) {
            // Category headers retain their own native surfaces.
            return item != null && !(item instanceof androidx.preference.PreferenceCategory);
        }

        private static boolean sameGroup(androidx.preference.@Nullable Preference a,
                androidx.preference.@Nullable Preference b) {
            return a != null && b != null && ordinary(a) && ordinary(b)
                    && a.getParent() == b.getParent();
        }

        @Override
        public void getItemOffsets(android.graphics.Rect out, View view,
                RecyclerView parent, RecyclerView.State state) {
            int position = parent.getChildAdapterPosition(view);
            androidx.preference.Preference current = item(parent, position);
            if (!ordinary(current)) return;
            out.left = mGutter;
            out.right = mGutter;
            out.top = sameGroup(item(parent, position - 1), current) ? 0 : mGap;
            out.bottom = sameGroup(current, item(parent, position + 1)) ? 0 : mGap;
        }

        @Override
        public void onDraw(android.graphics.Canvas canvas, RecyclerView parent,
                RecyclerView.State state) {
            for (int i = 0; i < parent.getChildCount(); i++) {
                View row = parent.getChildAt(i);
                int position = parent.getChildAdapterPosition(row);
                androidx.preference.Preference current = item(parent, position);
                if (!ordinary(current)) continue;
                float top = sameGroup(item(parent, position - 1), current) ? 0 : mRadius;
                float bottom = sameGroup(current, item(parent, position + 1)) ? 0 : mRadius;
                mBounds.set(row.getLeft(), row.getTop() + row.getTranslationY(),
                        row.getRight(), row.getBottom() + row.getTranslationY());
                mPath.reset();
                for (int corner = 0; corner < 8; corner++) {
                    mRadii[corner] = corner < 4 ? top : bottom;
                }
                mPath.addRoundRect(mBounds, mRadii, android.graphics.Path.Direction.CW);
                canvas.drawPath(mPath, mPaint);
            }
        }
    }

"""


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

SETTINGS_PALETTE_STYLE = """    <!-- Settings only: Shapes, accents and baseline browser palette stay unchanged. -->
    <style name="SandiumSettingsSurfacePalette" parent="">
        <item name="android:colorBackground">?attr/colorSurfaceContainerLowest</item>
        <item name="android:windowBackground">?attr/colorSurfaceContainerLowest</item>
        <item name="colorSurface">?attr/colorSurfaceContainerLowest</item>
        <item name="colorSurfaceContainerLow">@color/card_background_solid</item>
        <item name="colorSurfaceContainer">@color/card_background_solid</item>
        <item name="colorSurfaceContainerHigh">@color/card_background_solid</item>
        <item name="colorSurfaceContainerHighest">@color/card_background_solid</item>
    </style>
"""

def settings_palette_resource(source):
    if SETTINGS_PALETTE_STYLE in source:
        return source
    if source.count('</resources>') != 1:
        raise ValueError('Settings palette resource anchor changed')
    return source.replace('</resources>', SETTINGS_PALETTE_STYLE + '</resources>')

def settings_palette_theme(source):
    marker = '// SANDIUM_SETTINGS_SCOPED_PALETTE'
    if marker in source:
        return source
    anchor = '    @Override\n    protected void onCreate(@Nullable Bundle savedInstanceState) {'
    hook = """    // SANDIUM_SETTINGS_SCOPED_PALETTE: applied after native containment/theme overlays,
    // before inflation. Applies to this Activity's preferences/dialog contexts only.
    @Override
    public void applyThemeOverlays() {
        super.applyThemeOverlays();
        boolean night = (getResources().getConfiguration().uiMode
                & android.content.res.Configuration.UI_MODE_NIGHT_MASK)
                == android.content.res.Configuration.UI_MODE_NIGHT_YES;
        if (night && !org.chromium.chrome.browser.theme.BraveDynamicColors.isDynamicColorsEnabled()) {
            getTheme().applyStyle(R.style.SandiumSettingsSurfacePalette, true);
        }
    }

"""
    if source.count(anchor) != 1:
        raise ValueError('Settings palette Activity anchor changed')
    return source.replace(anchor, hook + anchor)


def settings_surface(source):
    old = 'contentView.setBackgroundColor(SemanticColorUtils.getSettingsBackgroundColor(this));'
    new = 'contentView.setBackgroundColor(sandiumSettingsBackground());'
    helper = """    // SANDIUM_SETTINGS_SURFACE: preserve explicit dynamic-color opt-in and light theme.
    private int sandiumSettingsBackground() {
        boolean night = (getResources().getConfiguration().uiMode
                & android.content.res.Configuration.UI_MODE_NIGHT_MASK)
                == android.content.res.Configuration.UI_MODE_NIGHT_YES;
        if (night && !org.chromium.chrome.browser.theme.BraveDynamicColors.isDynamicColorsEnabled()) {
            try {
                return SemanticColorUtils.getColorSurfaceContainerLowest(this);
            } catch (IllegalArgumentException missingThemeAttribute) {
                return getColor(R.color.container_background);
            }
        }
        return SemanticColorUtils.getSettingsBackgroundColor(this);
    }

"""
    # Upgrade the exact previously emitted helper before checking fresh-source anchors.
    # Do not insert a second helper into a restored checkpoint's generated Java.
    previous_attr_body = '            android.util.TypedValue color = new android.util.TypedValue();\n            if (getTheme().resolveAttribute(\n                    com.google.android.material.R.attr.colorSurfaceContainerLowest, color, true)) {\n                return color.resourceId != 0 ? getColor(color.resourceId) : color.data;\n            }\n            return getColor(R.color.container_background);'
    for previous_body in (previous_attr_body, '            return getColor(R.color.container_background);'):
        previous_helper = helper.replace(
                '            try {\n                return SemanticColorUtils.getColorSurfaceContainerLowest(this);\n            } catch (IllegalArgumentException missingThemeAttribute) {\n                return getColor(R.color.container_background);\n            }', previous_body)
        if previous_helper in source:
            source = source.replace(previous_helper, helper, 1)
    anchor = '    private void onSettingsFragmentViewReady(Fragment fragment, View fragmentView) {'
    if helper not in source:
        if source.count(anchor) != 1 or source.count(old) != 1:
            raise ValueError('Pinned Settings surface anchors changed')
        source = source.replace(old, new, 1).replace(anchor, helper + anchor, 1)
    # The base activity paints the shared AppBarLayout with its separate elevated
    # surface. Match the preference root after super.onCreate() so main Settings,
    # its search header and every sub-setting use one backing colour. Do not
    # recolour the search field, cards, title, icons or mutate inset/scroll policy.
    header = """contentView.setBackgroundColor(sandiumSettingsBackground());
        // SANDIUM_SETTINGS_HEADER_SURFACE: shared by main and sub-settings.
        View sandiumSettingsHeader = findViewById(R.id.app_bar_layout);
        if (sandiumSettingsHeader != null) {
            sandiumSettingsHeader.setBackgroundColor(sandiumSettingsBackground());
        }"""
    if 'SANDIUM_SETTINGS_HEADER_SURFACE' not in source:
        if source.count(new) != 1:
            raise ValueError('Pinned Settings header anchor changed')
        source = source.replace(new, header, 1)
    old_fragment = '\n        View insetView = getInsetView(fragment, fragmentView);'
    new_fragment = """
        // Paint only the screen root, never preference cards, dialogs or web content.
        if (fragment.getParentFragment() == null) {
            fragmentView.setBackgroundColor(sandiumSettingsBackground());
            sandiumStylePreferenceGroups(fragment, fragmentView);
        }
        View insetView = getInsetView(fragment, fragmentView);"""
    if new_fragment not in source:
        if source.count(old_fragment) != 1:
            raise ValueError('Pinned Settings root anchor changed')
        source = source.replace(old_fragment, new_fragment, 1)
    if SETTINGS_GROUPS not in source:
        if source.count(anchor) != 1:
            raise ValueError('Pinned Settings group anchor changed')
        source = source.replace(anchor, SETTINGS_GROUPS + anchor, 1)
    # Native Settings keeps its inset/content geometry. Route the resolved header
    # colour through the existing system-bar owner, which paints the E2E backing
    # and selects icons; never set a second Window colour or enable web underlap.
    status_anchor = '        super.initializeSystemBarColors(edgeToEdgeSystemBarColorHelper);'
    status = status_anchor + "\n\n        // SANDIUM_SETTINGS_STATUS_SURFACE: same top RGB, no elevated grey strip.\n        edgeToEdgeSystemBarColorHelper.setStatusBarColor(sandiumSettingsBackground());"
    if 'SANDIUM_SETTINGS_STATUS_SURFACE' not in source:
        if source.count(status_anchor) != 1:
            raise ValueError('Pinned Settings status surface anchor changed')
        source = source.replace(status_anchor, status, 1)
    return source

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
    for relative in (TOOLTIP_BACKGROUND, TOOLTIP_GROUP, TOOLTIP_LAYOUT, TOOLTIP_TOOLBAR):
        target = root / relative
        result[target] = tooltip_style(target.read_text(), relative)
    settings = root / SETTINGS
    result[settings] = settings_palette_theme(settings_surface(settings_motion(settings.read_text())))
    palette = root / 'android/java/res/values/brave_colors.xml'
    result[palette] = settings_palette_resource(result[palette])
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
