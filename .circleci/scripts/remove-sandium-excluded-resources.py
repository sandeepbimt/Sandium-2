#!/usr/bin/env python3
"""Remove exact, reviewed resources excluded from final GN lists.

Chromium prepare_resources checks physical directory membership; merely deleting
GN entries leaves illegal undeclared resources. All paths are reset from the pin
before recipe replay. No glob deletion and no resource checker bypass.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

MANIFEST = Path(__file__).with_name('sandium-excluded-resources.json')


def apply(core, entries):
    core = Path(core).resolve()
    plans = []
    seen = set()
    for entry in entries:
        relative = entry['path']
        path = PurePosixPath(relative)
        if (relative in seen or path.is_absolute() or '..' in path.parts or
                not any(x in relative for x in ('/java/res/', '/java/brave-res/'))):
            raise RuntimeError('Invalid or duplicate resource path: ' + relative)
        seen.add(relative)
        p = core / relative
        # Refuse symlink traversal, including absent resource paths.
        for parent in (p, *p.parents):
            if parent == core:
                break
            if parent.is_symlink():
                raise RuntimeError('Symlink in excluded resource path: ' + relative)
        gn = core / entry['gn']
        owner_relative = p.relative_to(gn.parent).as_posix()
        quoted = re.findall(r'"([^"\n]+)"', gn.read_text())
        if owner_relative in quoted or '//brave/' + relative in quoted:
            raise RuntimeError('Resource still declared in owning GN: ' + relative)
        if not p.exists():
            continue  # An already-completed same recipe replay.
        if not p.is_file():
            raise RuntimeError('Not a regular resource: ' + relative)
        allowed = entry.get('allowed_sha256', [entry['sha256']])
        if hashlib.sha256(p.read_bytes()).hexdigest() not in allowed:
            raise RuntimeError('Excluded resource content drift: ' + relative)
        plans.append(p)
    # All drift/ownership checks finish before any source is removed.
    for p in plans:
        p.unlink()
    print('SANDIUM_EXCLUDED_RESOURCES_REMOVED', len(plans), 'reviewed', len(entries))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--core', required=True, type=Path)
    args = parser.parse_args()
    apply(args.core, json.loads(MANIFEST.read_text()))
