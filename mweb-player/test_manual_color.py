"""Focused source and host behavioral checks on exact #1514 inputs."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import manual_color as edit

ROOT = Path(__file__).resolve().parents[1]


def section(text, begin, end):
    first = text.index(begin)
    return text[first:text.index(end, first + len(begin))]


class ManualColor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base, cls.out = {}, {}
        for owner, expected in edit.OWNERS.items():
            old = (ROOT / 'raws-adblock/production-postimages' / expected).read_bytes()
            if hashlib.sha256(old).hexdigest() != expected:
                raise ValueError(f'incorrect #1514 product owner: {owner}')
            cls.base[owner] = old.decode()
            cls.out[owner] = edit.transform(owner, old).decode()

    def test_native_eligibility_actual_extracted_body(self):
        cxx = shutil.which('clang++') or shutil.which('c++')
        self.assertIsNotNone(cxx, 'C++17 compiler required for eligibility smoke')
        eligible = section(self.out[edit.BLINK], 'bool SandiumElementColors::Eligible(',
                           'bool SandiumElementColors::CanCorrect(')
        with tempfile.TemporaryDirectory() as path:
            src = Path(path) / 'manual_color.cc'
            exe = Path(path) / 'manual_color'
            src.write_text('''
#include <cassert>
struct UrlType {
  bool http = true;
  bool ProtocolIsInHttpFamily() const { return http; }
};
struct Document {
  bool active = true, outer = true;
  UrlType url;
  bool IsInOutermostMainFrame() const { return outer; }
  bool IsActive() const { return active; }
  const UrlType& Url() const { return url; }
};
struct Element {
  const Document* doc;
  bool connected = true, shadow = false;
  const Document& GetDocument() const { return *doc; }
  bool isConnected() const { return connected; }
  bool IsInShadowTree() const { return shadow; }
};
struct SandiumElementColors {
  const Document* doc;
  const Document* GetSupplementable() const { return doc; }
  bool Eligible(const Element& element) const;
};
''' + eligible + '''
int main() {
  Document document, unrelated;
  SandiumElementColors picker{&document};
  Element target{&document};
  assert(picker.Eligible(target));
  target.doc = &unrelated;
  assert(!picker.Eligible(target));
  target.doc = &document;
  document.active = false;
  assert(!picker.Eligible(target));
  document.active = true;
  document.outer = false;
  assert(!picker.Eligible(target));
  document.outer = true;
  document.url.http = false;
  assert(!picker.Eligible(target));
  document.url.http = true;
  target.connected = false;
  assert(!picker.Eligible(target));
  target.connected = true;
  target.shadow = true;
  assert(!picker.Eligible(target));
  target.shadow = false;
  assert(picker.Eligible(target));
}
''')
            subprocess.run([cxx, '-std=c++17', '-Werror', '-Wall', '-Wextra',
                            str(src), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_color_consumers_and_dark_guards_identical(self):
        marker = 'bool SandiumElementColors::CanCorrect('
        self.assertEqual(self.base[edit.BLINK].split(marker)[1],
                         self.out[edit.BLINK].split(marker)[1])
        blink = self.out[edit.BLINK]
        for guard in ('!element.GetDocument().InForcedColorsMode() && Eligible(element)',
                      'settings->GetForceDarkModeEnabled()', 'builder.InForcedColorsMode()',
                      'property == 2 && !element.HasTagName(html_names::kImgTag)',
                      'if (!Eligible(element)) {'):
            self.assertIn(guard, blink)

    def test_exact_dom_hit_without_durable_tag_or_parent_substitution(self):
        out = self.out[edit.RENDERER]
        pick = section(out, '  panel.addEventListener(\'click\'', '  // Keep control input')
        self.assertIn('event.isTrusted', pick)
        self.assertIn('document.elementFromPoint(event.clientX, event.clientY)', pick)
        self.assertIn('!hit || !select(hit)', pick)
        self.assertNotIn('parentElement', pick)
        selection = section(out, 'bool RawSColorRenderer::OnDomSelection(',
                            'bool RawSColorRenderer::ValidVisitChoice(')
        self.assertIn('node.GetDocument() != *selected_document_ || !node.CanSandiumCorrectColor()', selection)
        self.assertNotIn('ElementTag(', selection)
        self.assertIn('visit_only_ = !candidate;', selection)
        self.assertIn('selected_ = node;', selection)
        self.assertEqual(out.split('bool RawSColorRenderer::ValidVisitChoice(')[1],
                         self.base[edit.RENDERER].split('bool RawSColorRenderer::ValidVisitChoice(')[1])

    def test_fail_closed_unexpected_anchors(self):
        for path in edit.OWNERS:
            with self.assertRaises(ValueError):
                edit.transform(path, b'// unrelated source')


if __name__ == '__main__':
    unittest.main(verbosity=2)
