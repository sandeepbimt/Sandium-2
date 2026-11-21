"""Guard the admitted RawS Android resources before a full build."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1] / 'raws-adblock'
ANDROID_NS = 'http://schemas.android.com/apk/res/android'
SHIELDS = 'chrome/android/java/res/layout/raws_global_shield_sheet.xml'
RES_DIR = re.compile(r'res(?:_[a-z][a-z0-9_]*)?\Z')


def check_style_namespace(path, xml):
    parsed = ET.fromstring(xml)
    for element in parsed.iter():
        if f'{{{ANDROID_NS}}}style' in element.attrib:
            raise ValueError(f'{path}: <{element.tag}> must use unqualified style=, not android:style=')
    return parsed


class RawSResourceXMLTest(unittest.TestCase):
    def test_all_active_android_resources_use_correct_style_attribute(self):
        recipe = json.loads((ROOT / 'production-restore-recipe.json').read_bytes())
        checked = set()
        for path, entry in recipe['files'].items():
            candidate = PurePosixPath(path)
            if candidate.suffix != '.xml' or not any(
                    RES_DIR.fullmatch(segment) for segment in candidate.parts[:-1]):
                continue
            with self.subTest(path=path):
                sha = entry['after_sha256']
                data = (ROOT / 'production-postimages' / sha).read_bytes()
                self.assertEqual(sha, hashlib.sha256(data).hexdigest())
                doc = check_style_namespace(path, data)
                if path == SHIELDS:
                    matches = [element for element in doc.iter('Button') if
                               element.get(f'{{{ANDROID_NS}}}id') == '@+id/raws_global_shield_settings']
                    self.assertEqual(len(matches), 1)
                    self.assertEqual(matches[0].get('style'), '?android:attr/borderlessButtonStyle')
                checked.add(path)
        self.assertIn(SHIELDS, checked)

    def test_namespace_guard_rejects_another_android_prefix_too(self):
        good = (f'<Button xmlns:a="{ANDROID_NS}" '
                f'style="?android:attr/borderlessButtonStyle" a:layout_width="match_parent"/>')
        self.assertIsNotNone(check_style_namespace(SHIELDS, good))
        with self.assertRaisesRegex(ValueError, 'must use unqualified style'):
            check_style_namespace(SHIELDS, good.replace(' style=', ' a:style='))


if __name__ == '__main__':
    unittest.main()
