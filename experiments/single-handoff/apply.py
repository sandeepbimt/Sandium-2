#!/usr/bin/env python3
"""Transactional, fail-closed candidate over the separately restored native profile.

Held/off by default. Restore this journal BEFORE restoring native-navigation.
"""
import argparse
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = '.sandium-single-handoff-state.json'
PIN = 'd331de35ca8ab1358c7a17e4bd41627d55eaef51'
BRAVE_PIN = '44a84b1f89d9a35287289d6a3d493e362f5a5123'


def source_identity(root):
    path=HERE.parents[1]/'.circleci/scripts/sandium-source-identity.py'
    spec=importlib.util.spec_from_file_location('handoff_source_identity',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.verify(root)

def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def recipe():
    digest = hashlib.sha256()
    # Fixture anchors are executable recipe inputs too; changing them must not
    # silently reuse an earlier journal's output.
    for path in sorted(HERE.rglob('*')):
        if path.is_file() and path.suffix in ('.py', '.java', '.cc', '.h', '.gn', '.gni', '.gz'):
            digest.update(str(path.relative_to(HERE)).encode())
            digest.update(b'\0')
            digest.update(path.read_bytes())
    return digest.hexdigest()


def proposed(root):
    # The enabled candidate must never silently build only the old partial stages.
    # Explicit profile activation plans the reviewed whole source set.
    path = HERE / 'candidate_plan.py'
    if not path.exists():
        raise RuntimeError('Incomplete candidate: missing whole source planner')
    spec = importlib.util.spec_from_file_location('single_handoff_candidate', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.plan(root)


def plan(root, enabled, identity=None):
    state_path = root / STATE
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if identity is not None and tuple(state.get('source_identity', (PIN, BRAVE_PIN))) != tuple(identity):
            raise RuntimeError('Candidate journal source identity mismatch')
        if state.get('schema') not in (1, 2):
            raise RuntimeError('Unknown candidate journal schema')
        if enabled and state.get('recipe') != recipe():
            raise RuntimeError('Candidate recipe changed; restore before replay')
        changes = {}
        for relative, item in state['files'].items():
            path = (root / relative).resolve()
            if not path.is_relative_to(root.resolve()):
                raise RuntimeError('Journal path escapes source')
            before_hash = sha(item['before']) if item['before'] is not None else None
            if before_hash != item['before_sha'] or sha(item['after']) != item['after_sha']:
                raise RuntimeError('Corrupt candidate journal')
            current_hash = sha(path.read_text()) if path.exists() else None
            if current_hash not in (item['before_sha'], item['after_sha']):
                raise RuntimeError('Source changed; refusing destructive restore: ' + relative)
            changes[path] = item['after'] if enabled else item['before']
        return changes, state
    if not enabled:
        return {}, None
    changes = proposed(root)
    state = {'schema': 2, 'recipe': recipe(), 'source_identity': list(identity or (PIN, BRAVE_PIN)), 'files': {}}
    for path, after in changes.items():
        relative = str(path.resolve().relative_to(root.resolve()))
        before = path.read_text() if path.exists() else None
        state['files'][relative] = dict(before=before, after=after, before_sha=sha(before) if before is not None else None, after_sha=sha(after))
    return changes, state


def execute(root, enabled, verify_only=False, identity=None):
    root = root.resolve()
    changes, state = plan(root, enabled, identity)
    if verify_only:
        if any((path.read_text() if path.exists() else None) != value for path, value in changes.items()):
            raise RuntimeError('Candidate verification differs')
        return
    if state is not None:
        temporary = root / (STATE + '.tmp')
        temporary.write_text(json.dumps(state))
        temporary.replace(root / STATE)
    for path, value in changes.items():
        if value is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value)
    if any((path.read_text() if path.exists() else None) != value for path, value in changes.items()):
        raise RuntimeError('Candidate write verification differs')
    if not enabled and state is not None:
        (root / STATE).replace(root / (STATE + '.restored'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--mode', choices=('on', 'off', 'configured'), default='configured')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    enabled = json.loads((HERE / 'profile.json').read_text())['enabled'] if args.mode == 'configured' else args.mode == 'on'
    identity = source_identity(args.source)
    if enabled:
        if not (args.source / '.sandium-native-navigation-state.json').exists():
            raise RuntimeError('Apply native baseline before this candidate')
    execute(args.source, enabled, args.verify_only, identity)
