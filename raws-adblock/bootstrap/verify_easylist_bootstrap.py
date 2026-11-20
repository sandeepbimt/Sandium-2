#!/usr/bin/env python3
"""Build-time validation of the exact reviewed offline EasyList asset; no downloads."""
from pathlib import Path
import argparse
import hashlib
import json
import re

MAX_BYTES = 4 * 1024 * 1024
PIN = '2d0f3968f88ded9441bfddf2284c3819d8de3018150fbd175afc49e2f116050a'
EXPECTED_FILENAME = 'easylist.txt'

def verified_asset(path, manifest_path):
    if path.name != EXPECTED_FILENAME or path.is_symlink():
        raise ValueError('Expected a regular easylist.txt asset')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    with path.open('rb') as f:
        asset = f.read(MAX_BYTES + 1)
    if (manifest.get('schema') != 1 or not 0 < len(asset) <= MAX_BYTES
            or len(asset) != manifest.get('size_bytes')
            or hashlib.sha256(asset).hexdigest() != PIN
            or manifest.get('sha256') != PIN):
        raise ValueError('EasyList asset bytes differ from the reviewed snapshot')
    rules = asset.decode('utf-8', errors='strict')
    if '\x00' in rules or '!#include' in rules or '%include ' in rules:
        raise ValueError('Rules asset contains forbidden control or include directives')
    prefix = rules.splitlines()[:16]
    if (prefix[0] != '[Adblock Plus 2.0]'
            or '! Title: EasyList' not in prefix
            or '! Version: ' + manifest['version'] not in prefix
            or '! Commit: ' + manifest['source_commit'] not in prefix
            or '! Licence: https://easylist.to/pages/licence.html' not in prefix):
        raise ValueError('Rules header differs from review')
    sections = re.findall(r'^! \*\*\* easylist:(.+) \*\*\*$', rules, re.M)
    if not sections or sections != manifest.get('sections'):
        raise ValueError('Source section inventory differs from review')
    return asset

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('asset', type=Path)
    parser.add_argument('manifest', type=Path)
    args = parser.parse_args()
    try:
        print('EasyList snapshot verified:',len(verified_asset(args.asset,args.manifest)), 'bytes')
    except (OSError, ValueError, KeyError) as exc:
        raise SystemExit(str(exc))
