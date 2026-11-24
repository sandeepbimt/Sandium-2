#!/usr/bin/env python3
"""Count scriptlet-shaped text, not runtime effects, from verified snapshots."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / 'production-restore-recipe.json'
ADS_ROOT = {
    'sha256': '1e6da6ccc448b68ee8649393790c901a36f1ffe1fb1f16391d7b2177c7e8d728',
    'git_blob': 'c98d54230833c1b5a4aecddc1316564027cc1fc0',
}
ADS_EXPANDED = {
    'sha256': 'da9ed5748dd64c8b1d518c2cc98426fab21ffca0ae526a6c6c61ebd76479051f',
    'git_blob': '2f942706a61cf3c02ce98039a6ee2d3918643191',
}
REVISION = 'a21816ca2ebafbc46cfe5191f2fccaeb5286fb2e'
RULE = re.compile(rb'^[^\r\n]*?(##|#@#)\+js\([ \t]*([A-Za-z0-9_.-]*)'
                  rb'(?=[ \t]*[,\)])[\w\W]*\)[ \t]*$')
ADGUARD = re.compile(rb"^[^\r\n]*?(#%#|#@%#)//scriptlet\([ \t]*['\"]"
                     rb"([A-Za-z0-9_.-]+)['\"][\w\W]*\)[ \t]*$")
ALIASES = {
    'remove-attr': 'ra', 'remove-class': 'rc', 'remove-node-text': 'rmnt',
    'abort-on-property-read': 'aopr', 'abort-current-script': 'acs',
    'set-constant': 'set', 'abort-on-property-write': 'aopw',
    'addEventListener-defuser': 'aeld',
    'prevent-setTimeout': 'nostif', 'prevent-window-open': 'nowoif',
    'replace-node-text': 'rpnt',
}
FACTORY = 'components/sandium_adblock/document_subresource_factory.cc'
POLICY = 'components/sandium_adblock/passive_scriptlet_policy.h'


def verified(path, identity):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != identity['sha256']:
        raise ValueError(f'Unverified source: {path.name}')
    blob_header = f'blob {len(data)}\0'.encode()
    if 'git_blob' in identity and hashlib.sha1(blob_header + data).hexdigest() != identity['git_blob']:
        raise ValueError(f'Mismatched Git blob: {path.name}')
    return data


def product(recipe, key):
    sha = recipe[key]['after_sha256']
    return verified(ROOT/'production-postimages'/sha, {'sha256': sha})


def count(data):
    lanes = {key: Counter() for key in ('positive', 'exception', 'adguard_positive',
                                       'adguard_exception')}
    remove_attr = Counter()
    other = 0
    for raw in data.split(b'\n'):
        line = raw.strip()
        if not line or line.startswith((b'!', b'[')):
            continue
        m = RULE.fullmatch(line)
        if m:
            token = m[2].decode()
            family = ALIASES.get(token, token)
            if m[1] == b'##' and not family:
                other += 1
                continue
            lane = 'positive' if m[1] == b'##' else 'exception'
            lanes[lane][family or '(blanket exception)'] += 1
            if lane == 'positive' and family == 'ra':
                # Heuristic census of the nearest reviewed action. Do not
                # record selectors, site scopes, or full invocation text.
                args = line[m.end(2):].lstrip()
                arg = args[1:].split(b',', 1)[0].strip().rstrip(b')').strip()
                if arg.startswith(b'data-'):
                    category = 'custom_html_metadata'
                elif arg.startswith(b'on'):
                    category = 'event_handler_attribute'
                elif arg in (b'href', b'target', b'href|target', b'srcdoc'):
                    category = 'link_or_frame_behavior'
                else:
                    category = 'other_dom_semantics'
                remove_attr[category] += 1
            continue
        m = ADGUARD.fullmatch(line)
        if m:
            lanes['adguard_positive' if m[1] == b'#%#' else 'adguard_exception'][
                m[2].decode()] += 1
        elif any(marker in line for marker in
                 (b'##+js', b'#@#+js', b'#%#//scriptlet', b'#@%#//scriptlet')):
            other += 1
    return {key: {'lines': sum(c.values()), 'families': len(c),
                  'by_family': dict(c.most_common())}
            for key, c in lanes.items()} | {
                'remove_attr_first_argument_categories': dict(remove_attr),
                'other_shaped_lines': other,
            }


def build(cwd, recipe):
    factory = product(recipe, FACTORY).decode()
    start = factory.index('using DATFileDataBuffer =')
    end = factory.index('\n}', factory.index('void PruneSandiumSubscription'))+2
    (cwd/'policy.h').write_bytes(product(recipe, POLICY))
    source = cwd/'audit.cc'
    source.write_text(r'''
#include <cstring>
#include <iostream>
#include <iterator>
#include <optional>
#include <span>
#include <string_view>
#include <vector>
#include "policy.h"
namespace base {
class VSpan {
 public:
  explicit VSpan(std::span<uint8_t> s) : s_(s) {}
  VSpan subspan(size_t at, size_t size) const {
    return VSpan(s_.subspan(at, size));
  }
  void copy_from(VSpan other) const {
    std::memmove(s_.data(), other.s_.data(), s_.size());
  }
 private:
  std::span<uint8_t> s_;
};
VSpan span(std::vector<uint8_t>& b) { return VSpan(b); }
}
''' + factory[start:end] + r'''
int main(int argc, char**) {
  DATFileDataBuffer bytes(std::istreambuf_iterator<char>(std::cin), {});
  PruneSandiumSubscription(bytes);
  if (argc > 1) {
    if (bytes.empty()) return 0;
    auto reviewed =
        sandium::adblock_native::passive_scriptlets::ReviewedSourceRules(
            {reinterpret_cast<const char*>(bytes.data()), bytes.size()});
    if (!reviewed) return 2;
    std::cout << *reviewed;
    return 0;
  }
  for (auto byte : bytes) std::cout.put(static_cast<char>(byte));
}
''')
    out = cwd/'audit'
    subprocess.run([shutil.which('c++') or 'c++', '-std=c++20', '-Wall',
                    '-Wextra', '-Werror', str(source), '-o', str(out)], check=True)
    return out


def audited(binary, data, live_slot):
    preprocessed = subprocess.check_output([binary], input=data)
    projection = None
    if live_slot:
        completed = subprocess.run([binary, '--reviewed'], input=data,
                                   stdout=subprocess.PIPE, check=False)
        if completed.returncode not in (0, 2):
            completed.check_returncode()
        projection = (None if completed.returncode else
                      count(completed.stdout)['positive']['lines'])
    return {'source_bytes': len(data), 'preprocessed_sha256':
            hashlib.sha256(preprocessed).hexdigest(),
            'raw': count(data), 'preprocessed': count(preprocessed),
            'slot0_syntax_projection_lines': projection}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ads-root', required=True, type=Path,
                   help='Network-catalog Ads root from the sealed archived uAssets pin')
    p.add_argument('--illustrative-expanded', type=Path,
                   help='Audit separately; includes are not installed/live')
    opts = p.parse_args()
    recipe = json.loads(RECIPE.read_bytes())['files']
    easy = product(recipe, 'chrome/browser/resources/raws/easylist.txt')
    ads = verified(opts.ads_root, ADS_ROOT)
    expanded = (verified(opts.illustrative_expanded, ADS_EXPANDED)
                if opts.illustrative_expanded else None)
    with tempfile.TemporaryDirectory() as d:
        exe = build(Path(d), recipe)
        result = {
            'sources': {
                'packaged_easylist': audited(exe, easy, False),
                'archived_slot0_ads_root': audited(exe, ads, True),
            },
            'ads_revision': REVISION,
            'live_other_catalog_slot_bodies_verified': 0,
            'live_other_catalog_slots_not_measured': 29,
            'production_phase': 'disabled by default; experimental DOMContentLoaded only',
        }
        if expanded is not None:
            report = audited(exe, expanded, False)
            result['sources']['not_installed_expanded_ads_counterfactual'] = report
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
