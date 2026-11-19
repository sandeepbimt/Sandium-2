#!/usr/bin/env python3
"""Source-journalled DNS overlay. Restore before pinned source reset/replay."""
import argparse,importlib.util,json
from pathlib import Path
HERE=Path(__file__).parent
JOURNAL='.sandium-secure-dns-source.json'
def load(name):
 s=importlib.util.spec_from_file_location('dns_'+name,HERE/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def plan(root):
 output={}
 for name in ('default_mode','adapter'):
  edits=load(name).plan(root)
  if output.keys()&edits.keys():raise ValueError('DNS ownership collision')
  output.update(edits)
 return output

def execute(root,verify=False,off=False):
 root=Path(root);journal=root/JOURNAL
 state=json.loads(journal.read_text()) if journal.exists() else None
 if state:
  if state.get('schema')!=1:raise ValueError('DNS journal schema')
  for rel,item in state['files'].items():
   if Path(rel).is_absolute() or '..' in Path(rel).parts:raise ValueError('DNS journal path')
   file=root/rel;current=file.read_text() if file.exists() else None
   if current not in (item['before'],item['after']):raise ValueError('DNS source conflict: '+rel)
 if off:
  if not state:return 0
  for rel,item in state['files'].items():
   file=root/rel
   if item['before'] is None:
    if file.exists():file.unlink()
   else:file.write_text(item['before'])
  journal.unlink();return len(state['files'])
 result=plan(root)
 if state and set(state['files'])!={str(p.relative_to(root)) for p in result}:raise ValueError('DNS inventory changed')
 if verify:
  if any(not p.exists() or p.read_text()!=value for p,value in result.items()):raise ValueError('DNS overlay missing')
  return len(result)
 if not state:
  originals={str(p.relative_to(root)):(p.read_text() if p.exists() else None) for p in result}
  if any(originals[str(p.relative_to(root))]==value for p,value in result.items()):raise ValueError('DNS postimage without journal')
  state={'schema':1,'files':{str(p.relative_to(root)):{'before':originals[str(p.relative_to(root))],'after':value} for p,value in result.items()}}
  tmp=journal.with_suffix('.tmp');tmp.write_text(json.dumps(state));tmp.replace(journal)
 for p,value in result.items():p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value)
 return len(result)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('src',type=Path);g=p.add_mutually_exclusive_group();g.add_argument('--off',action='store_true');g.add_argument('--verify-only',action='store_true');a=p.parse_args();print('SANDIUM_SECURE_DNS_PASS',execute(a.src,a.verify_only,a.off))
