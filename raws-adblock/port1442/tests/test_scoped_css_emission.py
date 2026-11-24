"""Compile the exact restored CSS emitter, not a parallel parser fixture."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ADBLOCK = Path(__file__).resolve().parents[2]
IMAGES = ADBLOCK / 'production-postimages'
LEGACY = 'b96338066556601c066c83fa9d9c5baed131d343f9a4620403ba7c3fb87d58f2'


def image(digest):
    data = (IMAGES / digest).read_bytes()
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Postimage digest mismatch')
    return data


class ScopedCssEmission(unittest.TestCase):
    def test_exact_selector_emission(self):
        cxx = shutil.which('g++') or shutil.which('clang++')
        self.assertIsNotNone(cxx, 'A host C++20 compiler is required')
        recipe = json.loads((ADBLOCK / 'production-restore-recipe.json').read_bytes())['files']
        owner = recipe['components/sandium_adblock/style.h']
        easylist = image(recipe['chrome/browser/resources/raws/easylist.txt']['after_sha256'])
        prefix = 'yahoo.com##div[style="height:'
        # Derive the four selectors from the actual packaged list. Their host
        # scope comes from Rust; these tests exercise only CSS output.
        selectors = [s.split('##', 1)[1] for s in easylist.decode().splitlines()
                     if s.startswith(prefix)]
        self.assertEqual(4, len(selectors))
        source = r'''
#include "style.h"
#include <cassert>
using sandium::port1442::HideStyles;

template <typename Range>
void TestPackaged(const Range& selected) {
  for (auto* value : selected) {
    const std::string selector(value);
#ifdef LEGACY
    assert(HideStyles({selector}, {}).empty());
#else
    assert(HideStyles({selector}, {}) == selector + " { display:none !important; }\n");
    assert(HideStyles({selector}, {selector}).empty());
#endif
  }
}

int main() {
  const char* actual[] = {ACTUAL};
  TestPackaged(actual);
  const char* same[] = {"#sda-LREC", ".btm-sda", "div[id^=\"sda-\"]",
                        ".outer:has(.slot)", "span:lang(\"en\")",
                        ".ordinary"};
  for (auto* raw : same) {
    const std::string s(raw);
    assert(HideStyles({s}, {}) == s + " { display:none !important; }\n");
  }

#ifndef LEGACY
  const char* allowed[] = {
      R"CSS(div:has(>[aria-hidden=false][data-test='left;right']))CSS",
      R"CSS(div[style *= 'height: 250px; width: 970px;' i])CSS",
      R"CSS([data-attr="literal['];()]"] .slot)CSS",
      R"CSS([data-a][data-b^="x;y"],.other)CSS"
  };
  for (auto* raw : allowed) {
    const std::string s(raw);
    assert(HideStyles({s}, {}) == s + " { display:none !important; }\n");
  }

  const std::string denied[] = {
      R"CSS(.slot";")CSS", R"CSS(.slot:lang("a;b"))CSS",
      R"CSS(.slot:is("[style='x;y']"))CSS",
      R"CSS([style="left;right])CSS", R"CSS([style="left;right")CSS",
      R"CSS([style="x;y"]])CSS", R"CSS(["x;y"])CSS",
      R"CSS([--="x;y"]oops;)CSS", R"CSS([1illegal="x;y"])CSS",
      R"CSS([-="x;y"])CSS", R"CSS([style"x;y"])CSS",
      R"CSS([style=x;y])CSS", R"CSS([style="x;y"ii])CSS",
      R"CSS([style="x;y" i s])CSS",
      R"CSS([style="x;y"];)CSS", R"CSS(;[style="x;y"])CSS",
      R"CSS(:has([style="x;y"])CSS", R"CSS([style="x;y"]))CSS",
      R"CSS([style="x;y"][data-z=z;)CSS",
      R"CSS([style="x;y}"])CSS", R"CSS([style="x;y{"])CSS",
      R"CSS([style="x;y@import"])CSS", R"CSS([style="x;\y"])CSS",
      R"CSS([style="x;/*y"])CSS", "[style=\"x;\ry\"]",
      "[style=\"x;\ny\"]", "[style=\"x;\fy\"]", "[style=\"x;\x7f\"]",
      std::string("[style=\"x;\0y\"]", 15)
  };
  for (const auto& s : denied) {
    assert(HideStyles({s}, {}).empty());
    assert(HideStyles({s, ".ordinary"}, {}) ==
           ".ordinary { display:none !important; }\n");
  }
#endif
}
'''
        materialized = source.replace('ACTUAL', ', '.join(json.dumps(s) for s in selectors))
        with tempfile.TemporaryDirectory() as tmp:
            stem = Path(tmp)
            (stem / 'case.cc').write_text(materialized)
            for legacy in (True, False):
                with self.subTest(legacy=legacy):
                    (stem / 'style.h').write_bytes(image(LEGACY if legacy else owner['after_sha256']))
                    flags = ['-DLEGACY'] if legacy else []
                    subprocess.run([cxx, '-std=c++20', '-Wall', '-Wextra', '-Werror',
                                    '-Wconversion', '-pedantic', *flags,
                                    str(stem / 'case.cc'), '-o', str(stem / 'case')],
                                   check=True, timeout=60)
                    subprocess.run([str(stem / 'case')], check=True, timeout=10)


if __name__ == '__main__':
    unittest.main()
