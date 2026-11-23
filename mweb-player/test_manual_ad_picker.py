"""Compile the actual manual save grammar and run locator logic on a model DOM."""
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
import manual_ad_picker as ad

ROOT = Path(__file__).resolve().parents[1]


class ManualAdPicker(unittest.TestCase):
    def output(self, path):
        sha = ad.OWNERS[path]
        data = (ROOT / 'raws-adblock/production-postimages' / sha).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), sha)
        return ad.transform(path, data).decode()

    def test_actual_browser_policy_and_whole_sheet_budget(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p/'policy.h').write_text(self.output(ad.POLICY))
            (p/'test.cc').write_text(r'''
#include <cassert>
#include <vector>
#include "policy.h"
using namespace sandium::adblock_native;
int main() {
  for (auto good : {"#subscribe", "button.old-save", ":root",
       ":root > body:nth-child(2) > button:nth-child(3) > span:nth-child(1)",
       "#nav > *:nth-child(3)", "#nav > video:nth-child(1000000)"}) {
    assert(IsSafePickedSelector(good));
  }
  for (auto bad : {"#nav > *:nth-child(0)", "#nav > *:nth-child(01)",
       "#nav > *:nth-child(1000001)", ":root > html:nth-child(n+1)",
       "#nav > *:nth-child(2),body", "body{} #nav", "#nav > ",
       ":root > *:nth-child(1):has(input)", ":root > *:nth-child()",
       "#nav > *:nth-child(1) > *:nth-child(2){}", ":root > x:nth-child("}) {
    assert(!IsSafePickedSelector(bad));
  }
  std::string deep = ":root";
  for (int a = 0; a < 126; ++a) deep += " > custom-tag-57:nth-child(7777)";
  assert(IsSafePickedSelector(deep));
  std::vector<std::string> rules(32, deep);
  auto css = BuildPickedSelectorStyles(rules);
  assert(!css.empty() && css.size() <= 132096);
}
''')
            subprocess.run(['c++','-std=c++20','test.cc','-o','picker-test'],cwd=p,check=True)
            subprocess.run([str(p/'picker-test')],cwd=p,check=True)
        renderer = self.output(ad.RENDERER)
        self.assertIn('selector->size() > 4096', renderer)
        self.assertIn('selector->size() <= 4096', renderer)
        self.assertIn('css.size() > 132096', renderer)

    def test_locator_exact_node_no_kind_checks_parent_is_deliberate(self):
        script = self.output(ad.PICKER)
        self.assertNotIn('element.closest(excludeTree)', script)
        self.assertNotIn('match.querySelector(embedded)', script)
        self.assertIn('selected === lastHit && picked?.node?.parentElement', script)
        a = script.index('  const selectorOf = element =>')
        b = script.index('  const candidateAt = node =>',a)
        js = '''
const assert = require('node:assert/strict');
const lookup = new Map();
const document = {querySelectorAll: s => lookup.get(s) || []};
const identifier = /^[A-Za-z_][A-Za-z_0-9-]{0,63}$/;
const safeTag = /^[a-z][a-z0-9-]{0,30}$/;
const maxSelectorBytes = 4096;
const make = (localName, parentElement, id='', previousElementSibling=null) =>
    ({localName,parentElement,id,previousElementSibling,isConnected:true,getRootNode:()=>document});
const root=make('html',null);
const body=make('body',root);
const wrapper=make('nav',body,'header');
const button=make('button',wrapper);
const text=make('span',button);
const input=make('input',wrapper,'',button);
lookup.set('#header',[wrapper]);
''' + script[a:b] + '''
for (const [node,path] of [
  [text,'#header > button:nth-child(1) > span:nth-child(1)'],
  [button,'#header > button:nth-child(1)'],
  [input,'#header > input:nth-child(2)'],
  [root,':root'],
  [make('iframe',button),'#header > button:nth-child(1) > iframe:nth-child(1)'],
  [make('video',body),':root > body:nth-child(1) > video:nth-child(1)']]) {
  lookup.set(path,[node]);
  assert.equal(selectorOf(node),path);
  assert.equal(previewMatches(node,path)?.[0],node);
  lookup.set(path,[button, text]);
  assert.equal(previewMatches(node,path),null);
}
'''
        subprocess.run(['node','-e',js],check=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
