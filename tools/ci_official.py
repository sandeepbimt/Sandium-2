"""Fail closed on official optimization settings and record resolved inputs."""
import hashlib
import json
import re
import subprocess
from pathlib import Path
from raw import lock


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_settings(text):
    values = dict(re.findall(r'^([a-zA-Z_][a-zA-Z_0-9]*) = (.+)$', text, re.M))
    expected = {'is_official_build': 'true', 'is_debug': 'false',
                'is_component_build': 'false', 'target_os': '"android"',
                'target_cpu': '"arm64"', 'use_thin_lto': 'true',
                'use_remoteexec': 'true', 'use_siso': 'true', 'use_reclient': 'false'}
    for name, value in expected.items():
        if values.get(name) != value:
            raise ValueError('Unexpected official GN setting: ' + name)
    # Preserve upstream's platform choice: high-end Android uses PGO, others AFDO.
    if values.get('chrome_pgo_phase') == '2':
        profile_mode = 'pgo'
    elif values.get('chrome_pgo_phase') == '0' and values.get('clang_use_default_sample_profile') == 'true':
        profile_mode = 'afdo'
    else:
        raise ValueError('Official profile optimization disabled or unsupported')
    return values, profile_mode


def validate_flags(payload, out, src, mode):
    if not isinstance(payload, dict):
        raise ValueError('Unexpected GN flags response')
    if 'cflags' not in payload and len(payload) == 1:
        payload = next(iter(payload.values()))
    flags = payload.get('cflags', [])
    if '-flto=thin' not in flags:
        raise ValueError('Native graph does not enable ThinLTO')
    prefix = '-fprofile-use=' if mode == 'pgo' else '-fprofile-sample-use='
    profiles = [f[len(prefix):] for f in flags if f.startswith(prefix)]
    if len(profiles) != 1:
        raise ValueError('Native graph lacks exact optimization profile')
    profile = (out / profiles[0]).resolve()
    relative = ('chrome/android/orderfiles/arm64/pgo_profile.arm64.profdata' if mode == 'pgo'
                else 'chrome/android/profiles/afdo.prof')
    if profile != (src / relative).resolve() or not profile.is_file() or not profile.stat().st_size:
        raise ValueError('Missing or unexpected pinned optimization profile')
    return {'path': relative, 'sha256': sha(profile), 'bytes': profile.stat().st_size}


def verify_official(src, depot, out, env, artifacts, stage):
    args = subprocess.check_output([str(depot/'gn'), 'args', str(out), '--list', '--short'],
                                   cwd=src, env=env, text=True, timeout=120)
    (artifacts/f'gn-effective-{stage}.txt').write_text(args)
    values, mode = validate_settings(args)
    payload = subprocess.check_output([str(depot/'gn'), 'desc', str(out), '//base:base', 'cflags', '--format=json'],
                                      cwd=src, env=env, text=True, timeout=120)
    profile = validate_flags(json.loads(payload), out, src, mode)
    clang = src/'third_party/llvm-build/Release+Asserts/cr_build_revision'
    if not clang.is_file() or not clang.read_text().strip():
        raise ValueError('Missing resolved Clang revision')
    data = lock()
    result = {'chromium': data['chromium'], 'depot_tools': data['depot_tools'],
              'gclient_custom_vars': data['gclient_custom_vars'], 'profile_mode': mode,
              'profile': profile, 'clang_revision': clang.read_text().strip(),
              'deps_sha256': sha(src/'DEPS'), 'args_sha256': sha(out/'args.gn'),
              'effective_settings': {k: values[k] for k in (
                  'is_official_build', 'use_thin_lto', 'chrome_pgo_phase', 'target_os', 'target_cpu')},
              'arm64_orderfile_pin': (src/'chrome/build/android-arm64.orderfile.txt').read_text().strip()}
    (artifacts/f'official-inputs-{stage}.json').write_text(json.dumps(result, indent=2)+'\n')
    return result
