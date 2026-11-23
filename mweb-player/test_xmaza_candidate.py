"""Host check of the exact proposal through the #1514 CSS emitter."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from xmaza_candidate import POSTIMAGES, RECIPE, RULE, SELECTOR, candidate


class CosmeticCandidate(unittest.TestCase):
    def test_exact_delta_and_scope(self):
        policy = candidate().decode()
        rules = [line for line in policy.splitlines() if '.happy-under-player-mobile' in line]
        self.assertEqual(rules, [RULE])
        self.assertTrue(SELECTOR.endswith(':not(:has(video,audio,iframe,form,[role="dialog"]))'))
        self.assertNotIn('Back to top', policy)

    def test_production_css_emitter_and_exact_exception(self):
        files = json.loads(RECIPE.read_bytes())['files']
        digest = files['components/sandium_adblock/style.h']['after_sha256']
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'policy.h').write_bytes(candidate())
            (root / 'style.h').write_bytes((POSTIMAGES / digest).read_bytes())
            (root / 'test.cc').write_text(r'''
#include <cassert>
#include "policy.h"
#include "style.h"
int main() {
  std::string_view rules(sandium::port1442::kPlayerIncidentRules);
  constexpr std::string_view start = "\nxmaza.tv##";
  auto p = rules.find(start);
  assert(p != rules.npos);
  rules.remove_prefix(p + start.size());
  std::string s(rules.substr(0, rules.find('\n')));
  auto css = sandium::port1442::HideStyles({s}, {});
  assert(css == s + " { display:none !important; }\n");
  assert(sandium::port1442::HideStyles({s}, {s}).empty());
}
''')
            subprocess.run(['g++','-std=c++20',str(root/'test.cc'),'-o',str(root/'test')],
                           check=True, timeout=30, cwd=root)
            subprocess.run([str(root/'test')], check=True, timeout=10, cwd=root)


if __name__ == '__main__':
    unittest.main(verbosity=2)
