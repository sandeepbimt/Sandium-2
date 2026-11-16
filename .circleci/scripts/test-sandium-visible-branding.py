#!/usr/bin/env python3
import argparse
import importlib.util
from pathlib import Path
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

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

    def test_about_titles_in_consumed_source_preserve_legal(self):
        legal = '<message name="IDS_LEGAL_INFORMATION_SUMMARY">Copyright The Brave Authors</message>'
        for brand in ('Chrome', 'Brave', 'Sandium'):
            source = ''.join(f'<message name="{name}">About {brand}</message>'
                             for name in ('IDS_PREFS_ABOUT_CHROME', 'IDS_MENU_ABOUT_CHROME')) + legal
            out = b.rebrand_about_titles(source)
            self.assertEqual(out.count('About Sandium'), 2)
            self.assertIn(legal, out)
            self.assertEqual(out, b.rebrand_about_titles(out))
        for invalid in ('', source + source, source.replace('About Sandium', 'Other title')):
            with self.assertRaises(RuntimeError):
                b.rebrand_about_titles(invalid)

    def test_copyright_relocated_not_deleted(self):
        fixtures=Path(__file__).resolve().parents[2]/'tests/fixtures/about-branding'
        original_about=(fixtures/'AboutChromeSettings.java').read_text()
        original_legal=(fixtures/'LegalInformationSettings.java').read_text()
        about, legal=b.relocate_copyright(original_about, original_legal)
        self.assertIn('findPreference(PREF_LEGAL_INFORMATION)', about)
        self.assertNotIn(b.COPYRIGHT_BLOCK, about)
        self.assertIn(b.COPYRIGHT_CLEARED, about)
        self.assertIn('R.xml.legal_information_preferences', legal)
        self.assertIn('R.string.legal_information_summary', legal)
        self.assertIn('calendar.get(java.util.Calendar.YEAR)', legal)
        self.assertEqual((about, legal), b.relocate_copyright(about, legal))
        with self.assertRaises(RuntimeError): b.relocate_copyright('changed', original_legal)
        with self.assertRaises(RuntimeError): b.relocate_copyright(original_about, 'changed')

    def test_reset_inventory_covers_new_inputs(self):
        import json
        recipe=json.loads((Path(__file__).resolve().parents[1]/'features/removal-recipe.json').read_text())
        for key in ('chromium_restore','ui_only_chromium_restore'):
            self.assertIn(b.ABOUT_JAVA, recipe[key])
            self.assertIn(b.LEGAL_JAVA, recipe[key])

    def test_consumed_copy_and_recursive_parts_are_branded_together(self):
        import json
        with tempfile.TemporaryDirectory() as temporary:
            src=Path(temporary); core=src/'brave'
            canonical='browser/ui/android/strings/android_chrome_strings.grd'
            consumed='chrome/'+canonical
            pairs=[{'core':canonical,'consumed':consumed},
                   {'core':'browser/ui/android/strings/child.grdp','consumed':'chrome/browser/ui/android/strings/child.grdp'}]
            root='<grit><part file="child.grdp"/><message name="IDS_PASSWORD_MANAGER_SETTINGS_TITLE">Brave Password Manager</message></grit>'
            child='<grit-part><message name="IDS_CLEAR">Clear Brave browsing data</message><message name="IDS_LEGAL">Copyright The Brave Authors</message><message name="IDS_URL">https://brave.com</message></grit-part>'
            for pair, text in zip(pairs, [root,child]):
                for path in (core/pair['core'],src/pair['consumed']):
                    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
            manifest=src/'manifest.json'
            manifest.write_text(json.dumps({'roots':[pairs[0]],'copies':pairs}))
            with patch.object(b,'COPY_MANIFEST',manifest):
                with self.assertRaisesRegex(RuntimeError,'Unbranded consumed'):
                    b.rebrand_consumed_graph(core,verify=True)
                report=b.rebrand_consumed_graph(core)
                self.assertEqual(len(report),4)
                self.assertIn('Sandium Password Manager',(src/consumed).read_text())
                for path in (core/pairs[1]['core'],src/pairs[1]['consumed']):
                    self.assertIn('Clear Sandium browsing data',path.read_text())
                    self.assertIn('The Brave Authors',path.read_text())
                    self.assertIn('https://brave.com',path.read_text())
                b.rebrand_consumed_graph(core,verify=True)
                # Simulate npm overwriting consumed files from old checkpoint.
                (src/consumed).write_text(root)
                b.rebrand_consumed_graph(core)
                b.rebrand_consumed_graph(core,verify=True)
                # Source drift must not silently escape the inventory.
                (core/canonical).write_text(root.replace('child.grdp','new.grdp'))
                (core/Path(canonical).parent/'new.grdp').write_text(child)
                with self.assertRaisesRegex(RuntimeError,'inventory drift'):
                    b.branding_copy_manifest(core)

    def test_developer_hint_keeps_copyright_and_identifiers(self):
        source='<!-- Copyright The Brave Authors --><Preference android:key="beta_stable_hint" android:title="Hint: You can also enable Developer options on Beta/Stable channels by tapping the Brave version in &quot;Settings > About Brave&quot; multiple times."/>'
        out=b.rebrand_developer_hint(source)
        self.assertIn('About Sandium',out)
        self.assertIn('The Brave Authors',out)
        self.assertEqual(out,b.rebrand_developer_hint(out))
        with self.assertRaises(RuntimeError):b.rebrand_developer_hint('<changed/>')
        import json
        recipe=json.loads((Path(__file__).resolve().parents[1]/'features/removal-recipe.json').read_text())
        for key in ('core_restore','ui_only_core_restore'):
            self.assertIn(b.DEVELOPER_XML,recipe[key])
        for key in ('chromium_restore','ui_only_chromium_restore'):
            self.assertIn('chrome/'+b.DEVELOPER_XML,recipe[key])

    def test_service_and_data_recipient_claims_not_rebranded(self):
        for ident,text in [('IDS_FEEDBACK_ATTACH_FILE_NOTE','File will be sent to Brave for debugging'),
                           ('IDS_CREATE_GOOGLE_DOC','Create a Brave document'),
                           ('IDS_POLICY_OFF_CWS_URL_ERROR','Brave Webstore'),
                           ('IDS_DICTIONARY','downloads from Brave servers')]:
            source=f'<message name="{ident}">{text}</message>'
            self.assertEqual(source,b.rebrand_messages(source)[0])

    def test_provider_and_disclosure_semantics_survive_broad_graph(self):
        examples = [
            ('IDS_CRASH_REPORTING', 'Automatically send crash reports to Brave'),
            ('IDS_GENERIC', 'Page content will be shared with <b>Brave</b>'),
            ('IDS_GENERIC', 'Data is stored by Brave'),
            ('IDS_GENERIC', 'Your chats may be reviewed by Brave'),
            ('IDS_GENERIC', 'Brave Browser Cloud Management'),
            ('IDS_GENERIC', "Brave’s Advanced Protection"),
            ('IDS_AUTOFILL_AI_NOTICE', 'Brave will process this data'),
            ('IDS_FEATURE_SHOWCASE_GEMINI_DISCLOSURE_2', 'Brave Terms apply'),
            ('IDS_GENERIC', 'Use Brave DNS as backup'),
            ('IDS_GENERIC', 'Brave Root Store'),
            ('IDS_GENERIC', 'Brave Sync'),
            ('IDS_GENERIC', 'Brave Workspace data'),
            ('IDS_GENERIC', 'Brave Apps Script'),
            ('IDS_GENERIC', 'Brave AI Mode'),
            ('IDS_AUTOFILL_GMAIL_OTP_REQUIRED_STEP_2', 'Smart features in other Brave products'),
            ('IDS_MERCHANT_VIEWER_PREVIEW_SHEET_TITLE', 'Brave | About this store'),
            ('IDS_PIX_ACCOUNT_LINKING_PROMPT_C_BODY', 'Brave encryption protects your info'),
            ('IDS_GENERIC', 'Brave account'),
            ('IDS_CONTEXTUAL_CUEING_SETTINGS_CONSIDER_1_PRIVATE', 'Brave processes page titles and URLs in the cloud'),
            ('IDS_GENERIC', 'Brave may personalize Search based on your history'),
            ('IDS_GENERIC', 'Notify Brave that your account may be at risk'),
            ('IDS_GENERIC', 'Websites and services, including Brave'),
        ]
        for ident, body in examples:
            with self.subTest(ident=ident, body=body):
                source = f'<message name="{ident}">{body}</message>'
                out, changed, retained = b.rebrand_messages(source)
                self.assertEqual(source, out)
                self.assertEqual([], changed)
                self.assertEqual([ident], retained)

    def test_factual_external_help_center_is_preserved(self):
        source='<message name="IDS_HELP">Open the Brave Help Center in a new tab</message>'
        self.assertEqual(source,b.rebrand_messages(source)[0])

    def test_drawable_preserves_aspect_and_intrinsic_dimensions(self):
        root = ET.fromstring(b.mark_drawable(162,162))
        ns='{http://schemas.android.com/apk/res/android}'
        self.assertEqual(root[0].attrib[ns+'width'], '162dp')
        w=float(root[1].attrib[ns+'width'][:-2]);h=float(root[1].attrib[ns+'height'][:-2])
        self.assertAlmostEqual(w/h,64/77,places=3)
        self.assertEqual(root[1][0].attrib[ns+'src'],'@drawable/sandium_toolbar_mark')

    def test_full_fixture_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            core=Path(directory) / 'brave'
            consumed=core.parent/'chrome/browser/ui/android/strings/android_chrome_strings.grd'
            consumed.parent.mkdir(parents=True, exist_ok=True)
            consumed.write_text('<grit>'+''.join(f'<message name="{name}">About Brave</message>' for name in ('IDS_PREFS_ABOUT_CHROME','IDS_MENU_ABOUT_CHROME'))+'</grit>')
            for rel, name in ((b.ABOUT_JAVA, 'AboutChromeSettings'), (b.LEGAL_JAVA, 'LegalInformationSettings')):
                target=core.parent/rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text((Path(__file__).resolve().parents[2]/'tests/fixtures/about-branding'/f'{name}.java').read_text())
            for hint in (core/b.DEVELOPER_XML, core.parent/('chrome/'+b.DEVELOPER_XML)):
                hint.parent.mkdir(parents=True, exist_ok=True)
                hint.write_text('<Preference android:title="Hint: You can also enable Developer options on Beta/Stable channels by tapping the Brave version in &quot;Settings > About Brave&quot; multiple times."/>')
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
            with patch.object(b, 'rebrand_consumed_graph', return_value={}):
                b.apply(core)
            self.assertIn('ic_social_brave_release_favicon_fullheight_color',
                          (core/'android/java/brave-res/xml/brave_main_preferences.xml').read_text())
            self.assertIn('R.drawable.sandium_ntp_mark',j.read_text())
            self.assertIn('canvas.scale((float) size / intrinsicWidth',j.read_text())
            self.assertIn('"Sandium"',n.read_text())
            first={str(p):p.read_bytes() for p in core.parent.rglob('*') if p.is_file()}
            with patch.object(b, 'rebrand_consumed_graph', return_value={}):
                b.apply(core)
            self.assertEqual(first,{str(p):p.read_bytes() for p in core.parent.rglob('*') if p.is_file()})
            self.assertIn('The Brave Authors', (core/'android/java/brave-res/drawable/ic_brave_logo.xml').read_text())


def verify_core(core):
    b.rebrand_consumed_graph(core, verify=True)
    for hint in (core/b.DEVELOPER_XML, core.parent/('chrome/'+b.DEVELOPER_XML)):
        if b.rebrand_developer_hint(hint.read_text()) != hint.read_text():
            raise RuntimeError('Developer hint unbranded')
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
    consumed=(core.parent/'chrome/browser/ui/android/strings/android_chrome_strings.grd').read_text()
    if b.rebrand_about_titles(consumed) != consumed:
        raise RuntimeError('Unbranded consumed About titles')
    about=(core.parent/b.ABOUT_JAVA).read_text()
    legal=(core.parent/b.LEGAL_JAVA).read_text()
    if (about, legal) != b.relocate_copyright(about, legal):
        raise RuntimeError('Copyright relocation missing')
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
