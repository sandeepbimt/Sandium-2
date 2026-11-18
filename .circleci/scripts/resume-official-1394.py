#!/usr/bin/env python3
"""Fail-closed one-off continuation from the verified official #1394 stage 3."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess

WORKFLOW = '59a89c27-4187-414d-9f34-8cf6e4b31ebf'
REVISION = '68eb3032aed511ed5b49ac3a85464a16b9eb3d37'
EXPECTED = {
    'STAGE': '3', 'WORKFLOW_ID': WORKFLOW, 'REFERENCE_SOURCE_REVISION': REVISION,
    'CHECKPOINT_VALID': 'true', 'REFERENCE_MODE': 'reference',
    'CHROMIUM_SHA': 'd331de35ca8ab1358c7a17e4bd41627d55eaef51',
    'BRAVE_CORE_TAG': 'v1.98.62', 'TARGET': 'android-arm64', 'BUILD_TYPE': 'Release',
    'APK_VALIDATED': 'false', 'REFERENCE_READY': 'false',
}
GN = {
    'target_cpu': '"arm64"', 'is_debug': 'false', 'is_java_debug': 'false',
    'is_official_build': 'true', 'use_remoteexec': 'true', 'use_siso': 'true',
    'use_reclient': 'false', 'enable_android_secondary_abi': 'false',
    'enable_updater': 'false', 'enable_update_notifications': 'false',
    'android_channel': '"default"', 'brave_channel': '"development"',
    'chrome_public_manifest_package': '"com.brave.browser_default"',
}

def validate_manifest(payload):
    if payload.get('schema_version') != 2 or payload.get('format') != 'independent-tar+zstd-shards':
        raise ValueError('unsupported manifest format')
    cp = payload.get('checkpoint_manifest', {})
    for key, value in EXPECTED.items():
        if cp.get(key) != value:
            raise ValueError(f'1394 provenance mismatch: {key} expected={value!r} actual={cp.get(key)!r}')
    if payload.get('workers') != 8 or len(payload.get('shards', [])) != 8:
        raise ValueError('expected exactly eight shards/workers')

def validate_gn(text):
    for key, expected in GN.items():
        values = re.findall(r'^\s*'+re.escape(key)+r'\s*=\s*([^\n#]+)', text, re.M)
        if len(values) != 1 or values[0].strip() != expected:
            raise ValueError(f'official GN mismatch: {key} expected={expected} actual={values}')

def validate_gn_files(out):
    # Brave writes the effective generated values into an imported file, not
    # into its user-editable args.gn wrapper (build/commands/lib/util.js).
    generated = out/'args_generated.gni'
    wrapper = (out/'args.gn').read_text()
    import_line = 'import("//out/android_Release_arm64/args_generated.gni")'
    lines = [line.split('#', 1)[0].strip() for line in wrapper.splitlines()]
    lines = [line for line in lines if line]
    if lines.count(import_line) != 1:
        raise ValueError('expected one active exact generated GN import')
    validate_gn(generated.read_text())
    # Do not accept commented-out imports, other imports/control flow, or an
    # override that could change official identity after the generated import.
    for line in lines:
        if line == import_line:
            continue
        match = re.fullmatch(r'([a-zA-Z_][a-zA-Z_0-9]*)\s*=\s*(true|false|[0-9]+|"[^"\n]*")', line)
        if not match:
            raise ValueError('unsupported executable GN wrapper statement: '+line)
        key, value = match.groups()
        if key in GN and value != GN[key]:
            raise ValueError('conflicting GN wrapper override: '+key)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['preverify', 'postrestore'])
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    validate_manifest(json.loads((root/'brave-workspace-checkpoint.manifest.json').read_text()))
    if args.phase == 'preverify':
        path = Path(__file__).with_name('sandium-checkpoint-shards.py')
        spec = importlib.util.spec_from_file_location('shards', path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        module.verify(root, zstd_test=False, workers=8)
    else:
        subprocess.run(['bash', str(Path(__file__).with_name('verify-brave-reference.sh')),
                        '--handoff', '4', WORKFLOW, REVISION], check=True,
                       env={**os.environ, 'CIRCLE_WORKING_DIRECTORY': str(root)})
        validate_gn_files(root/'brave-work/src/out/android_Release_arm64')
    print('OFFICIAL_1394_RESUME=PASS phase='+args.phase)

if __name__ == '__main__':
    main()
