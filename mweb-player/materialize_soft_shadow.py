"""Seal the validated soft toolbar backdrop edits against exact local RawS inputs."""
import argparse
import json
from pathlib import Path

import seal
import soft_toolbar_shadow as change

BASE = '815e296b76d7aee8dbed7cfc7763e1313c07ffd0'
ROOT = Path(__file__).resolve().parents[1]


def make_plan(preimages):
    def read(path):
        return seal.git('show', BASE + ':' + path)
    prior_recipe = read(seal.RECIPE)
    prior = json.loads(prior_recipe)['files']
    existing = {path: expected for path, expected in change.OWNERS.items() if path in prior}
    tracked = {path: (expected, (preimages / path).read_bytes())
               for path, expected in change.OWNERS.items() if path not in prior}
    return read, seal.plan(read, owners=existing, tracked=tracked, edit=change.transform,
                           man=seal.digest(prior_recipe), proof=seal.digest(read(seal.ADMISSION)))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--preimages', type=Path, required=True)
    p.add_argument('--write', action='store_true')
    args = p.parse_args()
    read, out = make_plan(args.preimages)
    for path, data in sorted(out.items()):
        print(seal.digest(data), path)
    if not args.write:
        return
    if Path.cwd().resolve() != ROOT or seal.git('rev-parse', 'HEAD').decode().strip() != BASE:
        raise ValueError('must run on the exact #1515 follow-up base')
    for name, data in out.items():
        path = ROOT / name
        if path.is_symlink():
            raise ValueError(f'symlink not accepted: {name}')
        if name.startswith(seal.IMAGE):
            if path.exists() and path.read_bytes() != data:
                raise ValueError(f'postimage collision: {name}')
        elif path.read_bytes() != read(name):
            raise ValueError(f'dirty overlay metadata: {name}')
    for name, data in out.items():
        (ROOT / name).write_bytes(data)


if __name__ == '__main__':
    main()
