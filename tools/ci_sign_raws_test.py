#!/usr/bin/env python3
"""Promote a CircleCI workspace input in the isolated RawS test signer."""
import argparse
import base64
import binascii
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from raws_release_identity import APPLICATION_ID, expected_fingerprint, sign_release_locally

SIGNING_SECRETS = (
    'RAWS_TEST_KEYSTORE_B64', 'RAWS_KEYSTORE_PASSWORD', 'RAWS_KEY_PASSWORD',
    'RAWS_TEST_SIGNER_PIN_SHA256',
)
ALIAS = 'raws-test'
HANDOFF = '.raws-signing-input'
ROUTE_BRANCH = 'raw-sandium/official158'
APK_NAME = 'RawSandium-Test-arm64.apk'
HEX64 = re.compile(r'[0-9a-f]{64}')
HEX40 = re.compile(r'[0-9a-f]{40}')
UUID = re.compile(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}')
EVIDENCE = (
    'apk_produced', 'apk_verified', 'apk_zip_verified', 'apk_signature_verified',
    'raws_engine_apk_graph_verified', 'raws_ui_apk_graph_verified',
)


def sha256(path):
    with path.open('rb') as obj:
        return hashlib.file_digest(obj, 'sha256').hexdigest()


def run_identity(root):
    if os.environ.get('CIRCLE_BRANCH') != ROUTE_BRANCH:
        raise ValueError('RawS test signing is not enabled on this branch')
    workflow = os.environ.get('CIRCLE_WORKFLOW_ID', '')
    checkout = subprocess.check_output(
        ['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True, timeout=10,
    ).strip()
    declared_commit = os.environ.get('CIRCLE_SHA1')
    if (not UUID.fullmatch(workflow) or not HEX40.fullmatch(checkout)
            or (declared_commit is not None and declared_commit != checkout)):
        raise ValueError('Missing or inconsistent CircleCI workflow and checkout identity')
    return checkout, workflow


def build_receipt(root, state, apk):
    checkout, workflow = run_identity(root)
    digest = state.get('apk_sha256', '')
    smoke_cases = state.get('raws_engine_smoke', {}).get('cases', [])
    if (state.get('stage') != 1 or state.get('status') != 'done'
            or state.get('apk_package') != APPLICATION_ID
            or state.get('apk_abis') != ['arm64-v8a']
            or not all(state.get(k) is True for k in EVIDENCE)
            or not HEX64.fullmatch(state.get('feature_recipe_sha256') or '')
            or len(smoke_cases) != 14 or 'incident1471-player-rules' not in smoke_cases
            or not apk.is_file() or apk.is_symlink()
            or not HEX64.fullmatch(digest) or sha256(apk) != digest):
        raise ValueError('Unverified candidate cannot enter the RawS signing workspace')
    proof = {
        'schema': 1, 'commit': checkout, 'workflow': workflow,
        'input_sha256': digest, 'recipe_sha256': state['feature_recipe_sha256'],
        'package': APPLICATION_ID, 'device_tested': False,
    }
    from raws_codec_ci import mode as codec_mode, validate_proof
    if codec_mode():
        validate_proof(root, state.get('codec_trial'))
        if smoke_cases != state['codec_trial']['native_smoke_cases']:
            raise ValueError('Combined codec proof does not match actual native smoke receipt')
        proof['codec_trial'] = state['codec_trial']
    elif 'codec_trial' in state:
        raise ValueError('Codec proof cannot enter ordinary test signing')
    return proof


def stage_private_input(root, state, apk):
    proof = build_receipt(root, state, apk)
    target = root / HANDOFF
    target.mkdir(mode=0o700, exist_ok=False)
    candidate = target / 'candidate.apk'
    shutil.copyfile(apk, candidate)
    if sha256(candidate) != proof['input_sha256']:
        raise ValueError('RawS signing handoff copy did not verify')
    (target / 'receipt.json').write_text(json.dumps(proof, sort_keys=True) + '\n')
    apk.unlink()


def input_receipt(root, source):
    checkout, workflow = run_identity(root)
    if (source.is_symlink() or not source.is_dir()
            or {p.name for p in source.iterdir()} != {'candidate.apk', 'receipt.json'}):
        raise ValueError('Unexpected files in RawS private signing handoff')
    apk, receipt_file = source / 'candidate.apk', source / 'receipt.json'
    if any(p.is_symlink() or not p.is_file() for p in (apk, receipt_file)):
        raise ValueError('Unexpected paths in RawS private signing handoff')
    if receipt_file.stat().st_size > 4096:
        raise ValueError('Oversize RawS signing receipt')
    proof = json.loads(receipt_file.read_bytes())
    from raws_codec_ci import mode as codec_mode, validate_proof, verify_checkout
    trial = codec_mode()
    fields = {'schema', 'commit', 'workflow', 'input_sha256', 'recipe_sha256', 'package', 'device_tested'}
    if trial:
        fields.add('codec_trial')
    if (not isinstance(proof, dict)
            or set(proof) != fields
            or proof['schema'] != 1 or proof['commit'] != checkout
            or proof['workflow'] != workflow or proof['package'] != APPLICATION_ID
            or proof['device_tested'] is not False
            or not HEX64.fullmatch(proof['input_sha256'] or '')
            or not HEX64.fullmatch(proof['recipe_sha256'] or '')
            or proof['input_sha256'] != sha256(apk)):
        raise ValueError('RawS private signing receipt does not match the exact candidate')
    manifest = root / 'raws-adblock/production-restore-recipe.json'
    if sha256(manifest) != proof['recipe_sha256']:
        raise ValueError('RawS signing receipt does not match the checked out feature recipe')
    if trial:
        verify_checkout(root)
        validate_proof(root, proof['codec_trial'])
    return apk, proof


def sign(root, source, sdk, output):
    apk, proof = input_receipt(root, source)
    from raws_codec_ci import TRIAL_APK
    trial = 'codec_trial' in proof
    pin = expected_fingerprint(os.environ.get('RAWS_TEST_SIGNER_PIN_SHA256'))
    try:
        b64 = os.environ.get('RAWS_TEST_KEYSTORE_B64', '')
        if not 1 <= len(b64) <= 24000:
            raise ValueError
        data = base64.b64decode(b64, validate=True)
        if not data:
            raise ValueError
    except (ValueError, binascii.Error):
        raise ValueError('The RawS test keystore is not provisioned') from None
    if output.exists() or output.is_symlink():
        raise ValueError('Refusing a pre-existing release output')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='raws-test-key-') as secrets:
        key = Path(secrets) / 'raws-test.p12'
        fd = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
        with tempfile.TemporaryDirectory(prefix='.raws-release-', dir=output.parent) as scratch:
            stage = Path(scratch) / 'verified'
            stage.mkdir()
            result = sign_release_locally(
                apk, stage / (TRIAL_APK if trial else APK_NAME), sdk, key, ALIAS, pin,
                expected_input_sha256=proof['input_sha256'],
            )
            (stage / 'signing-receipt.json').write_text(json.dumps(
                {**proof, **result, 'distribution_ready': not trial},
                sort_keys=True, indent=2,
            ) + '\n')
            stage.rename(output)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--sdk', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    args = p.parse_args()
    try:
        sign(Path(__file__).resolve().parents[1], args.input, args.sdk, args.output_dir)
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        raise SystemExit('RawS test signing failed; no APK was promoted') from None
