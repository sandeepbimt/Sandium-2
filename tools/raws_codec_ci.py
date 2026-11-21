"""Optional RawS #1477 codec-trial admission and private APK provenance."""
import os
from pathlib import Path
import re

from raws_codec_trial import (
    BASELINE, BASELINE_TREE, CHROMIUM, FEATURE_SHA256, FFMPEG, WEBRTC, compose,
    ffmpeg_expected, git, media_settings, sha,
)

PROFILE = 'raws-1477-android-arm64-avc-aac-v1'
TRIAL_APK = 'RawSandium-Codec-Trial-arm64.apk'
HEX64 = re.compile(r'[0-9a-f]{64}')
# Every modified tracked file must be a trial control/tool or its test. In
# particular, no Chromium overlay, APK identity, source pin or checkpoint
# routine can be changed as part of this controlled A/B.
SCOPED_FILES = frozenset({
    '.circleci/config.yml', 'docs/raws-codec-trial.md',
    'tools/generate_full_config.py', 'tools/ci_compile.py',
    'tools/ci_restore_only.py', 'tools/ci_sign_raws_test.py',
    'tools/raws_codec_ci.py', 'tools/raws_codec_trial.py',
    'tests/test_raws_codec_ci.py', 'tests/test_raws_codec_trial.py',
    'tests/test_raws_distinct_signing_workflow.py',
})
BUILD_FLAGS = {
    'USE_PROPRIETARY_CODECS': 1, 'ENABLE_FFMPEG': 1,
    'ENABLE_OPENH264': 0, 'ENABLE_HLS_DEMUXER': 0,
    'ENABLE_MSE_MPEG2TS_STREAM_PARSER': 0, 'ENABLE_PLATFORM_HEVC': 0,
    'ENABLE_HEVC_PARSER_AND_HW_DECODER': 0,
    'PLATFORM_HAS_OPTIONAL_HEVC_DECODE_SUPPORT': 0,
    'PLATFORM_HAS_OPTIONAL_HEVC_ENCODE_SUPPORT': 0,
}


def mode():
    text = os.environ.get('RAWS_CODEC_TRIAL', 'false')
    if text not in ('true', 'false'):
        raise ValueError('Malformed RawS codec test selector')
    return text == 'true'


def verify_checkout(root):
    parent = git(root, 'show', '-s', '--format=%P', 'HEAD')
    if parent != BASELINE:
        raise ValueError('Codec test requires a single isolated child of exact RawS #1477')
    # Validate original tree, all changed paths and absence of tracked dirty edits.
    changes = set(git(root, 'diff', '--name-only', '--no-renames', BASELINE, 'HEAD').splitlines())
    if (git(root, 'rev-parse', BASELINE + '^{tree}') != BASELINE_TREE
            or not changes <= SCOPED_FILES or not {'tools/raws_codec_ci.py', '.circleci/config.yml'} <= changes
            or git(root, 'diff', 'HEAD', '--name-only')):
        raise ValueError('Codec trial checkout differs from the allowed #1477 A/B source')
    if sha((root/'raws-adblock/production-restore-recipe.json').read_bytes()) != FEATURE_SHA256:
        raise ValueError('Codec trial requires the original #1477 browser overlay')


def expected_args(root):
    return compose((root/'ci/args.gn').read_bytes(), True)


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


def compile_proof(root, out, settings, ffmpeg_configs):
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
        'test_only': True,
    }
    validate_proof(root, value)
    return value


def validate_proof(root, value):
    expected = {
        'profile': PROFILE, 'control_commit': BASELINE,
        'chromium_revision': CHROMIUM, 'ffmpeg_revision': FFMPEG,
        'webrtc_revision': WEBRTC, 'generated_args_sha256': sha(expected_args(root)),
        'resolved_media_args': media_settings(True), 'generated_media_buildflags': BUILD_FLAGS,
        'test_only': True,
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
