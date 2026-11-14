#!/usr/bin/env python3
"""Publish final removal-modified Android resource overrides to compiled paths.

Pinned Brave branding.js copies these during prepare, before final removal surgery.
Java overrides are compiled directly from brave/ and must not be copied over Chromium.
Do not rerun branding: that would overwrite other Sandium Chromium customizations.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAPPINGS = {
    'android/java/res/layout/new_tab_page_layout.xml':
        'chrome/android/java/res/layout/new_tab_page_layout.xml',
    'android/java/res/layout/new_tab_page_incognito.xml':
        'chrome/android/java/res/layout/new_tab_page_incognito.xml',
}
# Resource roots copied by pinned build/commands/lib/branding.js. New removal
# inputs in these roots require a reviewed explicit mapping, not a broad copy.
COPIED_ROOTS = (
    'android/java/res/',
    'browser/download/internal/android/java/res/',
    'app/theme/brave/android/',
)
FORBIDDEN = (
    b'@drawable/product_vpn_layer_list', b'@drawable/ic_news_settings',
    b'@layout/brave_news_load_new_content',
)


def contained(root, relative):
    root = root.resolve()
    target = root / relative
    # Reject symlink destinations/parents even when they point inside the root.
    for part in (target, *target.parents):
        if part == root:
            break
        if part.is_symlink():
            raise ValueError('Symlink in removal overlay path: ' + relative)
    if not target.resolve().is_relative_to(root):
        raise ValueError('Escaping removal overlay path: ' + relative)
    return target


def apply(core, src, manifest=None):
    manifest = manifest or json.loads((ROOT / '.circleci/features/removal-recipe.json').read_text())
    copied = {p for p in manifest['core_restore'] if p.startswith(COPIED_ROOTS)}
    if copied != set(MAPPINGS):
        raise ValueError('Review removal overlay mappings: ' + repr(sorted(copied ^ set(MAPPINGS))))
    pending = []
    for source, destination in MAPPINGS.items():
        data = contained(core, source).read_bytes()
        if any(reference in data for reference in FORBIDDEN):
            raise ValueError('Removed NTP component resource reference remains: ' + source)
        pending.append((contained(src, destination), data))
    for target, data in pending:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file() or target.read_bytes() != data:
            target.write_bytes(data)
        if target.read_bytes() != data:
            raise ValueError('Removal overlay publication mismatch: ' + str(target))
    print('SANDIUM_REMOVAL_RESOURCE_OVERLAYS=PASS files=' + str(len(pending)))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--core', type=Path, required=True)
    p.add_argument('--src', type=Path, required=True)
    a = p.parse_args()
    apply(a.core, a.src)
