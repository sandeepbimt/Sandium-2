#!/usr/bin/env python3
"""Apply the reviewed native-home wallpaper owner and matching toolbar paint together."""
import argparse, importlib.util, subprocess
from pathlib import Path
HERE = Path(__file__).resolve().parent

def module(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

backing = module('apply-sandium-homepage-backing')
paint = module('apply-sandium-homepage-surround')

def compose(source):
    # Plans validate every anchor before any output is written; owner and paint
    # target disjoint classes, so neither reads a partly updated other component.
    owner = backing.plan(source)
    consumer = paint.plan(source)
    if set(owner) & set(consumer):
        raise RuntimeError('Homepage owner and paint scopes unexpectedly overlap')
    return {**owner, **consumer}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    source = args.source.resolve()
    if subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip() != backing.PIN:
        raise RuntimeError('Chromium pin mismatch')
    result = compose(source)
    if not args.verify_only:
        for path, text in result.items():
            path.write_text(text)
    if any(path.read_text() != text for path, text in result.items()):
        raise RuntimeError('Homepage backing and paint verification mismatch')
    print('HOMEPAGE_BACKING_AND_SURROUND=VERIFIED')

if __name__ == '__main__':
    main()
