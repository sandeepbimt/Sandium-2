#!/usr/bin/env python3
"""Pinned Chromium158 native host dependencies. Caller owns process-group deadline.

prepare may install upstream OS packages; verify is read-only. SDK/JDK remain
owned by pinned source initialization/CIPD, never replaced with system versions.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile
import source

FIXTURES = Path(__file__).resolve().parents[2] / 'tests/fixtures/upgrade1100/host-deps'
# No system-wide upgrade, ChromeOS fonts, debug symbols, NaCl or cross GCC.
# Upstream158 retains --android as a compatibility alias enabling lib32.
FLAGS = ['--android', '--no-prompt', '--no-chromeos-fonts', '--no-syms',
         '--no-nacl', '--no-arm', '--no-backwards-compatible']


def authenticated_source(root):
    root = Path(root).resolve()
    source.verify(root / 'brave-work')
    src = root / 'brave-work/src'
    manifest = json.loads((FIXTURES / 'manifest.json').read_text())
    for relative, expected in manifest.items():
        data = (src / relative).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected['sha256']:
            raise ValueError('Unreviewed Chromium158 host input: ' + relative)
    patches = json.loads((FIXTURES / 'brave-patches.json').read_text())
    for relative, expected in patches.items():
        data = (src / 'brave' / relative).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected['sha256']:
            raise ValueError('Unreviewed Brave158 host patch: ' + relative)
    return src


def versions(src):
    deps = (src / 'DEPS').read_text()
    config = (src / 'build/config/android/config.gni').read_text()
    def one(pattern, text):
        matches = re.findall(pattern, text)
        if len(matches) != 1:
            raise ValueError('Ambiguous composed host version: ' + pattern)
        return matches[0]
    return {
        'jdk': one(r"'jdk_version': 'version:2@jdk-([0-9.]+)\+", deps),
        'sdk_platform': one(r'public_android_sdk_platform_version = "([0-9.]+)"', config),
        'sdk_build_tools': one(r'public_android_sdk_build_tools_version = "([0-9.]+)"', config),
    }


def native_command(src, *, check_only):
    command = [sys.executable, str(src / 'build/install-build-deps.py'), *FLAGS]
    if check_only:
        command.append('--quick-check')
    else:
        # Noninteractive privilege check; no detached process, shell or daemon.
        command = ['sudo', '-n', *command]
    return command


def invoke(command, src):
    return subprocess.run(command, cwd=src, check=True,
                          env=dict(os.environ, DEBIAN_FRONTEND='noninteractive',
                                   PYTHONDONTWRITEBYTECODE='1'))


def executable(path):
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError('Missing pinned native executable: ' + str(path))
    return str(path)


def output(args):
    return subprocess.check_output(args, stderr=subprocess.STDOUT, text=True, timeout=30)


def capabilities(src):
    selected = versions(src)
    java = src / 'third_party/jdk/current/bin/java'
    javac = src / 'third_party/jdk/current/bin/javac'
    # DEPS pins jdk-25.0.5+8; these binaries, not system JAVA_HOME, must work.
    for binary, args, pattern in ((java, ['-version'], r'version "' + re.escape(selected['jdk']) + r'(?:[+"-])'),
                                  (javac, ['-version'], r'javac ' + re.escape(selected['jdk']) + r'(?:[+\s-]|$)')):
        if not re.search(pattern, output([executable(binary), *args])):
            raise ValueError('Pinned JDK version mismatch: ' + str(binary))
    sdk = src / 'third_party/android_sdk/public'
    platform_jar = sdk / ('platforms/android-' + selected['sdk_platform']) / 'android.jar'
    with zipfile.ZipFile(platform_jar) as jar:
        if 'android/app/Activity.class' not in jar.namelist():
            raise ValueError('Android37.2 framework jar missing Activity')
    build = sdk / ('build-tools/' + selected['sdk_build_tools'])
    for aapt2 in (build / 'aapt2', src / 'third_party/android_build_tools/aapt2/cipd/aapt2'):
        aapt = output([executable(aapt2), 'version'])
        if 'Android Asset Packaging Tool' not in aapt:
            raise ValueError('Pinned Android aapt2 capability unavailable: ' + str(aapt2))
    # Validate signing capability without keys, an APK, or any signing operation.
    signer = build / 'lib/apksigner.jar'
    if not signer.is_file() or not output([str(java), '-jar', str(signer), 'version']).strip():
        raise ValueError('Pinned APK signer unavailable')
    return selected


def verify(root):
    src = authenticated_source(root)
    invoke(native_command(src, check_only=True), src)
    result = capabilities(src)
    print('SANDIUM_HOST_DEPS=VERIFIED ' + json.dumps(result, sort_keys=True))
    return result


def prepare(root):
    src = authenticated_source(root)
    try:
        invoke(native_command(src, check_only=True), src)
    except subprocess.CalledProcessError:
        invoke(native_command(src, check_only=False), src)
    # Never trusts an archived marker or success exit without capability checks.
    return verify(root)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('prepare', 'verify'))
    parser.add_argument('--root', required=True, type=Path)
    args = parser.parse_args()
    (prepare if args.action == 'prepare' else verify)(args.root)


if __name__ == '__main__':
    main()
