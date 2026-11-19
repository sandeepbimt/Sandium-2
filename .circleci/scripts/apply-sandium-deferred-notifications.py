#!/usr/bin/env python3
"""Exact-source, idempotent two-owner deferred notification handshake."""
import argparse,json
from pathlib import Path
FEATURE=Path(__file__).resolve().parents[1]/'features'/'deferred-notifications'
def plan(src):
    staged={}
    for patch in json.loads((FEATURE/'patches.json').read_text()):
        path=src/patch['path'];text=staged.get(path)
        if text is None:text=path.read_text()
        if patch['new'] in text:
            if text.count(patch['new'])!=1:raise ValueError('duplicate applied anchor: '+str(path))
        elif text.count(patch['old'])==1:text=text.replace(patch['old'],patch['new'],1)
        else:raise ValueError('missing/ambiguous source anchor: '+str(path))
        staged[path]=text
    return staged

def verify(src):
    for item in json.loads((FEATURE/'patches.json').read_text()):
        text=(src/item['path']).read_text()
        if text.count(item['new']) != 1:
            raise ValueError('missing/duplicate applied anchor: '+item['path'])
    print('SANDIUM_DEFERRED_NOTIFICATIONS_VERIFY=PASS')

def apply(src):
    staged=plan(src)  # No mutation until every owner validates.
    for path,text in staged.items():
        if path.read_text()!=text:path.write_text(text)
    if any(path.read_text()!=text for path,text in staged.items()):raise RuntimeError('write verification failed')
    print('SANDIUM_DEFERRED_NOTIFICATIONS=PASS owners='+str(len(staged)))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--src',type=Path,required=True)
    parser.add_argument('--verify-only',action='store_true')
    args=parser.parse_args()
    (verify if args.verify_only else apply)(args.src)
