#!/usr/bin/env python3
"""Experimental renderer transport; deliberately NOT wired into CI.

Chromium d331de35ca8ab1358c7a17e4bd41627d55eaef51 only. Requires matching
Java JNI method from dark-pages integration. See README before enabling.
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

def apply(root):
    staged = {}
    for patch in json.loads((HERE / 'patches.json').read_text()):
        path = root / patch['path']
        text = staged.get(path, path.read_text())
        # Chromium158 renamed the non-null style accessor; retain upstream spelling.
        if patch['path'] == 'third_party/blink/renderer/core/frame/local_frame_view.cc':
            old158 = patch['old'].replace('StyleRef().ColorSchemeForced()', 'Style().ColorSchemeForced()')
            new158 = patch['new'].replace('StyleRef().ColorSchemeForced()', 'Style().ColorSchemeForced()')
            if old158 in text or new158 in text:
                patch = dict(patch, old=old158, new=new158)
        if text.count(patch['new']) == patch['count']:
            continue
        if text.count(patch['old']) != patch['count']:
            raise ValueError('Pinned renderer anchor mismatch: ' + patch['path'])
        staged[path] = text.replace(patch['old'], patch['new'])
    # Validate all anchors before touching any input.
    for path, text in staged.items():
        path.write_text(text)
    return len(staged)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source_root', type=Path)
    print(apply(parser.parse_args().source_root))
