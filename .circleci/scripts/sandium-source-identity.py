"""Reviewed paired source identities; no cross-version mixing or revision fallback."""
import subprocess
from pathlib import Path
PAIRS = (
    ('d331de35ca8ab1358c7a17e4bd41627d55eaef51', '44a84b1f89d9a35287289d6a3d493e362f5a5123'),
    ('52bdd21723d5db0c9ab11716d38feac74828cf84', 'bd6d26d1bced03c17a98baa86d2cd3425d543d1b'),
)
def verify(source):
    root=Path(source)
    pair=tuple(subprocess.check_output(['git','-C',str(p),'rev-parse','HEAD'],text=True).strip()
               for p in (root,root/'brave'))
    if pair not in PAIRS:raise ValueError('Unreviewed or mixed Sandium source identity')
    return pair
