#!/usr/bin/env python3
"""#1086 regression: prune -> final identity -> checkpoint -> Brave copy -> prune."""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

p = load('prune', 'apply-sandium-ui-prune.py')
v = load('verify', 'test-sandium-ui-prune.py')
b = load('branding', 'apply-sandium-visible-branding.py')


class UIReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src = Path(self.tmp.name)
        self.core = self.src / 'brave'
        self.chrome = self.src / 'chrome/browser/ui/android/strings/android_chrome_strings.grd'
        self.canonical = self.core / 'browser/ui/android/strings/android_chrome_strings.grd'
        self.brave = self.core / 'browser/ui/android/strings/android_brave_strings.grd'
        self.gn = self.core / 'android/BUILD.gn'
        for file in (self.chrome, self.canonical, self.brave, self.gn):
            file.parent.mkdir(parents=True, exist_ok=True)
        self.gn.write_text('sources = []\n')
        self.brave.write_text('<grit><messages>' + ''.join(
            f'<message name="{name}">{body.replace("&", "&amp;")}</message>'
            for name, body in v.UI_COPY.items()) + '</messages></grit>')
        self.set_body('Make Brave default')
        shutil.copyfile(self.chrome, self.canonical)

    def set_body(self, body):
        self.chrome.write_text('<grit><messages><message desc="variable description" '
                              'name="IDS_MAKE_CHROME_DEFAULT">\n  ' + body +
                              '\n</message></messages></grit>')

    def patch(self):
        p.patch_make_brave_default_label(self.core, self.src)

    def test_all_known_states_converge_and_repeat(self):
        for state in ('Make Chrome default', 'Make Brave default', 'Make Sandium default'):
            self.set_body(state)
            self.patch()
            expected = self.chrome.read_bytes()
            self.patch()
            self.assertEqual(expected, self.chrome.read_bytes())
            self.assertIn('Make Sandium default', expected.decode())

    def test_actual_overlay_order_repeated(self):
        for _ in range(3):
            # Brave npm build updates Chromium branding from its canonical core GRD.
            shutil.copyfile(self.canonical, self.chrome)
            self.patch()
            v.verify_ui_identity(self.core, self.src)
            for file in (self.canonical, self.brave):
                file.write_text(b.rebrand_messages(file.read_text())[0])
            v.verify_ui_identity(self.core, self.src, final=True)

    def test_corrupt_bodies_rejected_unchanged(self):
        for body in ('Make Other default', 'Make Chrome default\nExtra',
                     'Extra\nMake Chrome default', '<ph>Make Brave default</ph>', ''):
            self.set_body(body)
            before = self.chrome.read_bytes()
            with self.assertRaises(RuntimeError):
                self.patch()
            self.assertEqual(before, self.chrome.read_bytes())

    def test_missing_duplicate_ids_rejected(self):
        for text in ('<grit/>', self.chrome.read_text().replace('</messages>',
                     '<message name="IDS_MAKE_CHROME_DEFAULT">Make Brave default</message></messages>')):
            self.chrome.write_text(text)
            with self.assertRaises(RuntimeError):
                self.patch()

    def test_final_rejects_upstream_identity(self):
        self.patch()
        with self.assertRaises(SystemExit):
            v.verify_ui_identity(self.core, self.src, final=True)

    def test_wrong_id_extra_markup_and_duplicates_fail_gate(self):
        for mutation in (
            lambda s: s.replace('IDS_BRAVE_SHIELDS_AND_PRIVACY', 'IDS_OTHER'),
            lambda s: s.replace('Brave Shields &amp; privacy', '<ph>Brave Shields &amp; privacy</ph>'),
            lambda s: s.replace('</messages>', '<message name="IDS_BRAVE_SHIELDS_AND_PRIVACY">Brave Shields &amp; privacy</message></messages>'),
            lambda s: s.replace('Brave Shields &amp; privacy', 'Brave Shields &amp; privacy extra'),
        ):
            original = self.brave.read_text()
            self.brave.write_text(mutation(original))
            with self.assertRaises(SystemExit):
                v.verify_ui_identity(self.core, self.src)
            self.brave.write_text(original)

    def test_legacy_duplicate_resource_removed(self):
        override = self.core / 'android/java/brave-res/values/sandium_ui_overrides.xml'
        override.parent.mkdir(parents=True)
        override.write_text('<resources/>')
        self.gn.write_text('    "java/brave-res/values/sandium_ui_overrides.xml",\n')
        self.patch()
        self.assertFalse(override.exists())
        self.assertNotIn('sandium_ui_overrides', self.gn.read_text())


if __name__ == '__main__':
    unittest.main()
