#!/usr/bin/env python3
"""Ordered compile-exclusion recipe. Reset only declared pinned inputs before UI.
Unchanged outputs may reuse Siso actions; a prior APK never satisfies new revision.
"""
import argparse,hashlib,json,os,re,subprocess,sys,tempfile
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
 for target,patch in m.get('chromium_restore_patches',{}).items():
  if target not in m['chromium_restore'] or not patch.startswith('patches/') or '..' in Path(patch).parts:
   raise ValueError('Invalid pinned Chromium patch replay mapping')
 # Every dark/manual patch input must survive the production reset and the
 # disposable full composition tree, not only the standalone feature fixtures.
 dark=json.loads((ROOT/'.circleci/features/dark-pages/integration-plan.json').read_text())
 for key in ('chromium_restore','core_restore','generated_overwrite'):
  missing=set(dark[key])-set(m[key])
  if missing:raise ValueError('Dark input absent from removal '+key+': '+', '.join(sorted(missing)))
 # Keep typography reset ownership mandatory as well as its standalone tests.
 text=json.loads((ROOT/'.circleci/features/page-text/integration-plan.json').read_text())
 for key in ('chromium_restore','core_restore','generated_overwrite'):
  missing=set(text[key])-set(m[key])
  if missing:raise ValueError('Page text input absent from removal '+key+': '+', '.join(sorted(missing)))
 return m

def restore_payload(m, core_reader, chromium_reader, core_only=False):
 """Compute all raw reset bytes and pinned Brave patch results before live writes.
 Readers fetch exact pinned blobs in production; fixture tests share this path.
 """
 result={'core':{p:core_reader(p) for p in m['core_restore']},
         'chromium':{} if core_only else {p:chromium_reader(p) for p in m['chromium_restore']}}
 if core_only:return result
 with tempfile.TemporaryDirectory(prefix='sandium-reset-preflight-') as temporary:
  stage=Path(temporary)
  for relative,data in result['chromium'].items():
   target=stage/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
  for target,patch in m.get('chromium_restore_patches',{}).items():
   data=core_reader(patch)
   # A declared patch may only affect its declared reset target, never another input.
   paths=re.findall(rb'^\+\+\+ b/(.+)$',data,re.M)
   if paths != [target.encode()]:raise ValueError('Pinned replay patch target mismatch: '+patch)
   command=['git','apply','--whitespace=nowarn','--include='+target]
   subprocess.run(command+['--check','-'],cwd=stage,input=data,check=True,capture_output=True)
   subprocess.run(command+['-'],cwd=stage,input=data,check=True,capture_output=True)
  result['chromium']={p:(stage/p).read_bytes() for p in result['chromium']}
 return result

def reset(m,core,src,out,core_only=False):
 for repo,pin in [(core,m['brave_pin']),(src,m['chromium_pin'])]:
  actual=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
  if actual!=pin:raise ValueError('Unexpected upstream pin '+str(repo))
 def blob(repo,pin,path):return subprocess.check_output(['git','-C',str(repo),'show',pin+':'+path])
 payload=restore_payload(m,lambda p:blob(core,m['brave_pin'],p),lambda p:blob(src,m['chromium_pin'],p),core_only)
 pending=[(repo/relative,data) for repo,key in [(core,'core'),(src,'chromium')] for relative,data in payload[key].items()]
 # All pins, files and Brave patches validated before mutation. An interruption
 # during writes is recovered by the same deterministic reset on the next run.
 for p,data in pending:p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 # Retired product overrides cannot reach the old preparation GN pass before
 # final dependency surgery has been replayed (Playlist asserts on Android).
 for name in (() if core_only else ('args.gn','args_generated.gni')):
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
 p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);p.add_argument('--src',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--phase',choices=['reset','reset-core','apply'],required=True);a=p.parse_args();m=load()
 if a.phase in ('reset','reset-core'):reset(m,a.core,a.src,a.out,core_only=a.phase=='reset-core')
 else:apply(m,a.core,a.src,a.out)
