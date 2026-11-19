#!/usr/bin/env python3
"""Guard the one-off recovery from the unfinished #1416 Stage 1 checkpoint."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess

SCRIPTS = Path(__file__).resolve().parent
SOURCE_WORKFLOW = '6a283962-1ca0-413a-999a-cd56a7c3f3cd'
SOURCE_REVISION = '46e65867d84b8adfcba3de0cd6d6ad0e6862a5fe'
MANIFEST_SHA = '7a0e13f9920b3f814bcdedb657e74790567ad3f1a1ebe1bd89c25bb281ecf107'
ARCHIVE_BYTES = 35559388358
SOURCE_BYTES = 75221518662
MANIFEST_FILE = 'brave-workspace-checkpoint.manifest.json'


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


reference = load_script('resume-official-1394')
EXPECTED = {
    **reference.EXPECTED,
    'STAGE': '1', 'WORKFLOW_ID': SOURCE_WORKFLOW,
    'REFERENCE_SOURCE_REVISION': SOURCE_REVISION,
    'APK_VALIDATED': 'false', 'REFERENCE_READY': 'false',
}


def validate_checkpoint(root):
    manifest = root / MANIFEST_FILE
    if manifest.is_symlink() or reference.digest(manifest) != MANIFEST_SHA:
        raise ValueError('1416 Stage 1 manifest SHA256 mismatch')
    data = json.loads(manifest.read_text())
    if (data.get('schema_version') != 2
            or data.get('format') != 'independent-tar+zstd-shards'
            or data.get('workspace_root') != 'brave-work'
            or data.get('workers') != 8
            or len(data.get('shards', [])) != 8
            or data.get('archive_bytes') != ARCHIVE_BYTES
            or data.get('source_bytes') != SOURCE_BYTES):
        raise ValueError('1416 Stage 1 manifest format, size or shard count mismatch')
    if any(
            data['checkpoint_manifest'].get(key) != value for key, value in EXPECTED.items()):
        raise ValueError('1416 Stage 1 manifest provenance or readiness mismatch')
    return data


def read_flags(path):
    return dict(line.split('=', 1) for line in path.read_text().splitlines() if '=' in line)


def validate_unfinished(root):
    status_dir = root/'brave-work/.sandium'
    build = read_flags(status_dir/'build-stage-status.txt')
    apk = read_flags(status_dir/'apk-completion-status.txt')
    required = {
        'BUILD_EXIT_CODE': '124', 'BUILD_REASON': 'TIME_SLICE_COMPLETE',
        'BUILD_TIME_SLICE_EXPIRED': 'true', 'BUILD_COMMAND_SUCCEEDED': 'false',
        'BUILD_SLICE_INCOMPLETE': 'true', 'BUILD_HANDOFF_ALLOWED': 'true',
        'STAGE_BUILD_BUDGET_SECONDS': '720',
    }
    if (any(build.get(key) != value for key, value in required.items())
            or apk.get('BUILD_FINISHED') != 'false'):
        raise ValueError('1416 Stage 1 is not the expected unfinished attested time slice')


def postrestore(root, data):
    subprocess.run(['bash', str(SCRIPTS/'verify-brave-reference.sh'), '--handoff',
                    '2', SOURCE_WORKFLOW, SOURCE_REVISION], check=True,
                   env={**os.environ, 'CIRCLE_WORKING_DIRECTORY': str(root)})
    workspace = root/'brave-work'
    if reference.digest(workspace/'.sandium/checkpoint-manifest.txt') != data['checkpoint_manifest_sha256']:
        raise ValueError('extracted checkpoint provenance does not match hashed manifest')
    reference.validate_gn_files(workspace/'src/out/android_Release_arm64')
    validate_unfinished(root)


def retire_outputs(root):
    validate_unfinished(root)
    # Retire only the exact product output/markers, not intermediates or state.
    (root/reference.APK_PATH).unlink(missing_ok=True)
    status_dir = root/'brave-work/.sandium'
    for name in ('apk-completion-status.txt', 'restored-apk-valid', 'build-stage-status.txt'):
        (status_dir/name).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('preverify', 'postrestore', 'retire-seed-outputs'))
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    data = validate_checkpoint(root)
    if args.phase == 'preverify':
        load_script('sandium-checkpoint-shards').verify(root, zstd_test=False, workers=8)
    elif args.phase == 'postrestore':
        postrestore(root, data)
    else:
        retire_outputs(root)
    print('OFFICIAL_1416_STAGE_1_RESUME=PASS phase=' + args.phase)


if __name__ == '__main__':
    main()
