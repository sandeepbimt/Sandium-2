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
        for color in [theme.BACKGROUND, theme.CARD, theme.ACCENT,
                      theme.NIGHT['schemes_on_surface_variant']]:
            self.assertEqual(color[1:3], color[3:5])
            self.assertEqual(color[3:5], color[5:7])
    def test_welcome_checked_switch_contrast(self):
        self.assertGreaterEqual(contrast('#171717', '#F5F5F5'), 3)
        source = (Path(__file__).resolve().parents[2] / 'android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java').read_text()
        self.assertIn('private static final int SUCCESS = Color.rgb(230, 244, 232)', source)
        self.assertIn('                    PRIMARY_TEXT,', source)
    def test_settings_subpage_tokens_have_readable_day_and_night_pairs(self):
        for name in ['filter_title_color', 'filter_summary_color',
                     'bookmark_menu_text_color', 'brave_theme_hint_text',
                     'bookmark_import_export_dialog_button_color', 'url_text_primary', 'text_tertiary']:
            self.assertGreaterEqual(contrast(theme.NIGHT[name], theme.CARD), 4.5, name)
            self.assertGreaterEqual(contrast(theme.LIGHT[name], '#E8E8E8'), 4.5, name)
        self.assertEqual(theme.NIGHT['bookmark_menu_bg_color'], theme.CARD)
        self.assertEqual(theme.COMMON['baseline_neutral_0'], theme.BACKGROUND)
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
