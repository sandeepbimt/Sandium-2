"""Wire the two manual picker transforms into the exact combined local trial."""
import argparse
from pathlib import Path

import manual_ad_picker as ad
import manual_color as color
import seal

BASE = 'bb6aa374c9f0371d172abe389fd0b989c8686dde'
BASE_MAN = 'a9a4ec3a72e79632b69a669ae9671985a7b382655fe8eb18a93fc251433ca895'
ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return seal.git('show', BASE + ':' + path)


def plan():
    for name in set(ad.OWNERS) & set(color.OWNERS):
        if ad.OWNERS[name] != color.OWNERS[name]:
            raise ValueError('manual transforms disagree on base source')

    def edit(name, before):
        if name in ad.OWNERS:
            before = ad.transform(name, before)
        if name in color.OWNERS:
            before = color.transform(name, before)
        return before

    return seal.plan(read, owners={**ad.OWNERS, **color.OWNERS}, man=BASE_MAN,
                     proof=seal.digest(read(seal.ADMISSION)), edit=edit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    result = plan()
    for name, data in sorted(result.items()):
        print(seal.digest(data), name)
    if not args.write:
        return
    if Path.cwd().resolve() != ROOT or seal.git('rev-parse', 'HEAD').decode().strip() != BASE:
        raise ValueError('write only at the clean #1514 combined trial base')
    for name, data in result.items():
        dest = ROOT / name
        if dest.is_symlink():
            raise ValueError('unexpected symlink: ' + name)
        if name.startswith(seal.IMAGE):
            if dest.exists() and dest.read_bytes() != data:
                raise ValueError('postimage collision')
        elif dest.read_bytes() != read(name):
            raise ValueError('active metadata differs from trial base')
    for name, data in result.items():
        (ROOT / name).write_bytes(data)


if __name__ == '__main__':
    main()
