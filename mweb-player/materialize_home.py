"""Prepare the exact local manual-shortcut overlay. No CI or network actions."""
import argparse
from pathlib import Path

import manual_home_shortcuts as home
import seal

BASE = 'bc8fb1629eb4be56b3abbb6980ed1a652b9bbadc'
BASE_MAN = '4e75d55dfa00f37b80a0d64715c2434c9554473ecaabc40c8a65c637c9130b7c'
ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return seal.git('show', BASE + ':' + path)


def plan(preimages):
    tracks = {path: (sha, (preimages/path).read_bytes())
              for path, sha in home.OWNERS.items()}
    return seal.plan(read, owners={}, man=BASE_MAN,
                     proof=seal.digest(read(seal.ADMISSION)),
                     edit=home.transform, tracked=tracks)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--preimages', type=Path, required=True)
    p.add_argument('--write', action='store_true')
    args = p.parse_args()
    outputs = plan(args.preimages)
    for path, data in sorted(outputs.items()):
        print(seal.digest(data), path)
    if not args.write:
        return
    if Path.cwd().resolve() != ROOT or seal.git('rev-parse', 'HEAD').decode().strip() != BASE:
        raise ValueError('must be based on the sealed local #1515 equivalent')
    for path, data in outputs.items():
        dest = ROOT / path
        if dest.is_symlink():
            raise ValueError('unexpected symlink')
        if path.startswith(seal.IMAGE):
            if dest.exists() and dest.read_bytes() != data:
                raise ValueError('postimage collision')
        elif dest.read_bytes() != read(path):
            raise ValueError('overlay metadata differs from the base')
    for path, data in outputs.items():
        (ROOT / path).write_bytes(data)


if __name__ == '__main__':
    main()
