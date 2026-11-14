#!/usr/bin/env python3
"""Feature-local exact News transformations, composed after other removals."""
import argparse,json
from pathlib import Path
OPS=json.loads(Path(__file__).with_name('operations.json').read_text())
def apply(core):
    staged={}
    for op in OPS:
        p=core/op['path']; s=staged.get(p,p.read_text());old,new=op['old'],op['new']
        count=s.count(old)
        if count:
            if count!=op.get('count',1):raise RuntimeError(f"News source drift: {op['path']} {op['anchor'][:100]}")
            s=s.replace(old,new)
        elif new and new in s:pass
        elif not new and op['anchor'] not in s:pass
        else:raise RuntimeError(f"News unknown composed source: {op['path']} {op['anchor'][:100]}")
        staged[p]=s
    for p,s in staged.items():p.write_text(s)
    print('SANDIUM_NEWS_REMOVAL=APPLIED files=16 require enable_brave_news=false')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);apply(p.parse_args().core)
