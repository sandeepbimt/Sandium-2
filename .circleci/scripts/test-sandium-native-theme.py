#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
spec = importlib.util.spec_from_file_location('theme', Path(__file__).with_name('apply-sandium-native-theme.py'))
theme = importlib.util.module_from_spec(spec)
spec.loader.exec_module(theme)

def contrast(a,b):
    def luminance(c):
        v=[int(c[i:i+2],16)/255 for i in (1,3,5)]
        v=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in v]
        return sum(x*w for x,w in zip(v,(.2126,.7152,.0722)))
    a,b=sorted((luminance(a),luminance(b)))
    return (b+.05)/(a+.05)

class ThemeTests(unittest.TestCase):
    def test_recolor_idempotent_preserves_other_colors(self):
        source='<resources><color name="error">#FF0000</color><color name="schemes_primary">#123456</color></resources>'
        new=theme.recolor(source,theme.NIGHT)
        self.assertEqual(new,theme.recolor(new,theme.NIGHT))
        self.assertIn('<color name="error">#FF0000</color>',new)
        self.assertNotIn('#123456',new)
        ET.fromstring(new)
    def test_duplicate_fails(self):
        with self.assertRaises(ValueError):
            theme.recolor('<resources><color name="x">#000000</color><color name="x">#111111</color></resources>',{'x':'#222222'})
    def test_text_contrast(self):
        for fg,bg in [(theme.ACCENT,theme.BACKGROUND),(theme.ON_ACCENT,theme.ACCENT),(theme.LIGHT_PRIMARY,'#FFFFFF'),(theme.NIGHT['schemes_on_surface'],theme.CARD),(theme.NIGHT['schemes_on_surface_variant'],theme.CARD)]:
            self.assertGreaterEqual(contrast(fg,bg),4.5,(fg,bg))
    def test_neutral_surfaces(self):
        for color in [theme.BACKGROUND, theme.CARD,
                      theme.NIGHT['schemes_on_surface_variant']]:
            self.assertEqual(color[1:3], color[3:5])
            self.assertEqual(color[3:5], color[5:7])
    def test_welcome_checked_switch_contrast(self):
        self.assertGreaterEqual(contrast('#FFFFFF', '#198CFF'), 3)
        source = (Path(__file__).resolve().parents[2] / 'android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java').read_text()
        self.assertIn('private static final int SUCCESS = Color.rgb(230, 244, 232)', source)
        self.assertIn('Color.rgb(25, 140, 255)', source)
    def test_settings_subpage_tokens_have_readable_day_and_night_pairs(self):
        for name in ['filter_title_color', 'filter_summary_color',
                     'bookmark_menu_text_color', 'brave_theme_hint_text',
                     'bookmark_import_export_dialog_button_color', 'url_text_primary', 'text_tertiary']:
            self.assertGreaterEqual(contrast(theme.NIGHT[name], theme.CARD), 4.5, name)
            self.assertGreaterEqual(contrast(theme.LIGHT[name], '#E8E8E8'), 4.5, name)
        self.assertEqual(theme.NIGHT['bookmark_menu_bg_color'], theme.CARD)
        self.assertEqual(theme.COMMON['baseline_neutral_0'], '#000000')
    def test_reference_blue_active_controls(self):
        self.assertEqual(theme.ACCENT, '#198CFF')
        self.assertEqual(theme.NIGHT['shield_toggle_button_tint'], theme.ACCENT)
        self.assertEqual(theme.LIGHT['shield_toggle_button_tint'], theme.LIGHT_PRIMARY)
        for surface in ['#000000', '#1A1A1A', '#242424']:
            self.assertGreaterEqual(contrast(theme.ACCENT, surface), 4.5)
        for surface in ['#FFFFFF', '#F3F3F3', '#E8E8E8']:
            self.assertGreaterEqual(contrast(theme.LIGHT_PRIMARY, surface), 4.5)
        self.assertGreaterEqual(contrast('#BDBDBD', '#505050'), 3)  # OFF thumb/track
    def test_menu_action_resource_closure(self):
        root = Path(__file__).resolve().parents[2]
        for folder, expected in [('values', theme.LIGHT_PRIMARY), ('values-night', theme.ACCENT)]:
            colors = {e.get('name'): e.text for e in ET.parse(root / f'android/java/res/{folder}/sandium_menu_colors.xml').getroot()}
            self.assertEqual(colors['sandium_menu_accent'], expected)
            self.assertGreaterEqual(contrast(expected, colors['sandium_menu_surface_container']), 4.5)
        source = (root / 'android/java/org/chromium/chrome/browser/ui/appmenu/SandiumPagedMenu.java').read_text()
        self.assertIn('R.color.sandium_menu_accent', source)
        self.assertIn('text(label, 16, mAccentColor)', source)
    def test_settings_surface_migration(self):
        source = ('contentView.setBackgroundColor(SemanticColorUtils.getSettingsBackgroundColor(this));\n'
            '    private void onSettingsFragmentViewReady(Fragment fragment, View fragmentView) {\n'
            '        View insetView = getInsetView(fragment, fragmentView);\n}')
        result = theme.settings_surface(source)
        self.assertEqual(result, theme.settings_surface(result))
        self.assertIn('BraveDynamicColors.isDynamicColorsEnabled()', result)
        self.assertIn('fragment.getParentFragment() == null', result)
        self.assertIn('fragmentView.setBackgroundColor(sandiumSettingsBackground())', result)
        self.assertIn('UI_MODE_NIGHT_YES', result)
        with self.assertRaises(ValueError): theme.settings_surface('unexpected')
    def test_settings_surface_actual_pinned_fixture(self):
        original = (Path(__file__).resolve().parents[1] / 'tests/fixtures/motion/BraveSettingsActivity.java').read_text()
        result = theme.settings_surface(theme.settings_motion(original))
        self.assertEqual(result, theme.settings_surface(theme.settings_motion(result)))
        self.assertEqual(result.count('fragmentView.setBackgroundColor(sandiumSettingsBackground())'), 1)
        # Destroyed-view callback must remain untouched.
        self.assertIn('                    View insetView = getInsetView(fragment, fragmentView);', result)
    def test_oppo_group_contract(self):
        self.assertEqual(theme.BACKGROUND, '#000000')
        self.assertEqual(theme.CARD, '#1A1A1A')
        self.assertEqual(theme.NIGHT['dialog_bg_color_dark_baseline'], theme.CARD)
        self.assertIn('instanceof androidx.preference.PreferenceFragmentCompat', theme.SETTINGS_GROUPS)
        self.assertIn('instanceof androidx.preference.PreferenceGroupAdapter', theme.SETTINGS_GROUPS)
        self.assertIn('instanceof androidx.preference.PreferenceCategory', theme.SETTINGS_GROUPS)
        self.assertIn('a.getParent() == b.getParent()', theme.SETTINGS_GROUPS)
        self.assertIn('getItemDecorationAt(i) instanceof SandiumPreferenceGroups', theme.SETTINGS_GROUPS)
        self.assertNotIn('setBackground', theme.SETTINGS_GROUPS)
        self.assertNotIn('setOnClickListener', theme.SETTINGS_GROUPS)
        self.assertNotIn('setAdapter', theme.SETTINGS_GROUPS)
        root = Path(__file__).resolve().parents[2]
        welcome = (root / 'android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java').read_text()
        self.assertIn('CARD = Color.rgb(26, 26, 26)', welcome)
        self.assertIn('PRIMARY = Color.rgb(25, 140, 255)', welcome)
        self.assertIn('BACKGROUND = Color.rgb(0, 0, 0)', welcome)

    def test_shields_tooltip_pinned_styles_idempotent(self):
        fixture = Path(__file__).resolve().parents[1] / 'tests/fixtures/shields-tooltip'
        for path in (theme.TOOLTIP_BACKGROUND, theme.TOOLTIP_GROUP, theme.TOOLTIP_LAYOUT, theme.TOOLTIP_TOOLBAR):
            original = (fixture / Path(path).name).read_text()
            result = theme.tooltip_style(original, path)
            self.assertEqual(result, theme.tooltip_style(result, path))
            self.assertNotEqual(result, original)
            with self.assertRaises(ValueError): theme.tooltip_style('unexpected', path)
            if path == theme.TOOLTIP_TOOLBAR:
                # Every line but the arrow color remains byte-for-byte identical:
                # anchoring, counters, click/dismiss and once-only policy are untouched.
                self.assertEqual(result.replace('R.color.sandium_shields_tooltip_surface', 'R.color.primitive_primary_35'), original)
            if path == theme.TOOLTIP_LAYOUT:
                self.assertEqual(result.replace('@color/sandium_shields_tooltip_text', '@color/onboarding_welcome_text_color').replace('@color/sandium_shields_tooltip_secondary', '@color/onboarding_welcome_text_color'), original)
                self.assertIn('app:tint="@color/brave_theme_success"', result)
                self.assertIn('android:contentDescription="@null"', result)
    def test_shields_tooltip_contrast_and_resource_closure(self):
        for palette in (theme.NIGHT, theme.LIGHT):
            for text in ('text', 'secondary'):
                for surface in ('surface', 'group'):
                    self.assertGreaterEqual(contrast(palette['sandium_shields_tooltip_' + text], palette['sandium_shields_tooltip_' + surface]), 4.5)
        self.assertEqual(theme.NIGHT['sandium_shields_tooltip_surface'], theme.BACKGROUND)
        self.assertEqual(theme.NIGHT['sandium_shields_tooltip_group'], theme.CARD)
        import json
        root = Path(__file__).resolve().parents[2]
        recipe = json.loads((root / '.circleci/features/removal-recipe.json').read_text())
        for key in ('core_restore', 'ui_only_core_restore'):
            for path in (theme.TOOLTIP_BACKGROUND, theme.TOOLTIP_GROUP, theme.TOOLTIP_LAYOUT, theme.TOOLTIP_TOOLBAR):
                self.assertIn(path, recipe[key])

    def test_welcome_reference_category_icon_contrast(self):
        for color in ['#02BE12', '#FDB200', '#FF7701', theme.ACCENT]:
            self.assertGreaterEqual(contrast(color, theme.CARD), 3)

    def test_scope(self):
        allkeys=set(theme.COMMON)|set(theme.NIGHT)|set(theme.LIGHT)
        self.assertFalse(any('error' in x or 'wallet' in x or 'incognito' in x or 'private_window' in x for x in allkeys))
        self.assertNotIn('baseline_primary_100',allkeys)
    def test_dynamic_choice_preserved(self):
        self.assertIn('BRAVE_ANDROID_DYNAMIC_COLORS_ENABLED',theme.NEW_DEFAULT)
        self.assertNotIn('writeBoolean',theme.NEW_DEFAULT)
        self.assertIn('false',theme.NEW_DEFAULT)
    def test_native_control_tokens(self):
        self.assertEqual(theme.COMMON['baseline_primary_80'],theme.ACCENT)
        self.assertEqual(theme.NIGHT['schemes_primary'],theme.ACCENT)
        self.assertEqual(theme.NIGHT['schemes_on_primary'],theme.ON_ACCENT)
        self.assertEqual(theme.COMMON['gm3_baseline_surface_dark'],theme.BACKGROUND)

if __name__=='__main__': unittest.main()
