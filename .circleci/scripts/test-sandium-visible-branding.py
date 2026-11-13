#!/usr/bin/env python3
import argparse
import importlib.util
from pathlib import Path
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET

spec = importlib.util.spec_from_file_location('branding', Path(__file__).with_name('apply-sandium-visible-branding.py'))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

class BrandingTests(unittest.TestCase):
    def test_only_copy_changes(self):
        source = '<message name="IDS_BRAVE_EXIT" desc="Brave description">Exit Brave <ph name="URL">$1<ex>https://Brave.example</ex></ph> https://Brave.example</message>'
        out, changes, _ = b.rebrand_messages(source)
        self.assertIn('Exit Sandium', out)
        self.assertIn('name="IDS_BRAVE_EXIT" desc="Brave description"', out)
        self.assertEqual(out.count('https://Brave.example'), 2)
        self.assertEqual(changes, ['IDS_BRAVE_EXIT'])
        self.assertEqual(b.rebrand_messages(out)[0], out)

    def test_attribution_and_services_unchanged(self):
        for ident, body in [('IDS_LICENSE', 'Brave Authors'), ('IDS_SEARCH', 'Brave Search'),
                            ('IDS_PRIVACY_POLICY', 'Brave privacy policy'), ('IDS_VPN', 'Brave VPN'),
                            ('IDS_LEGAL', 'Copyright Brave Software')]:
            source = f'<message name="{ident}">{body}</message>'
            self.assertEqual(b.rebrand_messages(source)[0], source)

    def test_shields_and_browser_identity(self):
        for phrase in ('Brave Shields', 'Open in Brave', "Brave's password manager", 'Your Brave'):
            source = f'<message name="IDS_BROWSER_COPY">{phrase}</message>'
            self.assertIn(phrase.replace('Brave', 'Sandium'), b.rebrand_messages(source)[0])

    def test_drawable_preserves_aspect_and_intrinsic_dimensions(self):
        root = ET.fromstring(b.mark_drawable(162,162))
        ns='{http://schemas.android.com/apk/res/android}'
        self.assertEqual(root[0].attrib[ns+'width'], '162dp')
        w=float(root[1].attrib[ns+'width'][:-2]);h=float(root[1].attrib[ns+'height'][:-2])
        self.assertAlmostEqual(w/h,64/77,places=3)
        self.assertEqual(root[1][0].attrib[ns+'src'],'@drawable/sandium_toolbar_mark')

    def test_full_fixture_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            core=Path(directory)
            for rel in b.STRING_FILES:
                p=core/rel;p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text('<grit><message name="IDS_BROWSER">Brave browser</message></grit>')
            for rel in ('android/java/brave-res/drawable/ic_brave_logo.xml','android/java/res/drawable/chrome_logo_on_circular_background.xml'):
                p=core/rel;p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text('<!-- Copyright (c) The Brave Authors. --><vector/>')
            for rel in ('android/java/res/layout/new_tab_page_incognito.xml','android/java/brave-res/xml/brave_main_preferences.xml'):
                p=core/rel;p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text('<view src="@drawable/ic_social_brave_release_favicon_fullheight_color"/>')
            mark=core/'android/java/brave-res/drawable-nodpi/sandium_toolbar_mark.webp'
            mark.parent.mkdir(parents=True,exist_ok=True);mark.write_bytes(b'fixture')
            fav=core/'browser/ui/android/favicon'
            fav.mkdir(parents=True,exist_ok=True)
            (fav/'BUILD.gn').write_text('android_resources("java_resources") {\n}\n')
            j=fav/'java/src/org/chromium/chrome/browser/ui/favicon/BraveTabListFaviconProvider.java'
            j.parent.mkdir(parents=True,exist_ok=True)
            j.write_text('R.drawable.ic_social_brave_outline_favicon_fullheight; R.drawable.ic_social_brave_carved_favicon_fullheight;\n        drawable.setBounds(0, 0, size, size);\n        drawable.draw(canvas);')
            n=core/'android/java/org/chromium/chrome/browser/notifications/retention/RetentionNotificationUtil.java'
            n.parent.mkdir(parents=True,exist_ok=True)
            n.write_text('private static final String BRAVE_BROWSER = "Brave Browser";')
            b.apply(core)
            self.assertIn('ic_social_brave_release_favicon_fullheight_color',
                          (core/'android/java/brave-res/xml/brave_main_preferences.xml').read_text())
            self.assertIn('R.drawable.sandium_ntp_mark',j.read_text())
            self.assertIn('canvas.scale((float) size / intrinsicWidth',j.read_text())
            self.assertIn('"Sandium"',n.read_text())
            first={str(p):p.read_bytes() for p in core.rglob('*') if p.is_file()}
            b.apply(core)
            self.assertEqual(first,{str(p):p.read_bytes() for p in core.rglob('*') if p.is_file()})
            self.assertIn('The Brave Authors', (core/'android/java/brave-res/drawable/ic_brave_logo.xml').read_text())


def verify_core(core):
    refresh_spec = importlib.util.spec_from_file_location(
        'branding_refresh', Path(__file__).with_name('test-sandium-branding-refresh.py'))
    refresh = importlib.util.module_from_spec(refresh_spec)
    refresh_spec.loader.exec_module(refresh)
    refresh.verify_shields_copy(core / b.STRING_FILES[0], final=True)
    ui_spec = importlib.util.spec_from_file_location(
        'ui_identity', Path(__file__).with_name('test-sandium-ui-prune.py'))
    ui = importlib.util.module_from_spec(ui_spec)
    ui_spec.loader.exec_module(ui)
    ui.verify_ui_identity(core, core.parent, final=True)
    for rel in b.STRING_FILES:
        content=(core/rel).read_text()
        if b.rebrand_messages(content)[0] != content:
            raise RuntimeError('Unbranded browser-identity messages: '+rel)
    for rel in ('android/java/brave-res/drawable/ic_brave_logo.xml','android/java/res/drawable/chrome_logo_on_circular_background.xml'):
        content=(core/rel).read_text()
        ET.fromstring(content)
        if '@drawable/sandium_toolbar_mark' not in content:
            raise RuntimeError('Logo missing: '+rel)
    mark=core/'android/java/brave-res/drawable-nodpi/sandium_toolbar_mark.webp'
    if not mark.is_file():
        raise RuntimeError('Existing Sandium asset has not been installed')
    build=(core/'android/BUILD.gn').read_text()
    if 'java/brave-res/drawable-nodpi/sandium_toolbar_mark.webp' not in build:
        raise RuntimeError('Existing Sandium mark is not registered in Android GN resources')
    print('SANDIUM_VISIBLE_BRANDING_VERIFY=PASS')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--core',type=Path)
    args=parser.parse_args()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BrandingTests))
    if not result.wasSuccessful(): raise SystemExit(1)
    if args.core:verify_core(args.core)
