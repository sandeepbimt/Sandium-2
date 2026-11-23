#!/usr/bin/env python3
"""Construct a reviewable, fully sealed child of #1514 in a complete local clone.
Read only Git objects. Never change a checkout/index, run hooks, fetch, or push.
Without --commit print the planned file list and hashes; do not write anything.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from glue import OWNERS, once, transform

BASE = '1bdd41e4c478459ca6b86b1717dac601e17c832b'
BASE_TREE = 'e602433276fbe78e975347f8ac51362a848edc71'
RECIPE = 'raws-adblock/production-restore-recipe.json'
ADMISSION = 'raws-adblock/port1442/admission.json'
IMAGE = 'raws-adblock/production-postimages/'
FEATURE = 'tools/restore_only_feature.py'
PORT = 'tools/restore_only_port1442.py'
MAN = '743271dd5252003ecd18a25596c13deb95e48d9eca6a70323e9e05c5f8cd0824'
PROOF = 'eeb42170b6121473beefac392c262df710215a1b56a3703fdde1374de32a3531'
REF = 'refs/heads/local/raws-1514-mweb-sealed'

def git(*args, data=None, env=None):
    return subprocess.check_output(['git','--no-replace-objects','-c','core.hooksPath=/dev/null',*args],input=data,env=env)

def digest(data): return hashlib.sha256(data).hexdigest()

def plan(read, owners=OWNERS, man=MAN, proof=PROOF, edit=transform, tracked=None):
    tracked = tracked or {}
    recipe, admission = read(RECIPE), read(ADMISSION)
    if digest(recipe) != man or digest(admission) != proof:
        raise ValueError('baseline recipe/proof SHA-256 mismatch')
    m, a = json.loads(recipe), json.loads(admission)
    if a['manifest_sha256'] != man: raise ValueError('admission does not identify base recipe')
    out={}; text=recipe.decode()
    for name, expected in owners.items():
        before=read(IMAGE+expected)
        if digest(before) != expected or m['files'][name]['after_sha256'] != expected:
            raise ValueError('wrong production source: '+name)
        after=edit(name,before); new=digest(after)
        if new==expected: raise ValueError('empty product edit: '+name)
        out[IMAGE+new]=after
        old_anchor=f'    "{name}": {{\n      "after_sha256": "{expected}"'
        text=once(text,old_anchor,old_anchor.replace(expected,new));m['files'][name]['after_sha256']=new
    if json.loads(text) != m: raise ValueError('unexpected manifest change')
    for name, before in tracked.items():
        if name in m['files']:
            raise ValueError('new tracked owner collides: ' + name)
        expected, original = before
        if digest(original) != expected:
            raise ValueError('wrong pinned Chromium preimage: ' + name)
        after = edit(name, original)
        new = digest(after)
        if new == expected:
            raise ValueError('empty tracked edit: ' + name)
        out[IMAGE+new] = after
        m['files'][name] = {'before_sha256': expected, 'after_sha256': new}
    if tracked:
        text = json.dumps(m, indent=2, sort_keys=True) + '\n'
    out[RECIPE]=text.encode(); new_man=digest(out[RECIPE])
    out[ADMISSION]=once(admission.decode(),f'"manifest_sha256": "{man}"',f'"manifest_sha256": "{new_man}"').encode()
    a['manifest_sha256']=new_man
    if json.loads(out[ADMISSION]) != a: raise ValueError('unexpected admission change')
    if tracked:
        extra_tracked = set(a['extra_tracked'])
        if extra_tracked.intersection(tracked):
            raise ValueError('new tracked owner already in admission')
        a['extra_tracked'] = sorted(extra_tracked.union(tracked))
        out[ADMISSION] = (json.dumps(a, indent=2, sort_keys=True) + '\n').encode()
    for file,var,old,new in [(FEATURE,'APPROVED_UI_MANIFEST_SHA256',man,new_man),(PORT,'ADMISSION_SHA256',proof,digest(out[ADMISSION]))]:
        out[file]=once(read(file).decode(),f"{var} = '{old}'",f"{var} = '{new}'").encode()
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--commit',action='store_true'); args=p.parse_args()
    tip=git('rev-parse','HEAD').decode().strip()
    if git('rev-parse','HEAD^').decode().strip()!=BASE or git('rev-parse',BASE+'^{tree}').decode().strip()!=BASE_TREE:
        raise ValueError('run at the unsealed source candidate, direct child of #1514')
    changed=git('diff-tree','-r','--no-renames','--name-only','--no-commit-id',BASE,tip).decode().splitlines()
    if not changed or any(not n.startswith('mweb-player/') for n in changed):
        raise ValueError('unrelated candidate changes')
    # The script that produces bytes is reviewed source, not an arbitrary dirty working copy.
    for f in ('player.js','glue.py','seal.py'):
        if Path(__file__).with_name(f).read_bytes()!=git('show',tip+':mweb-player/'+f):
            raise ValueError('dirty sealer input: '+f)
    out=plan(lambda name: git('show',BASE+':'+name))
    for name,data in sorted(out.items()): print(digest(data),name)
    if not args.commit: return
    with tempfile.TemporaryDirectory() as tmp:
        env=dict(os.environ,GIT_INDEX_FILE=str(Path(tmp)/'index'))
        git('read-tree',tip,env=env)
        for path,data in sorted(out.items()):
            blob=git('hash-object','-w','--stdin',data=data).decode().strip()
            git('update-index','--add','--cacheinfo','100644',blob,path,env=env)
        tree=git('write-tree',env=env).decode().strip()
        sealed=git('commit-tree',tree,'-p',BASE,'-m','Guard MWEB player ad metadata without filtering media [skip ci]').decode().strip()
        git('update-ref',REF,sealed,'0'*40)
        print('new local ref', REF, sealed, 'parent',BASE)

if __name__=='__main__': main()
