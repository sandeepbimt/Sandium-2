#!/usr/bin/env python3
"""Run real GN generation and every independent removal audit; no compilation."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def commands(root):
    root = Path(root)
    src = root / 'brave-work/src'; core = src / 'brave'; out = src / 'out/android_Release_arm64'
    scripts = root / '.circleci/scripts'; reports = root / 'brave-apk'
    prefix = [sys.executable]
    preparation = [
        prefix + [str(scripts/'test-sandium-removal-composition.py'), '--source', str(core), '--gn', str(src/'buildtools/linux64/gn')],
        prefix + [str(scripts/'sandium-removal-recipe.py'), '--core', str(core), '--src', str(src), '--out', str(out), '--phase', 'apply'],
    ]
    audits = [
        prefix + [str(scripts/'audit-sandium-removal-graph.py'), '--src', str(src), '--out', str(out), '--report', str(reports/'removal-native.json')],
        prefix + [str(scripts/'audit-sandium-low-coupling.py'), '--src', str(src), '--out', str(out), '--report', str(reports/'removal-low-six.json')],
        prefix + [str(scripts/'audit-sandium-leo-removal.py'), '--core', str(core), '--deps-file', str(reports/'removal-native.deps.txt'), '--report', str(reports/'removal-leo.json')],
    ]
    return preparation, audits


def execute(root, run=subprocess.run, audits_only=False):
    preparation, audits = commands(root)
    # A failed generation has no current valid graph, so never inspect stale output.
    for command in ([] if audits_only else preparation):
        run(command, check=True)
    failures = []
    for command in audits:
        result = run(command, check=False)
        if result.returncode:
            failures.append(Path(command[1]).name)
    if failures:
        raise RuntimeError('Graph precheck failed: ' + ', '.join(failures))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--audits-only', action='store_true')
    args = parser.parse_args()
    execute(os.environ['CIRCLE_WORKING_DIRECTORY'], audits_only=args.audits_only)
