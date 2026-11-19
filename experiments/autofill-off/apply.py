#!/usr/bin/env python3
"""Reversible external-only Autofill overlay; no profile data migration."""
import argparse,importlib.util,json
from pathlib import Path
JOURNAL='.sandium-external-autofill-source.json'

def load(name):
    s=importlib.util.spec_from_file_location('autofill_'+name,Path(__file__).with_name(name+'.py'))
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def plan(root):
    result={}
    for module in (load('ui'),load('runtime')):
        edits=module.plan(root)
        if result.keys() & edits.keys():raise ValueError('Autofill stage collision')
        result.update(edits)
    return result

def execute(root,verify=False,off=False):
    root=Path(root);journal=root/JOURNAL
    state=json.loads(journal.read_text()) if journal.exists() else None
    if state:
        if state.get('schema')!=1:raise ValueError('Unsupported Autofill journal')
        for rel,item in state['files'].items():
            if Path(rel).is_absolute() or '..' in Path(rel).parts:raise ValueError('Unsafe Autofill journal path')
            if (root/rel).read_text() not in (item['before'],item['after']):
                raise ValueError('Autofill owned source changed; refusing destructive restore: '+rel)
    if off:
        if not state:return 0
        for rel,item in state['files'].items():(root/rel).write_text(item['before'])
        journal.unlink();return len(state['files'])
    result=plan(root) # All exact anchors validated before any source changes.
    if state and set(state['files'])!={str(p.relative_to(root)) for p in result}:
        raise ValueError('Autofill journal inventory changed')
    if verify:
        if any(p.read_text()!=s for p,s in result.items()):raise ValueError('Autofill overlay missing')
    else:
        if not state:
            if any(p.read_text()==s for p,s in result.items()):
                raise ValueError('Autofill postimage without journal; restore pinned inputs before adoption')
            state={'schema':1,'files':{str(p.relative_to(root)):{'before':p.read_text(),'after':s} for p,s in result.items()}}
            # Durable preimages precede writes so interrupted application remains reversible.
            tmp=journal.with_suffix('.tmp');tmp.write_text(json.dumps(state));tmp.replace(journal)
        for p,s in result.items():p.write_text(s)
    return len(result)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('src',type=Path);g=p.add_mutually_exclusive_group();g.add_argument('--verify-only',action='store_true');g.add_argument('--off',action='store_true');a=p.parse_args()
    print('SANDIUM_EXTERNAL_ONLY_AUTOFILL=PASS files='+str(execute(a.src,a.verify_only,a.off)))
