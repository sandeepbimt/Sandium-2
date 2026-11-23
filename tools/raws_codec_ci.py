"""Optional combined RawS codec-trial admission and private APK provenance."""
import os
from pathlib import Path
import re

from raws_codec_trial import (
    BASELINE, BASELINE_TREE, CHROMIUM, FEATURE_SHA256, FFMPEG, WEBRTC, compose,
    ffmpeg_expected, git, media_settings, sha,
)

PROFILE = 'raws-combined-1477-android-arm64-avc-aac-v1'
TRIAL_APK = 'RawSandium-Combined-Codec-Test-arm64.apk'
HEX64 = re.compile(r'[0-9a-f]{64}')
# This regular lane already includes the isolated codec compile/sign route.
# Keep the exact reviewed PPBAS configuration on #1519 and both descendants.
FROZEN_SOURCE_BASELINE = '133c9426647b797a9dc3e96a6957f7cfbed3a584'
FROZEN_SOURCE_TREE = '0d676fb099807b4ba0d161467dcd7b24be1f422d'
FROZEN_PREDECESSOR_CI_TREE = '9b7322603ba926268eb8b122b61ba7f5ca15a2e7'
FROZEN_CI_TREE = '9b7322603ba926268eb8b122b61ba7f5ca15a2e7'
GIT_SHA = re.compile(r'[0-9a-f]{40}')
SCOPED_FILES = frozenset({
    'tools/raws_codec_ci.py', 'tools/raws_codec_trial.py', 'tests/test_raws_codec_ci.py',
})
BUILD_FLAGS = {
    'USE_PROPRIETARY_CODECS': 1, 'ENABLE_FFMPEG': 1,
    'ENABLE_OPENH264': 0, 'ENABLE_HLS_DEMUXER': 0,
    'ENABLE_MSE_MPEG2TS_STREAM_PARSER': 0, 'ENABLE_PLATFORM_HEVC': 0,
    'ENABLE_HEVC_PARSER_AND_HW_DECODER': 0,
    'PLATFORM_HAS_OPTIONAL_HEVC_DECODE_SUPPORT': 0,
    'PLATFORM_HAS_OPTIONAL_HEVC_ENCODE_SUPPORT': 0,
}


# Exact order emitted by the admitted native smoke (both binaries have passed).
NATIVE_SMOKE_CASES = (
    'third-party', 'exception', 'important', 'type', 'ordinary-first-party',
    'additional-first-party', 'youtube-initiator', 'not-fake-third-party',
    'lookalike', 'six-network', 'four-popup', 'scoped-hide',
    'scoped-exception', 'incident1471-player-rules',
)


def mode():
    text = os.environ.get('RAWS_CODEC_TRIAL', 'false')
    if text not in ('true', 'false'):
        raise ValueError('Malformed RawS codec test selector')
    return text == 'true'


def verify_checkout(root):
    if any(not GIT_SHA.fullmatch(pin) for pin in
           (BASELINE, BASELINE_TREE, FROZEN_SOURCE_BASELINE,
            FROZEN_SOURCE_TREE, FROZEN_PREDECESSOR_CI_TREE, FROZEN_CI_TREE)) or not HEX64.fullmatch(FEATURE_SHA256):
        raise ValueError('Malformed RawS codec source pins')
    parent = git(root, 'show', '-s', '--format=%P', 'HEAD')
    if (parent != BASELINE or
            git(root, 'show', '-s', '--format=%P', BASELINE) != FROZEN_SOURCE_BASELINE):
        raise ValueError('Codec test requires the isolated PPBAS child of exact #1519 source')
    if (git(root, 'rev-parse', FROZEN_SOURCE_BASELINE + '^{tree}') != FROZEN_SOURCE_TREE
            or git(root, 'rev-parse', BASELINE + '^{tree}') != BASELINE_TREE):
        raise ValueError('Codec trial checkout differs from the allowed combined RawS source')
    if git(root, 'rev-parse', FROZEN_SOURCE_BASELINE + ':.circleci') != FROZEN_PREDECESSOR_CI_TREE:
        raise ValueError('Codec trial requires the unchanged #1519 CI predecessor')
    if any(git(root, 'rev-parse', commit + ':.circleci') != FROZEN_CI_TREE
           for commit in (BASELINE, 'HEAD')):
        raise ValueError('Codec trial requires the exact reviewed PPBAS CI contract')
    changes = git(root, 'diff', '--name-only', '-z', '--no-renames', BASELINE, 'HEAD')
    changed_paths = changes.split('\0')
    if (changed_paths[-1] != '' or len(changed_paths) != len(SCOPED_FILES) + 1
            or set(changed_paths[:-1]) != SCOPED_FILES
            or git(root, 'diff', 'HEAD', '--name-only')):
        raise ValueError('Codec trial checkout differs from the allowed combined RawS source')
    for path in sorted(SCOPED_FILES):
        entry = git(root, 'ls-tree', 'HEAD', '--', path)
        if not re.fullmatch(r'100644 blob [0-9a-f]{40}\t' + re.escape(path), entry):
            raise ValueError('Codec trial checkout contains an invalid control file')
    manifest = root/'raws-adblock/production-restore-recipe.json'
    if manifest.is_symlink() or not manifest.is_file() or sha(manifest.read_bytes()) != FEATURE_SHA256:
        raise ValueError('Codec trial requires the exact combined RawS browser overlay')


def expected_args(root):
    args = compose((root/'ci/args.gn').read_bytes(), True)
    from raws_unsigned_apk import append_arg, mode
    if mode():
        args = append_arg(args.decode()).encode()
    return args


def read_generated_header(out):
    header = out/'gen/media/media_buildflags.h'
    if not header.is_file() or header.is_symlink():
        raise ValueError('No generated media buildflag evidence for the trial APK')
    data = header.read_bytes()
    for name, value in BUILD_FLAGS.items():
        actual = re.findall(rb'^#define[ \t]+BUILDFLAG_INTERNAL_' + name.encode() +
                            rb'\(\)[ \t]+\(([01])\)$', data, re.M)
        if actual != [str(value).encode()]:
            raise ValueError('Trial generated media buildflags differ: ' + name)
    return sha(data)


def compile_proof(root, out, settings, ffmpeg_configs, native_smoke):
    args = expected_args(root)
    if (out/'args.gn').read_bytes() != args:
        raise ValueError('Generated codec input args changed before APK verification')
    value = {
        'profile': PROFILE, 'control_commit': BASELINE,
        'chromium_revision': CHROMIUM, 'ffmpeg_revision': FFMPEG,
        'webrtc_revision': WEBRTC, 'generated_args_sha256': sha(args),
        'resolved_media_args': settings, 'ffmpeg_profiles': ffmpeg_configs,
        'generated_media_header_sha256': read_generated_header(out),
        'generated_media_buildflags': BUILD_FLAGS,
        'native_smoke_cases': native_smoke.get('cases'), 'test_only': True,
    }
    validate_proof(root, value)
    return value


def validate_proof(root, value):
    expected = {
        'profile': PROFILE, 'control_commit': BASELINE,
        'chromium_revision': CHROMIUM, 'ffmpeg_revision': FFMPEG,
        'webrtc_revision': WEBRTC, 'generated_args_sha256': sha(expected_args(root)),
        'resolved_media_args': media_settings(True), 'generated_media_buildflags': BUILD_FLAGS,
        'native_smoke_cases': list(NATIVE_SMOKE_CASES), 'test_only': True,
    }
    extra = {'ffmpeg_profiles', 'generated_media_header_sha256'}
    if (not isinstance(value, dict) or set(value) != set(expected) | extra
            or any(value[k] != v for k, v in expected.items())
            or value['test_only'] is not True
            or any(type(v) is not int for v in value['generated_media_buildflags'].values())
            or not isinstance(value['generated_media_header_sha256'], str)
            or not HEX64.fullmatch(value['generated_media_header_sha256'])):
        raise ValueError('Missing or inconsistent private codec proof')
    profiles = value['ffmpeg_profiles']
    if not isinstance(profiles, dict) or set(profiles) != {'Chromium', 'Chrome'}:
        raise ValueError('Missing private FFmpeg configuration evidence')
    for name, profile in profiles.items():
        if (not isinstance(profile, dict) or set(profile) != {'path', 'sha256', 'features'}
                or profile['path'] != f'chromium/config/{name}/android/arm64/config_components.h'
                or profile['features'] != ffmpeg_expected(name)
                or not isinstance(profile['sha256'], str) or not HEX64.fullmatch(profile['sha256'])):
            raise ValueError('Unexpected FFmpeg evidence in private codec proof')
