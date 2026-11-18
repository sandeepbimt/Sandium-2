"""Plan scoped native Settings motion restoration, preserving Sandium theme.

Reversal pairs are exact forward-transform postimages. The older per-view fade
is deliberately NOT restored. Unused packaged fade resources are inert and stay
for byte-exact journal rollback; no source-set or resource removal is necessary.
"""
import json
from pathlib import Path
PAIRS=json.loads(Path(__file__).with_name('settings-reversal.json').read_text())

def transform(path,text):
    for before,after in reversed(PAIRS[path]):
        if text.count(after)!=1:
            raise RuntimeError('Native Settings reversal anchor mismatch: '+path+' '+after[:70])
        text=text.replace(after,before,1)
    for marker in ('SANDIUM_SETTINGS_FADE_V1','SANDIUM_SETTINGS_MOTION','sandiumFadeIn(',
                   'sandiumFadeOut(','sandiumConfigureWindowFade('):
        if marker in text:
            raise RuntimeError('Residual custom Settings motion: '+path+' '+marker)
    return text

def plan(root):
    # Return only planned text. The parent transaction validates every source
    # before journaling/writing, preserving its all-or-nothing failure contract.
    return {root/p:transform(p,(root/p).read_text()) for p in PAIRS}
