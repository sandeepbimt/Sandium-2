#!/usr/bin/env python3
"""Honest diagnostic result. Never a build/checkpoint completion receipt."""
import argparse
import json
import os
from pathlib import Path

REPORTS = ('removal-native.json', 'removal-low-six.json', 'removal-leo.json')


def write_result(root, success=False, env=None):
    env = os.environ if env is None else env
    out = Path(root) / 'brave-apk'
    out.mkdir(exist_ok=True)
    identity = {k: env.get(k, '') for k in ('CIRCLE_SHA1', 'CIRCLE_PIPELINE_ID', 'CIRCLE_BUILD_NUM')}
    if not identity['CIRCLE_SHA1'] or not identity['CIRCLE_BUILD_NUM']:
        raise ValueError('Missing precheck run identity')
    observed = {}
    for name in REPORTS:
        p = out / name
        try:
            observed[name] = json.loads(p.read_text()).get('status', 'UNKNOWN')
        except (OSError, ValueError, AttributeError):
            observed[name] = 'MISSING_OR_INVALID'
    marker = out / '.graph-precheck-passed.json'
    if success:
        if not all(value == 'PASS' for value in observed.values()):
            raise ValueError('All generated graph audits must pass')
        marker.write_text(json.dumps(identity, sort_keys=True) + '\n')
    try:
        complete = json.loads(marker.read_text()) == identity and all(x == 'PASS' for x in observed.values())
    except (OSError, ValueError):
        complete = False
    try:
        build_status=json.loads((out/'build-precheck/build-precheck.json').read_text()).get('status','UNKNOWN')
    except (OSError, ValueError, AttributeError):
        build_status='NOT_RUN'
    result = {'identity': identity, 'status': 'PASS_GRAPH_ONLY' if complete else 'FAILED_OR_INCOMPLETE',
              'scope': 'Pinned source overlays, actual GN generation, native dependency/source audits, and graph configuration only',
              'audits': observed, 'selected_target_compile_status': build_status,
              'compiled': build_status == 'PASS_SELECTED_TARGETS', 'full_build_verified': False, 'apk_created': False, 'apk_verified': False,
              'runtime_verified': False, 'checkpoint_published': False,
              'limitations': ['No complete C++/Java/JNI compilation or final link proof', 'No packaging, installation or runtime proof',
                              'Cold precheck still restores full accepted base and deltas; no warm speed claim']}
    (out / 'graph-precheck.json').write_text(json.dumps(result, indent=2) + '\n')
    print('SANDIUM_GRAPH_PRECHECK=' + result['status'])
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--success', action='store_true')
    args = parser.parse_args()
    write_result(os.environ['CIRCLE_WORKING_DIRECTORY'], args.success)
