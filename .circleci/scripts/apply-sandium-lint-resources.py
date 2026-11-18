#!/usr/bin/env python3
"""Exact reviewed resource exceptions through Brave's official lint hook.

Default is fail closed while inventory contains unresolved diagnostics. This does
not edit a lint baseline, disable an issue, delete resources, or alter GN gates.
"""
import argparse
import ast
import xml.etree.ElementTree as ET
import hashlib
import html
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / '.circleci/features/lint-resources'
TARGET = 'chromium_src/chrome/android/expectations/lint-suppressions.xml'
HOOK = 'chromium_src/build/android/gyp/lint.py'


def load():
    inventory = json.loads((DATA / 'inventory.json').read_text())
    rows = inventory['resources']
    if len(rows) != 328 or len({x['resource'] for x in rows}) != 328:
        raise ValueError('Resource inventory identity/count mismatch')
    for row in rows:
        if not re.fullmatch(r'R\.[a-z]+\.[A-Za-z0-9_]+', row['resource']):
            raise ValueError('Invalid exact resource ID')
        if row['approved'] and (not row['evidence'] or row['classification'] not in
                ('retained_upstream_removed_feature', 'verified_indirect_reference',
                 'retained_upstream_replaced_consumer', 'verified_static_live_reference')):
            raise ValueError('Unjustified resource exception')
        if row['classification'] == 'removed_obsolete_owned':
            proof = row.get('removal_evidence', {})
            source = proof.get('source_path', '')
            if not source or Path(source).is_absolute() or '..' in Path(source).parts:
                raise ValueError('Invalid removed resource source')
            data = (ROOT / source).read_bytes()
            if hashlib.sha256(data).hexdigest() != proof.get('sha256'):
                raise ValueError('Removed resource source changed; review required')
            resource_name = row['resource'].split('.')[-1]
            if re.search(r'name=["\']' + re.escape(resource_name) + r'["\']', data.decode()):
                raise ValueError('Removed resource declaration restored')
            if proof.get('source_kind') == 'python_palette':
                mappings = [n.value for n in ast.parse(data).body if isinstance(n, ast.Assign)
                            and any(isinstance(t, ast.Name) and t.id == proof['mapping'] for t in n.targets)]
                if len(mappings) != 1 or not isinstance(mappings[0], ast.Dict):
                    raise ValueError('Palette mapping changed')
                if resource_name in [k.value for k in mappings[0].keys if isinstance(k, ast.Constant)]:
                    raise ValueError('Removed palette entry restored')
                palette = (ROOT / proof['upstream_palette_fixture']).read_bytes()
                if hashlib.sha256(palette).hexdigest() != proof['upstream_palette_sha256']:
                    raise ValueError('Upstream palette evidence changed')
                if resource_name in {n.attrib.get('name') for n in ET.fromstring(palette)}:
                    raise ValueError('Cannot delete a real upstream palette override')
            if row['approved']:
                raise ValueError('Removed resource must never have an exclusion')
    recipe = (ROOT / '.circleci/features/removal-recipe.json').read_bytes()
    if hashlib.sha256(recipe).hexdigest() != inventory['provenance']['removal_recipe_sha256']:
        raise ValueError('Canonical removal recipe changed; review required')
    baseline = (DATA / 'fixtures/upstream-lint-suppressions.xml').read_bytes()
    if hashlib.sha256(baseline).hexdigest() != inventory['provenance']['upstream_suppressions_sha256']:
        raise ValueError('Upstream suppression fixture changed')
    return inventory, baseline


def expression(resource):
    # Lint config matches messages using backtick-delimited resource IDs.
    # Java Pattern understands these literal-dot escapes; no wildcard suffix.
    return '^The resource `' + resource.replace('.', r'\.') + '` appears to be unused$'


def render(inventory, baseline, reviewed_only=False):
    unresolved = [r for r in inventory['resources'] if not r['approved'] and r['classification'] != 'removed_obsolete_owned']
    if unresolved and not reviewed_only:
        raise ValueError(f'{len(unresolved)} unresolved resources; full integration blocked')
    text = baseline.decode()
    if text.count('</lint>') != 1:
        raise ValueError('Unexpected upstream lint document')
    lines = ['        <!-- Sandium exact reviewed resource inventory; CircleCI #1394. -->']
    for row in inventory['resources']:
        if row['approved']:
            lines.append('        <ignore regexp="' + html.escape(expression(row['resource']), quote=True) + '" />')
    # Extend the existing issue, avoiding duplicate-ID merge semantics in lint.
    pattern = r'(<issue id="UnusedResources">)(.*?)(    </issue>)'
    if len(re.findall(pattern, text, re.S)) != 1:
        raise ValueError('Expected one upstream UnusedResources rule')
    return re.sub(pattern, lambda match: match[1] + match[2] + '\n'.join(lines) + '\n' + match[3],
                  text, count=1, flags=re.S).encode()



def apply(core, reviewed_only=False):
    inventory, baseline = load()
    pin = inventory['provenance']['brave_pin']
    actual = subprocess.check_output(['git', '-C', str(core), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != pin:
        raise ValueError('Unexpected Brave revision')
    for relative, expected in [(TARGET, baseline),
            (HOOK, (DATA / 'fixtures/upstream-lint-override.py').read_bytes())]:
        pinned = subprocess.check_output(['git', '-C', str(core), 'show', pin + ':' + relative])
        if pinned != expected:
            raise ValueError('Unexpected pinned upstream lint implementation')
    if (core / HOOK).read_bytes() != (DATA / 'fixtures/upstream-lint-override.py').read_bytes():
        raise ValueError('Live Brave lint hook differs from reviewed upstream')
    result = render(inventory, baseline, reviewed_only)
    target = core / TARGET
    if target.read_bytes() not in (baseline, result):
        raise ValueError('Unreviewed live lint rules; refusing overwrite')
    target.write_bytes(result)
    print('SANDIUM_LINT_RESOURCES=APPLIED exact_reviewed_exclusions=320 owned_removals=8; all other diagnostics remain fatal')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', required=True, type=Path)
    parser.add_argument('--reviewed-only', action='store_true',
                        help='Apply only approved entries; does NOT claim complete lint remediation')
    args = parser.parse_args()
    apply(args.core, args.reviewed_only)
