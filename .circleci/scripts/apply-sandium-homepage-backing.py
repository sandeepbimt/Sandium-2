#!/usr/bin/env python3
"""Pinned homepage-only backing candidate; validate all inputs before writes."""
import argparse,json,subprocess
from pathlib import Path
PATCHES=json.loads((Path(__file__).resolve().parents[1]/'features/homepage-surround/backing.json').read_text())
PIN='d331de35ca8ab1358c7a17e4bd41627d55eaef51'
def plan(root):
    changes={}
    for p in PATCHES:
        path=root/p['path'];s=changes.get(path,path.read_text());a=p['old'];b=p['new']
        if s.count(b)==1 and a not in s.replace(b,'',1):
            changes[path]=s;continue
        if s.count(a)!=1 or b in s:raise RuntimeError('home backing anchor mismatch: '+p['path']+' '+a[:50])
        changes[path]=s.replace(a,b,1)
    return changes
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--apply',action='store_true');a=p.parse_args()
    if subprocess.check_output(['git','-C',str(a.source),'rev-parse','HEAD'],text=True).strip()!=PIN:raise RuntimeError('Chromium pin mismatch')
    result=plan(a.source)
    if a.apply:
        for path,text in result.items():path.write_text(text)
    print('HOME_BACKING='+('APPLIED' if a.apply else 'CHECKED'))
