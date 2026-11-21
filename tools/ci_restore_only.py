#!/usr/bin/env python3
"""Read-only #1396 cache admission and strict success gate for regular RawS Full."""

import argparse
import hashlib
import os

import ci_full as full
from ci_compile import file_sha, fingerprint
from ci_restore_probe import validate_restore

BASELINE = 'e7e782067daef429073e54c2bd8fbb91da7c8439'
FINGERPRINT = 'b35abf73bb0a0a5998baeee4261715cbe73c8d55512c3a948cd6940590689843'
RECEIPT_ID = 'c84a3f88d74b96fc5c8f4b38e3946e85e1a253e1bccc61550f43f59af39c15fe'
RECEIPT_SHA = 'd6892b9f3cdfedaedd567b981f7459510877bfc001cd98781b8c9ce1802244e6'
BASE_ID = 'd0bf5cf09ce9adf4d176ba8271357f1d22aafa60cc120a54e215d58561b1e631'
OLD_APK = '7feb138bacb61dd9f77fca29c579330a2209f1ccd754c5e443962e76a76a977b'
RECEIPT_CACHE = 'raws-final-receipt-v1-1okrnzzf7a7dVnuYH3RZUQh3v8ABzZh4G4yc4YAiROY='
BASE_CACHE = 'raws-final-base-v1-xLg0fZPI+fw9SpoFza6mLhAhAB2lVxH6jMOzj9OmBBU='
FINAL = full.ROOT / '.raws-final-archive'


def distinct_test_mode():
    value = os.environ.get('RAWS_DISTINCT_TEST_IDENTITY', 'false')
    if value not in ('true', 'false'):
        raise ValueError('Malformed RawS test identity selector')
    return value == 'true'


def gate():
    from raws_codec_ci import mode as codec_mode, verify_checkout
    if codec_mode():
        if not distinct_test_mode():
            raise ValueError('Codec mode is only available to the isolated signed test job')
        verify_checkout(full.ROOT)
    if distinct_test_mode():
        from ci_sign_raws_test import SIGNING_SECRETS
        if any(key in os.environ for key in SIGNING_SECRETS):
            raise ValueError('RawS compiler job must not receive signing credentials')
    if (os.environ.get('RAWS_STAGE') != '1'
            or os.environ.get('RAWS_ALLOW_FRESH_SEED') != 'false'
            or fingerprint() != FINGERPRINT
            or full.fresh()):
        raise ValueError('Restore-only Full requires exact official158 scope and no fresh seed')
    full.gate()


def check_receipt(receipt):
    payload = full.D.valid(receipt)
    plan = payload['plan']
    if (receipt['id'] != RECEIPT_ID or payload['source'] != BASELINE
            or payload.get('apk_verified') is not True or payload.get('apk_sha256') != OLD_APK
            or plan['layers'] or plan['head'] != BASE_ID or plan['base']['id'] != BASE_ID):
        raise ValueError('Only the verified #1396 final archive is admitted')
    return payload


def select():
    gate()
    active_feature()  # Fail before downloading large shards if a recipe is not admitted.
    path = FINAL / 'receipt.json'
    if not path.is_file() or path.is_symlink() or file_sha(path) != RECEIPT_SHA:
        raise ValueError('Exact #1396 immutable receipt missing or changed; no fallback')
    receipt = full.D.c.read(path)
    check_receipt(receipt)
    proof = full.D.c.read(FINAL / 'archived-apk-proof.json')
    if proof.get('sha256') != OLD_APK or not proof.get('bytes', 0):
        raise ValueError('Missing #1396 archived APK proof')
    original = full.D.HEAD
    try:
        full.D.HEAD = path
        full.D.select(precheck=True)
    finally:
        full.D.HEAD = original


def restored():
    gate()
    root = full.ROOT
    selected = full.D.c.read(full.D.STATE / 'selected.json')
    check_receipt(selected)
    proof = full.D.c.read(full.D.STATE / 'restored-proof.json')
    validate_restore(selected, proof)
    source = root / 'work/source'
    old_apk = source / 'src/out/RawSandium/apks/ChromePublic.apk'
    if not old_apk.is_file() or file_sha(old_apk) != OLD_APK:
        raise ValueError('Restored #1396 APK differs from its receipt')
    ready = full.D.c.read(source / 'source-ready.json')
    lock_sha = hashlib.sha256((root / 'upstream.lock.json').read_bytes()).hexdigest()
    if ready.get('ready') is not True or ready.get('lock_sha256') != lock_sha:
        raise ValueError('Missing or invalid restored source proof; no fallback')


def active_feature():
    from raw import lock
    from restore_only_feature import load
    data = lock()
    return load(full.ROOT, FINGERPRINT, data['chromium']['revision'])


def compile_once():
    from ci_compile import main
    from raw import lock
    restored()
    feature = active_feature()
    if feature is not None:
        import time
        from ci_prepare_raws_engine import prepare
        epoch=full.D.c.read(full.D.STATE/'job-start.json')['epoch']
        if time.time()-epoch > 1800:
            raise ValueError('Not enough original RawS job budget to prepare and build')
        src = full.ROOT / 'work/source/src'
        upstream = lock()
        feature.preflight(src, upstream)
        prepare()
        from restore_only_port1442 import prepare_stage
        prepare_stage(full.ROOT/'.raws-staged-engine', feature)
        feature.apply(src, upstream)
    from raws_codec_ci import mode as codec_mode
    if codec_mode():
        return main(1, feature=feature, distinct_test=True, codec_trial=True)
    if distinct_test_mode():
        return main(1, feature=feature, distinct_test=True)
    return main(1, feature=feature)


def completed():
    gate()
    root = full.ROOT
    state = full.D.c.read(root / 'handoff/stage1/state.json')
    if state.get('status') == 'slice_expired':
        raise ValueError('RawS Full compile timed out; no progress saved and no continuation')
    feature = active_feature()
    from restore_only_port1442 import proof as port_proof
    port1442 = feature is not None and port_proof() is not None
    name = ('RawSandium-1442-Filters-arm64.apk' if port1442 else 'RawSandium-EasyList-arm64.apk')
    apk = (root / 'handoff/stage1' / name if feature is not None
           else root / 'artifacts/RawSandium-baseline-arm64.apk')
    expected_recipe = feature.identity if feature is not None else None
    smoke_cases = state.get('raws_engine_smoke', {}).get('cases', [])
    if feature is not None and (len(smoke_cases) != (14 if port1442 else 9)
                                or ('incident1471-player-rules' in smoke_cases) != port1442
                                or state.get('raws_engine_apk_graph_verified') is not True):
        raise ValueError('Missing actual engine smoke or Android linkage proof')
    if feature is not None and feature.has_ui and state.get('raws_ui_apk_graph_verified') is not True:
        raise ValueError('Missing RawS Settings Android linkage proof')
    if state.get('feature_recipe_sha256') != expected_recipe:
        raise ValueError('APK does not match the selected feature recipe')
    if (state.get('status') != 'done' or state.get('stage') != 1
            or state.get('fingerprint') != FINGERPRINT
            or not all(state.get(k) is True for k in (
                'apk_produced', 'apk_verified', 'apk_zip_verified', 'apk_signature_verified'))
            or not apk.is_file() or state.get('apk_sha256') != file_sha(apk)):
        raise ValueError('Restore-only Full did not produce a verified APK')
    from raws_codec_ci import mode as codec_mode, validate_proof
    if codec_mode():
        validate_proof(root, state.get('codec_trial'))
    elif 'codec_trial' in state:
        raise ValueError('Codec trial state cannot enter the ordinary test workflow')
    if distinct_test_mode():
        from ci_sign_raws_test import stage_private_input
        stage_private_input(root, state, apk)
    elif feature is not None:
        apk.replace(root/'artifacts'/apk.name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('select', 'restored', 'compile', 'completed'))
    args = parser.parse_args()
    raise SystemExit({'select': select, 'restored': restored, 'compile': compile_once,
                      'completed': completed}[args.phase]())
