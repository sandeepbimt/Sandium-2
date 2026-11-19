#!/usr/bin/env python3
"""Version-isolated source acquisition; caller owns deadline/process cleanup.

Never accepts old compiled output or manufactures a build-ready receipt. A
successful init is only source-synced; product/GN/official gates follow elsewhere.
"""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess

CORE = 'bd6d26d1bced03c17a98baa86d2cd3425d543d1b'
CHROMIUM = '52bdd21723d5db0c9ab11716d38feac74828cf84'
TAG = '158.0.8127.42'
BRAVE_TAG = 'v1.100.58'
BRAVE_TAG_OBJECT = '621f5b3bb82c70d193454b12ef4e351dbce715b7'
URL = 'https://github.com/brave/brave-core.git'
PROFILE = Path(__file__).resolve().parents[2] / 'docs/upgrades/1.100.58/candidate-profile.json'
IDENTITY = {'schema': 1, 'core': CORE, 'chromium': CHROMIUM}


def run(argv, **kwargs):
    return subprocess.run(argv, check=True, text=True, **kwargs)


def output(argv, **kwargs):
    return run(argv, capture_output=True, **kwargs).stdout.strip()


def owned(root):
    root = Path(root)
    if root.is_symlink() or (root / 'src').is_symlink():
        raise ValueError('Symlinked source root')
    root = root.resolve()
    scope = os.environ.get('FULL_U_SCOPE', '')
    marker = root / '.sandium/full-u-owner.json'
    if not re.fullmatch(r'full-u-v1-[0-9a-f]{64}', scope):
        raise ValueError('Runner upgrade scope required')
    if not marker.is_file() or json.loads(marker.read_text()) != {'schema': 1, 'scope': scope}:
        raise ValueError('Source root lacks exact runner ownership')
    return root


def verify(root, *, require_receipt=True):
    root = owned(root)
    core, src = root / 'src/brave', root / 'src'
    if output(['git', '-C', str(core), 'rev-parse', 'HEAD']) != CORE:
        raise ValueError('Wrong Brave core revision')
    package_bytes = (core / 'package.json').read_bytes()
    expected = json.loads(PROFILE.read_text())['source']['core_package_sha256']
    if hashlib.sha256(package_bytes).hexdigest() != expected:
        raise ValueError('Upstream package differs from reviewed bytes')
    package = json.loads(package_bytes)
    if package['version'] != '1.100.58' or package['config']['projects']['chrome']['tag'] != TAG:
        raise ValueError('Wrong upstream package pair')
    if output(['git', '-C', str(src), 'rev-parse', 'HEAD']) != CHROMIUM:
        raise ValueError('Wrong Chromium revision')
    for relative in ('.gclient', 'src/DEPS', 'src/build/install-build-deps.sh'):
        if not (root / relative).is_file():
            raise ValueError('Incomplete source initialization: ' + relative)
    proof = dict(IDENTITY, phase='source-synced', package_sha256=expected)
    if require_receipt and (not (root / '.sandium-source-synced.json').is_file() or
            json.loads((root / '.sandium-source-synced.json').read_text()) != proof):
        raise ValueError('Successful pinned initialization receipt required')
    return proof


def configure_remote(core, env):
    address = env.get('SANDIUM_REAPI_ADDRESS') or 'remote.buildbuddy.io:443'
    if not re.fullmatch(r'[A-Za-z0-9.-]+:443', address):
        raise ValueError('Invalid reviewed REAPI endpoint shape')
    path = core / '.env'
    prior = path.read_text().splitlines() if path.exists() else []
    lines = [line for line in prior if not line.startswith(
        ('rbe_service=', 'use_remoteexec=', 'is_brave_release_build='))]
    lines += ['rbe_service=' + address, 'use_remoteexec=true', 'is_brave_release_build=0']
    tmp = core / '.env.full-u.tmp'
    tmp.write_text('\n'.join(lines) + '\n')
    os.replace(tmp, path)


def ensure_origin(core):
    """Recover only the interrupted git-init window, never replace a remote."""
    remotes = output(['git', '-C', str(core), 'remote']).splitlines()
    if not remotes:
        head = subprocess.run(['git', '-C', str(core), 'rev-parse', '--verify', 'HEAD'],
                              text=True, capture_output=True)
        if head.returncode == 0 or output(['git', '-C', str(core), 'ls-files']):
            raise ValueError('Origin missing on nonempty source repository')
        run(['git', '-C', str(core), 'remote', 'add', 'origin', URL])
    if remotes and remotes != ['origin']:
        raise ValueError('Unexpected additional source remote')
    if output(['git', '-C', str(core), 'remote', 'get-url', 'origin']) != URL:
        raise ValueError('Unexpected source origin')


def assert_no_stale_git_locks(root):
    # A killed fetch/index update may leave a durable lock without a writer.
    # Ownership alone does not establish that deleting it is safe. Preserve the
    # checkpoint and report the exact bounded repair case instead of retrying
    # indefinitely or deleting arbitrary repository files.
    for repository in (root/'src', root/'src/brave', root/'src/brave/vendor/depot_tools'):
        git = repository/'.git'
        if git.is_dir() and not git.is_symlink():
            for name in ('index.lock', 'shallow.lock', 'config.lock', 'HEAD.lock', 'packed-refs.lock'):
                lock = git/name
                if lock.exists() or lock.is_symlink():
                    raise ValueError('SOURCE_REPAIR_REQUIRED: preserved Git lock ' + str(lock.relative_to(root)))


def acquire(root):
    root = owned(root)
    assert_no_stale_git_locks(root)
    core = root / 'src/brave'
    if (root / 'src/out').exists():
        raise ValueError('Source acquisition must not import compiled output')
    if not (core / '.git').exists():
        if core.exists() and any(core.iterdir()):
            raise ValueError('Unowned nonempty core directory')
        core.mkdir(parents=True, exist_ok=True)
        run(['git', 'init', str(core)])
    ensure_origin(core)
    # An interrupted fetch is resumable under this owned target namespace.
    # Never replace an already checked-out different source revision.
    head = subprocess.run(['git', '-C', str(core), 'rev-parse', '--verify', 'HEAD'],
                          text=True, capture_output=True)
    if head.returncode == 0 and head.stdout.strip() != CORE:
        raise ValueError('Existing core is not the target pin')
    if head.returncode != 0:
        run(['git', '-C', str(core), 'fetch', '--depth=1', 'origin',
             'refs/tags/' + BRAVE_TAG + ':refs/tags/' + BRAVE_TAG])
        if output(['git', '-C', str(core), 'rev-parse', BRAVE_TAG]) != BRAVE_TAG_OBJECT:
            raise ValueError('Official tag object mismatch')
        if output(['git', '-C', str(core), 'rev-parse', BRAVE_TAG + '^{commit}']) != CORE:
            raise ValueError('Fetched core pin mismatch')
        run(['git', '-C', str(core), 'checkout', '--detach', CORE])
    if output(['git', '-C', str(core), 'rev-parse', 'HEAD']) != CORE:
        raise ValueError('Core checkout not at requested revision')
    if output(['git', '-C', str(core), 'diff', 'HEAD', '--name-only']):
        raise ValueError('Source acquire cannot overwrite modified core')
    env = dict(os.environ)
    store = root / '.sandium/pnpm-store'
    store.mkdir(parents=True, exist_ok=True)
    # Command-local configuration, never mutates the user's global pnpm config.
    env['npm_config_store_dir'] = str(store)
    env['DEPOT_TOOLS_UPDATE'] = '0'
    configure_remote(core, env)
    receipt = root / '.sandium-source-synced.json'
    receipt.unlink(missing_ok=True)
    run(['pnpm', 'run', 'init', '--target_os=android', '--target_arch=arm64', '--no-history'], cwd=core, env=env)
    proof = verify(root, require_receipt=False)
    (root / '.sandium-source-synced.json').write_text(json.dumps(proof, indent=2) + '\n')
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('acquire', 'verify'))
    parser.add_argument('--root', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps((acquire if args.phase == 'acquire' else verify)(args.root), sort_keys=True))
