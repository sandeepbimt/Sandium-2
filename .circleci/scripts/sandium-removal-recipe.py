#!/usr/bin/env python3
"""Ordered compile-exclusion recipe. Reset only declared pinned inputs before UI.
Unchanged outputs may reuse Siso actions; a prior APK never satisfies new revision.
"""
import argparse,hashlib,json,os,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
MANIFEST=ROOT/'.circleci/features/removal-recipe.json'

def load(path=MANIFEST):
 m=json.loads(path.read_text())
 if m['schema']!=1 or len(m['groups'])!=13:raise ValueError('Expected canonical 13-group recipe')
 for key in ('core_restore','chromium_restore'):
  if len(m[key])!=len(set(m[key])):raise ValueError('Duplicate reset path')
  for p in m[key]:
   if Path(p).is_absolute() or '..' in Path(p).parts:raise ValueError('Unsafe reset path')
 return m

def reset(m,core,src,out):
 pending=[]
 for repo,pin,key in [(core,m['brave_pin'],'core_restore'),(src,m['chromium_pin'],'chromium_restore')]:
  actual=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
  if actual!=pin:raise ValueError('Unexpected upstream pin '+str(repo))
  for relative in m[key]:
   data=subprocess.check_output(['git','-C',str(repo),'show',pin+':'+relative])
   pending.append((repo/relative,data))
 # Missing pin/path fails before any restoration, and custom Sandium files are never reset.
 for p,data in pending:p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 # Retired product overrides cannot reach the old preparation GN pass before
 # final dependency surgery has been replayed (Playlist asserts on Android).
 for name in ('args.gn','args_generated.gni'):
  p=out/name
  if p.is_file():
   text=p.read_text()
   for key in m['gn_args']:
    text=re.sub(r'(?m)^\s*'+re.escape(key)+r'\s*=.*\n?','',text)
   p.write_text(text)
 print('SANDIUM_REMOVAL_RESET=PASS files='+str(len(pending)))

def configure_gn(m,out):
 p=out/'args.gn'
 if not p.is_file():raise ValueError('No existing pinned GN args')
 text=p.read_text()
 for key,value in m['gn_args'].items():
  if not re.fullmatch('[a-z][a-z0-9_]*',key) or not isinstance(value,bool):raise ValueError('Invalid GN argument')
  text=re.sub(r'(?m)^\s*'+re.escape(key)+r'\s*=.*\n?','',text)
  text+='\n'+key+' = '+str(value).lower()+'\n'
 p.write_text(text)

def apply(m,core,src,out):
 substitutions={'{core}':str(core),'{src}':str(src),'{out}':str(out),'{repo}':str(ROOT)}
 for step in m['steps']:
  command=[sys.executable,str(ROOT/step['script'])]+[substitutions.get(a,a) for a in step['args']]
  subprocess.run(command,check=True)
 configure_gn(m,out)
 gn=src/'buildtools/linux64/gn'
 if not gn.is_file():raise ValueError('Pinned GN missing')
 # Generation rejects unknown arguments and validates the actual new dependency graph.
 env=dict(os.environ)
 env['PYTHONPATH']=':'.join(str(x) for x in [core/'script',src/'tools/grit/grit/extern',core/'vendor/requests',src/'build',core/'vendor/depot_tools'])+(':'+env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
 subprocess.run([str(gn),'gen',str(out),'--fail-on-unused-args'],cwd=src,env=env,check=True)
 print('SANDIUM_REMOVAL_RECIPE=APPLIED graph_generated=true recipe='+hashlib.sha256(MANIFEST.read_bytes()).hexdigest())

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);p.add_argument('--src',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--phase',choices=['reset','apply'],required=True);a=p.parse_args();m=load()
 if a.phase=='reset':reset(m,a.core,a.src,a.out)
 else:apply(m,a.core,a.src,a.out)
