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
MATERIAL_SWITCH = 'com.google.android.material.materialswitch.MaterialSwitch'


class ShieldsAlignmentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ledger = REPO / 'raws-adblock/production-restore-recipe.json'
        cls.active = json.loads(ledger.read_bytes())['files']
        cls.images = REPO / 'raws-adblock/production-postimages'
        cls.before = {path: (cls.images / sha).read_bytes() for path, sha in change.OWNERS.items()}
        cls.after = {path: change.transform(path, data) for path, data in cls.before.items()}

    def test_replay_identifies_exact_active_postimages(self):
        for path, body in self.after.items():
            with self.subTest(path=path):
                digest = hashlib.sha256(body).hexdigest()
                self.assertEqual(digest, self.active[path]['after_sha256'])
                self.assertEqual(body, (self.images / digest).read_bytes())

    def test_labels_match_action_typography_without_replacing_switches(self):
        old, new = [ET.fromstring(body[change.LAYOUT]) for body in (self.before, self.after)]
        action = new.find(f".//TextView[@{NS}id='@+id/raws_shields_block_element']")
        self.assertIsNotNone(action)
        for name, string in change.SITE_SWITCHES.items():
            with self.subTest(name=name):
                node = new.find(f".//{MATERIAL_SWITCH}[@{NS}id='@+id/{name}']")
                native_before = old.find(f".//{MATERIAL_SWITCH}[@{NS}id='@+id/{name}']")
                expected = dict(native_before.attrib)
                del expected[NS + 'text']
                del expected[NS + 'textSize']
                del expected[NS + 'textColor']
                expected[NS + 'contentDescription'] = '@string/' + string
                expected[NS + 'layout_height'] = 'match_parent'
                self.assertEqual(node.attrib, expected)
                row = new.find(f'.//{MATERIAL_SWITCH}[@{NS}id="@+id/{name}"]/..')
                self.assertEqual(row.tag, 'FrameLayout')
                self.assertEqual(len(row), 2)
                label = row[0]
                self.assertIs(row[1], node, 'native switch remains the full-row top hit target')
                self.assertEqual(row.attrib[NS + 'importantForAccessibility'], 'no')
                self.assertEqual(row.attrib[NS + 'layout_height'], action.attrib[NS + 'layout_height'])
                self.assertEqual(row.attrib[NS + 'minHeight'], action.attrib[NS + 'minHeight'])
                self.assertEqual(label.tag, action.tag)
                self.assertEqual(label.attrib[NS + 'text'], '@string/' + string)
                for attr in ('textSize', 'minHeight', 'layout_width', 'layout_height',
                             'paddingVertical', 'gravity', 'clickable', 'focusable'):
                    self.assertEqual(label.attrib[NS + attr], action.attrib[NS + attr], attr)
                self.assertEqual(label.attrib[NS + 'paddingStart'], action.attrib[NS + 'paddingHorizontal'])
                self.assertGreater(int(label.attrib[NS + 'paddingEnd'].removesuffix('dp')),
                                   int(node.attrib[NS + 'paddingEnd'].removesuffix('dp')))
                self.assertEqual(label.attrib[NS + 'importantForAccessibility'], 'no')
                self.assertNotIn(NS + 'maxLines', label.attrib)
                self.assertEqual(label.attrib[NS + 'alpha'], node.attrib[NS + 'alpha'])
                row.attrib.clear()
                row.attrib.update(native_before.attrib)
                row[:] = []
                row.tag = native_before.tag
                row.text = native_before.text
        self.assertEqual(ET.tostring(old), ET.tostring(new), 'every unrelated view is unchanged')

    def test_native_listeners_and_checked_state_are_byte_identical(self):
        before = self.before[change.JAVA].decode()
        after = self.after[change.JAVA].decode()
        pairs = (
            ('mDarkSwitch', 'raws_shields_dark_pages_label'),
            ('mCookieSwitch', 'raws_shields_block_cookies_label'),
            ('row', 'raws_shields_ads_label'),
        )
        for row, label in pairs:
            call = f'renderSiteSwitchEditability({row}, R.id.{label}, editable);'
            self.assertEqual(after.count(call), 1)
            after = after.replace(call, f'{row}.setEnabled(editable);\n        '
                                  f'{row}.setAlpha(editable ? 1f : .55f);')
        method = self._java_helper(after)
        self.assertEqual(after.replace(method + '\n\n', ''), before)

    def test_extracted_production_helper_preserves_switch_and_label_dimming(self):
        java = shutil.which('java')
        if not java:
            self.skipTest('No Java launcher')
        helper = self._java_helper(self.after[change.JAVA].decode())
        source = '''class Check {
    static class View {
        float alpha;
        void setAlpha(float value) { alpha = value; }
    }
    static class SwitchCompat extends View {
        boolean enabled;
        boolean checked = true;
        void setEnabled(boolean value) { enabled = value; }
    }
    static class Content {
        final View label = new View();
        View findViewById(int id) {
            if (id != 19) throw new AssertionError();
            return label;
        }
    }
    final Content mContent = new Content();
''' + helper + '''
    public static void main(String[] args) {
        Check test = new Check();
        SwitchCompat row = new SwitchCompat();
        for (boolean editable : new boolean[]{false, true, false}) {
            test.renderSiteSwitchEditability(row, 19, editable);
            float expected = editable ? 1f : .55f;
            if (row.enabled != editable || row.alpha != expected
                    || test.mContent.label.alpha != expected || !row.checked)
                throw new AssertionError();
        }
    }
}
'''
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / 'Check.java'
            file.write_text(source)
            subprocess.run([java, file], check=True)

    @staticmethod
    def _java_helper(source):
        start = source.index('    private void renderSiteSwitchEditability(')
        return source[start: source.index('\n    }', start) + len('\n    }')]

    def test_refuses_drift_and_unknown_owner(self):
        for path, data in self.before.items():
            with self.assertRaises(ValueError):
                change.transform(path, data + b'\n')
            with self.assertRaises(ValueError):
                change.transform('not-owned.xml', data)

    def test_aapt2_compiles_exact_layout_when_available(self):
        aapt2 = os.getenv('AAPT2') or shutil.which('aapt2') or DEFAULT_AAPT2
        if not Path(aapt2).is_file():
            self.skipTest('No local aapt2')
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            layout = base / 'res' / 'layout' / Path(change.LAYOUT).name
            layout.parent.mkdir(parents=True)
            layout.write_bytes(self.after[change.LAYOUT])
            out = base / 'compiled'
            out.mkdir()
            subprocess.run([aapt2, 'compile', '-o', out, layout], check=True)
            self.assertEqual(len(list(out.glob('*.flat'))), 1)


if __name__ == '__main__':
    unittest.main()
