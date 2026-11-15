"""Prevent feature removal from deleting adjacent, retained Android components."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REL = 'android/java/AndroidManifest.xml'
ANDROID = '{http://schemas.android.com/apk/res/android}'

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'.circleci/scripts'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def components(text):
    root = ET.fromstring('<manifest xmlns:android="http://schemas.android.com/apk/res/android">'+text+'</manifest>')
    return {node.attrib[ANDROID+'name']: ET.tostring(node).strip()
            for node in root if ANDROID+'name' in node.attrib}

class ManifestPreservation(unittest.TestCase):
    def test_pinned_all_non_feature_components_preserved(self):
        source = (ROOT/'tests/fixtures/packaged-extras'/REL).read_text()
        original = components(source)
        for op in json.loads((ROOT/'.circleci/features/playlist-removal/operations.json').read_text()):
            if op['path'] == REL:
                self.assertEqual(source.count(op['old']), 1)
                source = source.replace(op['old'], op['new'])
        source = load('apply-sandium-remove-vpn').transform(REL, source)
        source = load('apply-sandium-wallet-removal').transform(REL, source)
        source = load('apply-sandium-leo-removal').manifest(source)
        source = load('remove-sandium-packaged-extras').transform(REL, source)
        removed = ('org.chromium.chrome.browser.vpn.', 'org.chromium.chrome.browser.crypto_wallet.',
                   'org.chromium.chrome.browser.playlist.', 'com.brave.playlist.',
                   'org.chromium.chrome.browser.brave_leo.BraveLeoPlansActivity', 'com.wireguard.')
        expected = {name: value for name, value in original.items() if not name.startswith(removed)}
        self.assertEqual(components(source), expected)
        for name in load('audit-sandium-stripped-apk').REQUIRED_ACTIVITIES:
            self.assertIn(name, components(source))

    def test_self_closing_and_paired_removal_do_not_consume_neighbor(self):
        for script, name in [('apply-sandium-remove-vpn','org.chromium.chrome.browser.vpn.Test'),
                             ('apply-sandium-wallet-removal','org.chromium.chrome.browser.crypto_wallet.Test'),
                             ('apply-sandium-leo-removal','org.chromium.chrome.browser.brave_leo.BraveLeoPlansActivity')]:
            module = load(script)
            for ending in ('/>', '><intent-filter><action android:name="test"/></intent-filter></activity>'):
                for neighbor_ending in ('/>','></activity>'):
                    text = '<activity android:name="'+name+'"'+ending+'\n<activity android:name="retained.Activity"'+neighbor_ending
                    out = module.manifest(text) if script.endswith('leo-removal') else module.transform(REL,text)
                    self.assertEqual(set(components(out)), {'retained.Activity'})

    def test_recipe_bound_apk_missing_manifest_rejected(self):
        audit = load('audit-sandium-stripped-apk')
        with tempfile.TemporaryDirectory() as td:
            apk = Path(td)/'a.apk'
            with zipfile.ZipFile(apk,'w') as archive:
                archive.writestr('placeholder', 'not a real APK')
            with self.assertRaisesRegex(ValueError, 'Required AndroidManifest.xml missing'):
                audit.audit(apk, recipe=ROOT/'.circleci/features/removal-recipe.json')

    def test_apk_missing_onboarding_rejected(self):
        audit = load('audit-sandium-stripped-apk')
        for encoding in ('utf-8','utf-16le'):
            with tempfile.TemporaryDirectory() as td:
                apk = Path(td)/'a.apk'
                with zipfile.ZipFile(apk,'w') as archive:
                    archive.writestr('AndroidManifest.xml', '\0'.join(audit.REQUIRED_ACTIVITIES[1:]).encode(encoding))
                with self.assertRaisesRegex(ValueError, 'Required retained activity.*WelcomeOnboardingActivity'):
                    audit.audit(apk)

if __name__ == '__main__':
    unittest.main()
