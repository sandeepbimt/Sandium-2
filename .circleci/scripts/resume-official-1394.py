#!/usr/bin/env python3
"""Fail-closed continuation from the readback-verified official #1402 stage 2."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess

WORKFLOW = '07214cac-daf8-47f1-a9dd-b48d229e934f'
REVISION = 'af15f567826041b83fb9295b12b3aa0d7c4b74ad'
MANIFEST_SHA = 'd6f47ee140ae7ec0ef36448f767e2fd90b1370da4e9bdae8673bd3fd93f47749'
APK_SHA = 'db8a86a10c317a5c2fc806cd15ff01d2d23fe1f906c1648bf5e0c6a6e3cc09a9'
ARCHIVE_BYTES = 35755833859
APK_BYTES = 365446122
APK_PATH = 'brave-work/src/out/android_Release_arm64/apks/BraveMonoarm64.apk'
EXPECTED = {
    'STAGE': '2', 'WORKFLOW_ID': WORKFLOW, 'REFERENCE_SOURCE_REVISION': REVISION,
    'CHECKPOINT_VALID': 'true', 'REFERENCE_MODE': 'reference',
    'CHROMIUM_SHA': 'd331de35ca8ab1358c7a17e4bd41627d55eaef51',
    'BRAVE_CORE_TAG': 'v1.98.62', 'TARGET': 'android-arm64', 'BUILD_TYPE': 'Release',
    'APK_VALIDATED': 'true', 'REFERENCE_READY': 'true',
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
            raise ValueError(f'1402 provenance mismatch: {key} expected={value!r} actual={cp.get(key)!r}')
    if payload.get('workers') != 8 or len(payload.get('shards', [])) != 8:
        raise ValueError('expected exactly eight shards/workers')

def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_checkpoint(root):
    manifest = root/'brave-workspace-checkpoint.manifest.json'
    if digest(manifest) != MANIFEST_SHA:
        raise ValueError('1402 manifest SHA256 mismatch')
    data = json.loads(manifest.read_text())
    validate_manifest(data)
    if data.get('archive_bytes') != ARCHIVE_BYTES:
        raise ValueError('1402 archive size mismatch')


def validate_restored_apk(root):
    apk = root/APK_PATH
    if not apk.is_file() or apk.is_symlink() or apk.stat().st_size != APK_BYTES or digest(apk) != APK_SHA:
        raise ValueError('1402 restored APK size or SHA256 mismatch')
    return apk


def retire_seed_outputs(root):
    # This APK and its completion markers are evidence of the seed, not the
    # current revision. Leave graph, object files and archive provenance intact.
    apk = validate_restored_apk(root)
    for name in ('apk-completion-status.txt', 'restored-apk-valid'):
        (root/'brave-work/.sandium'/name).unlink(missing_ok=True)
    apk.unlink()
    print('OFFICIAL_1402_SEED_APK=RETIRED for fresh revision build')


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
    parser.add_argument('phase', choices=['preverify', 'postrestore', 'retire-seed-outputs'])
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    validate_checkpoint(root)
    if args.phase == 'preverify':
        path = Path(__file__).with_name('sandium-checkpoint-shards.py')
        spec = importlib.util.spec_from_file_location('shards', path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        module.verify(root, zstd_test=False, workers=8)
    elif args.phase == 'postrestore':
        subprocess.run(['bash', str(Path(__file__).with_name('verify-brave-reference.sh')),
                        '--handoff', '3', WORKFLOW, REVISION], check=True,
                       env={**os.environ, 'CIRCLE_WORKING_DIRECTORY': str(root)})
        validate_gn_files(root/'brave-work/src/out/android_Release_arm64')
        validate_restored_apk(root)
    else:
        retire_seed_outputs(root)
    print('OFFICIAL_1402_RESUME=PASS phase='+args.phase)

if __name__ == '__main__':
    main()
