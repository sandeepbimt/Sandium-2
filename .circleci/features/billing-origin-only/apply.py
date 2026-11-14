#!/usr/bin/env python3
"""Feature-local exact transformations for pinned Android Billing removal."""
import argparse,json
from pathlib import Path
OPS=json.loads(Path(__file__).with_name('operations.json').read_text())
def apply(core):
 staged={}
 for op in OPS:
  p=core/op['path'];s=staged.get(p,p.read_text());old,new=op['old'],op['new']
  count=s.count(old)
  if count:
   if count!=op.get('count',1):raise RuntimeError(f"billing source drift: {op['path']} {op['anchor'][:80]}")
   s=s.replace(old,new)
  elif new and new in s:pass
  elif not new and op['anchor'] not in s:pass
  else:raise RuntimeError(f"billing unknown composed source: {op['path']} {op['anchor'][:80]}")
  staged[p]=s
 for p,s in staged.items():p.write_text(s)
 print(f"SANDIUM_BILLING_ORIGIN_ONLY=APPLIED files={len(staged)}")
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);a=p.parse_args();apply(a.core)
