import hashlib
import json
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

import shields_alignment as change

REPO = Path(__file__).resolve().parents[1]
NS = '{http://schemas.android.com/apk/res/android}'
DEFAULT_AAPT2 = REPO.parents[1] / 'raws1483-page-toolbar.kTqOFj/.local-audit/android-tools/aapt2'


class ShieldsAlignmentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ledger = REPO / 'raws-adblock/production-restore-recipe.json'
        cls.active = json.loads(ledger.read_bytes())['files'][change.LAYOUT]['after_sha256']
        cls.sha = change.OWNERS[change.LAYOUT]
        cls.before = (REPO / 'raws-adblock/production-postimages' / cls.sha).read_bytes()
        cls.after = change.transform(change.LAYOUT, cls.before)

    def test_only_three_switch_presentation_attributes_change(self):
        # The integration recipe may still hold the old file or the exact sealed output.
        self.assertIn(self.active, (self.sha, hashlib.sha256(self.after).hexdigest()))
        old_rows, new_rows = (list(ET.fromstring(body).iter()) for body in (self.before, self.after))
        self.assertEqual(len(old_rows), len(new_rows))
        changed = set()
        for before, after in zip(old_rows, new_rows):
            self.assertEqual(before.tag, after.tag)
            key = before.attrib.get(NS + 'id', '').removeprefix('@+id/')
            if key not in change.SITE_SWITCHES:
                self.assertEqual(before.attrib, after.attrib)
                continue
            changed.add(key)
            self.assertEqual(after.attrib[NS + 'paddingStart'], '16dp')
            self.assertEqual(after.attrib[NS + 'paddingEnd'], '16dp')
            self.assertEqual(after.attrib[NS + 'gravity'], 'start|center_vertical')
            self.assertEqual(after.attrib[NS + 'textAlignment'], 'viewStart')
            self.assertEqual(after.attrib[NS + 'minHeight'], '48dp')
            self.assertEqual(after.attrib[NS + 'enabled'], 'false')
            copy = dict(after.attrib)
            for new in ('paddingStart', 'paddingEnd', 'textAlignment'):
                del copy[NS + new]
            copy[NS + 'paddingHorizontal'] = '16dp'
            copy[NS + 'gravity'] = 'center_vertical'
            self.assertEqual(before.attrib, copy)
        self.assertEqual(changed, set(change.SITE_SWITCHES))
        self.assertEqual(self.after.count(change.NEW_ATTRIBUTES.encode()), 3)
        self.assertEqual(self.after.replace(change.NEW_ATTRIBUTES.encode(), change.OLD_ATTRIBUTES.encode()), self.before)

    def test_refuses_drift_and_unknown_owner(self):
        with self.assertRaises(ValueError):
            change.transform(change.LAYOUT, self.before + b'\n')
        with self.assertRaises(ValueError):
            change.transform('not-owned.xml', self.before)

    def test_aapt2_compiles_exact_layout_when_available(self):
        aapt2 = os.getenv('AAPT2') or shutil.which('aapt2') or DEFAULT_AAPT2
        if not Path(aapt2).is_file():
            self.skipTest('No local aapt2')
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            layout = base / 'res' / 'layout' / Path(change.LAYOUT).name
            layout.parent.mkdir(parents=True)
            layout.write_bytes(self.after)
            out = base / 'compiled'
            out.mkdir()
            subprocess.run([aapt2, 'compile', '-o', out, layout], check=True)
            self.assertEqual(len(list(out.glob('*.flat'))), 1)


if __name__ == '__main__':
    unittest.main()
