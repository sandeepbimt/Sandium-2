"""Opt-in outer profile: restore before native replay; verify both journals."""
import argparse
import importlib.util
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

native = load('single_native_composition', HERE.parent/'native-navigation/apply.py')
handoff = load('single_handoff_composition', HERE/'apply.py')


def verify_combined(root):
    handoff.execute(root, True, verify_only=True)
    outer = json.loads((root/handoff.STATE).read_text())
    inner = json.loads((root/native.STATE).read_text())
    if inner.get('schema') != 1 or inner.get('recipe_sha256') != native.recipe_hash():
        raise RuntimeError('Native composition journal or recipe mismatch')
    for relative, entry in inner['files'].items():
        path = (root/relative).resolve()
        if not path.is_relative_to(root.resolve()):
            raise RuntimeError('Native journal path escapes source')
        if native.sha(entry['before']) != entry['before_sha256'] or native.sha(entry['after']) != entry['after_sha256']:
            raise RuntimeError('Corrupt native composition journal')
        expected = entry['after']
        if relative in outer['files']:
            extra = outer['files'][relative]
            if extra['before'] != expected:
                raise RuntimeError('Outer candidate is not based on native postimage: '+relative)
            expected = extra['after']
        if path.read_text() != expected:
            raise RuntimeError('Combined native verification differs: '+relative)


def execute(root, native_enabled, handoff_enabled, verify_only=False):
    root = root.resolve()
    if handoff_enabled and not native_enabled:
        raise RuntimeError('Single-handoff requires native profile; refusing partial configuration')
    if verify_only:
        if handoff_enabled:
            verify_combined(root)
        else:
            if (root/handoff.STATE).exists():
                raise RuntimeError('Outer candidate remains applied while disabled')
            native.execute(root, native_enabled, verify_only=True)
        return
    # Outermost owner must restore first, including every source-reset wrapper.
    handoff.execute(root, False)
    native.execute(root, native_enabled)
    if handoff_enabled:
        handoff.execute(root, True)
        verify_combined(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--mode', choices=('on','off','configured'), default='configured')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    root = args.source.resolve()
    for directory, expected in ((root,native.PIN),(root/'brave',native.BRAVE)):
        if subprocess.check_output(['git','-C',str(directory),'rev-parse','HEAD'],text=True).strip()!=expected:
            raise RuntimeError('Source pin mismatch')
    native_enabled = json.loads((HERE.parent/'native-navigation/profile.json').read_text())['enabled'] if args.mode=='configured' else args.mode=='on'
    handoff_enabled = args.mode!='off' and json.loads((HERE/'profile.json').read_text())['enabled']
    if native_enabled and not (HERE.parent/'native-navigation/geometry.py').exists():
        raise RuntimeError('Native geometry profile missing; refusing partial profile')
    execute(root,native_enabled,handoff_enabled,args.verify_only)
    print('SANDIUM_NATIVE_NAVIGATION='+('ON' if native_enabled else 'OFF')+'; SINGLE_HANDOFF='+('ON' if handoff_enabled else 'OFF'))

if __name__ == '__main__':
    main()
