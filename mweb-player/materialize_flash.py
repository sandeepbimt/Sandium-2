"""Apply the reviewed Home navigation backing mitigation to a local RawS tree."""
import argparse
import json
from pathlib import Path

import flash_mitigation as flash
import seal

ROOT = Path(__file__).resolve().parents[1]


def make_plan(base, preimages):
    def read(path):
        return seal.git('show', base + ':' + path)
    original = read(seal.RECIPE)
    prior = json.loads(original)['files']
    owners = {path: expected for path, expected in flash.OWNERS.items()
              if path in prior}
    tracked = {path: (expected, (preimages / path).read_bytes())
               for path, expected in flash.OWNERS.items() if path not in prior}
    outputs = seal.plan(read, owners=owners, man=seal.digest(original),
                        proof=seal.digest(read(seal.ADMISSION)), edit=flash.transform,
                        tracked=tracked)
    return read, outputs


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--preimages', type=Path, required=True)
    p.add_argument('--write', action='store_true')
    args = p.parse_args()
    base = seal.git('rev-parse','HEAD').decode().strip()
    read, out = make_plan(base, args.preimages)
    for path, data in sorted(out.items()):
        print(seal.digest(data), path)
    if not args.write:
        return
    if Path.cwd().resolve() != ROOT:
        raise ValueError('must run in the local review checkout')
    for path, data in out.items():
        target = ROOT / path
        if target.is_symlink():
            raise ValueError('unexpected symlink: ' + path)
        if path.startswith(seal.IMAGE):
            if target.exists() and target.read_bytes() != data:
                raise ValueError('postimage collision: ' + path)
        elif target.read_bytes() != read(path):
            raise ValueError('metadata differs from verified base: ' + path)
    for path, data in out.items():
        (ROOT / path).write_bytes(data)


if __name__ == '__main__':
    main()
