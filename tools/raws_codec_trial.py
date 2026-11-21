#!/usr/bin/env python3
"""Prepare an isolated, test-only GN graph for the verified combined RawS source.

No CI, checkpoint, signing, APK building, or distribution actions.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from raw import ROOT, lock
from raws_release_identity import APPLICATION_ID, compose_gn_args

BASELINE = '343c5a912576938b2bdfb581b6186ff57ba630a1'
BASELINE_TREE = 'f7bab617166c80351f85d7c8666f8dbc4616622a'
BASE_ARGS_SHA256 = '978dbc344dde76631bb301585cf2b80d2020b45553a9757092fe24c32344e5d3'
FEATURE_SHA256 = '3b3caa7341f03798f02af66d2f7e6d4ce92cee23392729de3b2b9f746e8d4bc6'
CHROMIUM = '52bdd21723d5db0c9ab11716d38feac74828cf84'
WEBRTC = 'fb1c41a93d92d4188f068f437d80ef2c4b50c3a9'
FFMPEG = '42a2a7a2b2ceb0b1554af1e99a8cdaae189404bb'
TRIAL_OUT = 'out/RawSandiumCodecTrial'
# M158 media/media_options.gni declares these independent knobs. OpenH264
# is the bundled encoder (not Android MediaCodec or FFmpeg AVC decoding).
# Keeping the upstream HLS and HEVC knobs off also keeps their downstream
# defaults off for this exact non-Cast, non-fuzz ARM64 browser.
BASELINE_OPTION_OVERRIDES = (
    'media_use_openh264',
    'enable_hls_demuxer',
    'enable_hevc_parser_and_hw_decoder',
)
DERIVED_BASELINE_OPTIONS = (
    'enable_mse_mpeg2ts_stream_parser',
    'enable_platform_hevc',
    'platform_has_optional_hevc_decode_support',
    'platform_has_optional_hevc_encode_support',
    'rtc_use_h264',
    'rtc_use_h265',
)
FLAGS = (b'proprietary_codecs = true\nffmpeg_branding = "Chrome"\n' +
         ''.join(name + ' = false\n' for name in BASELINE_OPTION_OVERRIDES).encode())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def compose(baseline, distinct_identity):
    if sha(baseline) != BASE_ARGS_SHA256:
        raise ValueError('Exact #1477 ordinary args are required')
    if distinct_identity:
        baseline = compose_gn_args(baseline.decode()).encode()
    return baseline.rstrip(b'\n') + b'\n\n# Test-only RawS codec comparison.\n' + FLAGS


def media_settings(distinct_identity):
    expected = {
        'proprietary_codecs': 'true', 'ffmpeg_branding': '"Chrome"',
        'media_use_ffmpeg': 'true', 'is_chrome_branded': 'false',
        'is_chrome_for_testing_branded': 'false',
        'chrome_public_manifest_package': f'"{APPLICATION_ID if distinct_identity else "org.chromium.chrome"}"',
    }
    expected.update(dict.fromkeys(BASELINE_OPTION_OVERRIDES + DERIVED_BASELINE_OPTIONS, 'false'))
    return expected


def check_media_args(text, distinct_identity):
    expected = media_settings(distinct_identity)
    for key, value in expected.items():
        actual = re.findall(r'^' + key + r' = (.+)$', text, re.M)
        if actual != [value]:
            raise ValueError('Unexpected resolved media or package setting: ' + key)
    return expected


def ffmpeg_expected(brand):
    return {
        'CONFIG_MOV_DEMUXER': '1',
        **dict.fromkeys(('CONFIG_H264_DECODER', 'CONFIG_AAC_DECODER',
                         'CONFIG_H264_PARSER', 'CONFIG_AAC_PARSER'), '1' if brand == 'Chrome' else '0'),
        **dict.fromkeys(('CONFIG_HEVC_DECODER', 'CONFIG_HEVC_PARSER',
                         'CONFIG_HLS_DEMUXER'), '0'),
    }


def check_ffmpeg_configs(ffmpeg):
    # Check the actual generated configs in the pinned dependency, not the
    # FFmpeg branding name alone. Both profiles retain the same MP4 mux family.
    profiles = {}
    for brand in ('Chromium', 'Chrome'):
        relative = f'chromium/config/{brand}/android/arm64/config_components.h'
        path = ffmpeg/relative
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(ffmpeg.resolve()):
            raise ValueError('Pinned Android FFmpeg profile not found: ' + brand)
        data = path.read_bytes()
        checks = ffmpeg_expected(brand)
        for name, expected in checks.items():
            actual = re.findall(rb'^#define[ \t]+' + name.encode() + rb'[ \t]+([01])$', data, re.M)
            if actual != [expected.encode()]:
                raise ValueError('Unexpected Android FFmpeg feature: ' + brand + ' ' + name)
        profiles[brand] = {'path': relative, 'sha256': sha(data), 'features': checks}
    return profiles


def local_env(depot=None):
    # Pass only needed baseline environment values; no signer/CI credentials.
    env = {name: os.environ[name] for name in ('HOME', 'PATH', 'TMPDIR', 'LANG', 'LC_ALL')
           if name in os.environ}
    if depot is not None:
        env.update(PATH=str(depot)+os.pathsep+env.get('PATH', os.defpath), DEPOT_TOOLS_UPDATE='0')
    return env


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True, env=local_env(),
                                   timeout=120).strip()


def checked_paths(src, depot):
    if any(p.is_symlink() for p in (src, depot, src/'out', src/TRIAL_OUT)):
        raise ValueError('Trial input or output is a symlink')
    src, depot = src.resolve(strict=True), depot.resolve(strict=True)
    if src.is_relative_to(ROOT) or ROOT.is_relative_to(src) or (
            src.parent.name == 'source' and src.parent.parent.name == 'work'):
        raise ValueError('Use a separate prepared Chromium checkout, not production CI workspace')
    if not (depot/'gn').is_file():
        raise ValueError('Pinned depot_tools GN is unavailable')
    return src, depot


def verify_media_dependencies(src):
    for name, revision in (('ffmpeg', FFMPEG), ('webrtc', WEBRTC)):
        dep = src/'third_party'/name
        if not dep.is_dir() or dep.is_symlink() or git(dep, 'rev-parse', 'HEAD') != revision:
            raise ValueError('Exact M158 dependency checkout is required: ' + name)
        if git(dep, 'status', '--porcelain', '--untracked-files=no'):
            raise ValueError('Media dependency tracked sources differ from the pinned revision: ' + name)
    return check_ffmpeg_configs(src/'third_party/ffmpeg')


def prepare(src, depot, distinct_identity):
    from ci_official import verify_official
    from ci_restore_only import FINGERPRINT, active_feature
    src, depot = checked_paths(src, depot)
    # Additional untracked trial tool/tests do not change the exact tracked product baseline.
    if git(ROOT, 'rev-parse', 'HEAD') != BASELINE or git(ROOT, 'rev-parse', 'HEAD^{tree}') != BASELINE_TREE or git(
            ROOT, 'diff', 'HEAD', '--name-only', '-z'):
        raise ValueError('Use a clean exact combined RawS project checkout to run the trial')
    from ci_compile import fingerprint
    if fingerprint() != FINGERPRINT:
        raise ValueError('Ordinary restore fingerprint changed')
    args = compose((ROOT/'ci/args.gn').read_bytes(), distinct_identity)
    data = lock()
    if data['chromium']['revision'] != CHROMIUM:
        raise ValueError('Wrong Chromium lock revision')
    feature = active_feature()
    if feature is None or feature.identity != FEATURE_SHA256 or not feature.has_ui:
        raise ValueError('Exact combined RawS feature manifest is required')
    feature.verify(src, data)
    if git(depot, 'rev-parse', 'HEAD') != data['depot_tools']['revision']:
        raise ValueError('Wrong depot_tools revision')
    ffmpeg_config = verify_media_dependencies(src)
    out = src/TRIAL_OUT
    # Must not inherit an existing APK, args, Ninja graph, or checkpoint files.
    out.mkdir(parents=True, exist_ok=False)
    (out/'args.gn').write_bytes(args)
    env = local_env(depot)
    subprocess.run([str(depot/'gn'), 'gen', TRIAL_OUT, '--fail-on-unused-args'],
                   cwd=src, env=env, check=True, timeout=300)
    official = verify_official(src, depot, out, env, out, 'codec-trial')
    effective = check_media_args((out/'gn-effective-codec-trial.txt').read_text(), distinct_identity)
    if (out/'args.gn').read_bytes() != args:
        raise ValueError('Trial args changed while generating GN')
    feature.verify(src, data)
    receipt = {
        'schema': 1, 'purpose': 'Combined RawS test-only codec graph',
        'status': 'gn_verified_not_compiled', 'apk_produced': False,
        'product_commit': BASELINE, 'product_tree': BASELINE_TREE,
        'chromium': CHROMIUM, 'ffmpeg': FFMPEG, 'webrtc': WEBRTC, 'depot_tools': data['depot_tools']['revision'],
        'feature_manifest_sha256': feature.identity, 'base_args_sha256': BASE_ARGS_SHA256,
        'trial_args_sha256': sha(args), 'resolved_media_args': effective,
        'official_optimization': official, 'android_ffmpeg_configs': ffmpeg_config,
    }
    with (out/'codec-trial-receipt.json').open('x') as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write('\n')
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepared-source', type=Path, required=True)
    p.add_argument('--depot-tools', type=Path, required=True)
    p.add_argument('--distinct-test-identity', action='store_true')
    a = p.parse_args()
    try:
        out = prepare(a.prepared_source, a.depot_tools, a.distinct_test_identity)
    except (ValueError, OSError, subprocess.SubprocessError) as e:
        print('BLOCKED:', e, file=sys.stderr)
        return 1
    print('Verified test-only graph; no APK built:', out)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
