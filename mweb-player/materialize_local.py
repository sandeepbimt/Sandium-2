"""Materialize the reviewed local #1514 trial against the exact baseline tree.

Uses immutable Git blobs, not the working copy, for all original bytes.
No build, checkpoint, network or release/CI preset changes.
"""
import argparse
from pathlib import Path

import glue
import seal
import xmaza_candidate as xmaza

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ('xmaza', 'combined')


def read_at_base(path):
    tree = seal.git('rev-parse', seal.BASE_TREE + '^{tree}').decode().strip()
    if tree != seal.BASE_TREE:
        raise ValueError('expected exact #1514 root tree')
    return seal.git('show', f'{tree}:{path}')


def plan(target, preimages=None):
    if target not in TARGETS:
        raise ValueError('unknown local trial')
    if target == 'combined' and not getattr(glue, 'USES_COMMIT_POLICY', False):
        raise ValueError('refusing the unverified post-navigation-only YouTube hook')
    owners = {xmaza.POLICY: xmaza.PINNED}
    tracked = {}
    if target == 'combined':
        new = glue.NEW_TRACKED
        owners.update({name: sha for name, sha in glue.OWNERS.items() if name not in new})
        if new and preimages is None:
            raise ValueError('provide the pinned Chromium preimage root')
        for path, sha in new.items():
            tracked[path] = (sha, (preimages / path).read_bytes())

    def edit(name, old):
        return xmaza.transform_policy(old) if name == xmaza.POLICY else glue.transform(name, old)

    return seal.plan(read_at_base, owners=owners, edit=edit, tracked=tracked)


def materialize(target, write=False, preimages=None):
    result = plan(target, preimages)
    for name, data in sorted(result.items()):
        print(seal.digest(data), name)
    if not write:
        return
    if Path.cwd().resolve() != ROOT:
        raise ValueError('run with --write only from the isolated trial checkout root')
    # Reject dirty, partially updated, or divergent active overlay metadata.
    xmaza_only = plan('xmaza') if target == 'combined' else {}
    destinations = {}
    for name, new in result.items():
        dest = ROOT / name
        if dest.is_symlink():
            raise ValueError('unexpected symlink: ' + name)
        if name.startswith(seal.IMAGE):
            if dest.exists() and dest.read_bytes() != new:
                raise ValueError('existing postimage differs: ' + name)
        elif dest.read_bytes() not in (read_at_base(name), xmaza_only.get(name)):
            raise ValueError('active metadata differs from base: ' + name)
        destinations[dest] = new
    for dest, new in destinations.items():
        if not dest.exists() or dest.read_bytes() != new:
            dest.write_bytes(new)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', choices=TARGETS)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('--preimages', type=Path)
    args = parser.parse_args()
    materialize(args.target, args.write, args.preimages)
