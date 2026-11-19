#!/usr/bin/env python3
"""Admit only the exact official 158 lint policy; carry no 156 exceptions.

This is preparation for target lint, NOT proof that target lint is clean.
The 156 inventory is historical evidence until final 158 composition is audited.
"""
import hashlib
import json
import subprocess
from pathlib import Path

BRAVE_PIN = 'bd6d26d1bced03c17a98baa86d2cd3425d543d1b'
CHROMIUM_PIN = '52bdd21723d5db0c9ab11716d38feac74828cf84'
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / '.circleci/features/lint-resources/migration-158'
FILES = {
    'chromium_src/chrome/android/expectations/lint-suppressions.xml': 'lint-suppressions.xml',
    'chromium_src/build/android/gyp/lint.py': 'lint.py',
}


def verify(core):
    for repository, expected, name in [(core, BRAVE_PIN, 'Brave'),
                                       (core.parent, CHROMIUM_PIN, 'Chromium')]:
        actual = subprocess.check_output(['git', '-C', str(repository), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != expected:
            raise ValueError('Unexpected ' + name + ' revision for 158 lint')
    manifest = json.loads((DATA / 'policy.json').read_text())
    if (manifest['brave_pin'], manifest['chromium_pin'], manifest['extra_exceptions']) != (BRAVE_PIN, CHROMIUM_PIN, []):
        raise ValueError('Unreviewed target lint policy')
    for relative, fixture in FILES.items():
        expected = (DATA / fixture).read_bytes()
        if hashlib.sha256(expected).hexdigest() != manifest['files'][relative]['sha256']:
            raise ValueError('Target lint fixture modified')
        pinned = subprocess.check_output(['git', '-C', str(core), 'show', BRAVE_PIN + ':' + relative])
        if pinned != expected:
            raise ValueError('Target pinned lint implementation differs')
        if (core / relative).read_bytes() != expected:
            raise ValueError('Unreviewed live 158 lint rules/hook; restore exact target upstream, do not migrate 156 exceptions')
    print('SANDIUM_LINT_RESOURCES=UPSTREAM_158_VERIFIED extra_exceptions=0 lint_clean=UNVERIFIED')
