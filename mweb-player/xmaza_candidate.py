"""Produce a review-only xmaza CSS overlay from the exact #1514 policy bytes."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / 'raws-adblock/production-restore-recipe.json'
POLICY = 'components/sandium_adblock/policy.h'
POSTIMAGES = ROOT / 'raws-adblock/production-postimages'
SELECTOR = '.happy-under-player-mobile:not(:has(video,audio,iframe,form,[role="dialog"]))'
RULE = 'xmaza.tv##' + SELECTOR
PINNED = 'd9b6eb9856d510a395c8d521ed3b284d4deaa86254360e867a6344ef1ae55a2c'

def transform_policy(base):
    if hashlib.sha256(base).hexdigest() != PINNED:
        raise ValueError('unexpected #1514 incident-policy bytes')
    anchor = b'\n)raws";'
    if base.count(anchor) != 1:
        raise ValueError('unexpected filter-list boundary')
    return base.replace(anchor, (
        '\n! Mobile under-player wrapper. Preserve frames, media, forms and dialogs.\n'
        + RULE).encode() + anchor, 1)

def candidate():
    return transform_policy((POSTIMAGES / PINNED).read_bytes())

if __name__ == '__main__':
    import sys
    sys.stdout.buffer.write(candidate())
