#!/usr/bin/env python3
"""Exact Full Mode-U source identity; never admits #1402 compiled state."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRAVE_SHA = 'bd6d26d1bced03c17a98baa86d2cd3425d543d1b'
CHROMIUM_SHA = '52bdd21723d5db0c9ab11716d38feac74828cf84'
PACKAGE_SHA256 = 'cc13a7370be5e1cbc2dd76c7b59d3b716fd719d9a424234aca51af08d930adb9'


def load(root=ROOT):
    p = json.loads((Path(root)/'docs/upgrades/1.100.58/candidate-profile.json').read_text())
    source = p['source']
    expected = dict(brave_tag='v1.100.58', core_sha=BRAVE_SHA,
                    chromium_version='158.0.8127.42', chromium_sha=CHROMIUM_SHA,
                    core_package_sha256=PACKAGE_SHA256)
    if p.get('schema') != 1 or any(source.get(k) != v for k, v in expected.items()):
        raise ValueError('Unreviewed upgrade source profile')
    if p['build'] != dict(is_official_build=True, target_cpu='arm64',
                          target='brave', artifact='BraveMonoarm64.apk',
                          universal_target_approved=False):
        raise ValueError('Unreviewed upgrade build profile')
    if p['rollback'].get('compiled_seed_compatible') is not False:
        raise ValueError('Old compiled seed cannot be upgraded in place')
    return p


def verify(core, src, root=ROOT):
    p = load(root)
    for directory, expected in ((core, BRAVE_SHA), (src, CHROMIUM_SHA)):
        actual = subprocess.check_output(['git', '-C', str(directory), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != expected:
            raise ValueError('Upgrade source pin mismatch: ' + str(directory))
    raw = (Path(core)/'package.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != PACKAGE_SHA256:
        raise ValueError('Upgrade upstream package identity mismatch')
    package = json.loads(raw)
    if package['version'] != '1.100.58' or package['config']['projects']['chrome']['tag'] != '158.0.8127.42':
        raise ValueError('Upgrade Brave/Chromium package pair mismatch')
    return dict(brave_sha=BRAVE_SHA, chromium_sha=CHROMIUM_SHA,
                profile_verified=True, compiled_seed_compatible=False,
                source_sync_verified=False, apk_verified=False)


if __name__ == '__main__':
    q = argparse.ArgumentParser(description=__doc__)
    q.add_argument('--core', type=Path, required=True)
    q.add_argument('--src', type=Path, required=True)
    q.add_argument('--root', type=Path, default=ROOT)
    args = q.parse_args()
    print(json.dumps(verify(args.core, args.src, args.root), sort_keys=True))
