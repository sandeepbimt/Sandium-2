#!/usr/bin/env python3
"""Integration-owned exact subscription snapshot; never rewrites upstream ZIP."""
import argparse,hashlib,importlib.util,json,re,runpy
from pathlib import Path
from xml.sax.saxutils import escape
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
receipt=load('offline_receipt',HERE.parent/'routing/apply.py')
loader=load('offline_inventory',HERE.parent/'loader/apply.py')
RECEIPT='.sandium-ubo-offline-lists.json'
def verify():
 lock=json.loads((HERE/'sources.lock.json').read_text())
 expected=[url for url,_ in runpy.run_path(str(ROOT/'.circleci/scripts/apply-sandium-filter-subscriptions.py'))['FILTERS']]
 if [x['url'] for x in lock['subscriptions']]!=expected:raise ValueError('Product subscription catalogue drift')
 if len(expected)!=30:raise ValueError('Unexpected subscription count')
 required={x['url'] for x in lock['subscriptions'] if not x['upstream_local'] and not x.get('unavailable')}
 if required!={x['url'] for x in lock['files']}:raise ValueError('Offline coverage metadata mismatch')
 for x in lock['files']:
  p=HERE/x['file']
  if p.is_symlink() or not p.is_file() or len(p.read_bytes())!=x['size'] or hashlib.sha256(p.read_bytes()).hexdigest()!=x['sha256']:raise ValueError('Locked subscription integrity mismatch')
  if re.search(rb'^!#include\s+',p.read_bytes(),re.M):raise ValueError('Snapshot now requires unbundled includes: refresh audited lock')
 return lock

def plan(core):
 lock=verify();out={};prefix='components/sandium_ubo/';asset=prefix+'sandium_ubo/'
 sources={};symbols=[]
 for i,f in enumerate(lock['files']):
  path='assets/sandium-offline/'+f['sha256']+'.txt';out[asset+path]=(HERE/f['file']).read_bytes()
  sources[f['url']]={'path':path,'sha256':f['sha256']}
  symbols.append((path,'IDR_SANDIUM_UBO_OFFLINE_'+str(i)))
 seed=(HERE/'seed.js').read_text()+"\nexport const withSandiumOfflineSource = (urls,key,ready) => prependOfflineSource(urls,key,ready, "+json.dumps(sources,sort_keys=True)+");\n"
 out[asset+'js/sandium-offline-lists.js']=seed.encode();symbols.append(('js/sandium-offline-lists.js','IDR_SANDIUM_UBO_OFFLINE_HELPER'))
 name=asset+'js/assets.js';s=(core/name).read_text()
 s="import {withSandiumOfflineSource} from './sandium-offline-lists.js';\n"+s
 s=receipt.edit(s,'    const contentURLs = getContentURLs(assetKey, options);',
  '    const contentURLs = withSandiumOfflineSource(\n        getContentURLs(assetKey, options), assetKey, µb.readyToFilter);')
 out[name]=s.encode()
 grd=(core/(prefix+'resources.grd')).read_text();mapping=(core/(prefix+'resource_map.h')).read_text()
 for path,symbol in symbols:
  grd=receipt.edit(grd,'</includes>',f'<include name="{symbol}" file="sandium_ubo/{escape(path)}" type="BINDATA" />\n</includes>')
  mapping=receipt.edit(mapping,'\n};',f'\n    {{"sandium_ubo/{path}", {symbol}}},\n}};')
 out[prefix+'resources.grd']=grd.encode();out[prefix+'resource_map.h']=mapping.encode()
 disk=[]
 for path,symbol in re.findall(r'\{"sandium_ubo/([^"\n]+)", (IDR_SANDIUM_UBO_[A-Z0-9_]+)\}',mapping):
  name=asset+path;b=out[name] if name in out else (core/name).read_bytes()
  disk.append('    {"'+path+'", '+symbol+', "'+hashlib.sha256(b).hexdigest()+'"},')
 if len(disk)>700:raise ValueError('Resource reservation overflow')
 out[prefix+'disk_resources.h']=loader.disk_header(disk).encode()
 return out

def apply(core):
 r=core/RECEIPT
 if r.exists():receipt.transition(core,json.loads(r.read_text()),'after');return
 changes=plan(core);state={}
 for n,b in changes.items():
  p=receipt.path(core,n)
  if ('/assets/sandium-offline/' in n or n.endswith('/sandium-offline-lists.js')) and p.exists():raise ValueError('Unowned offline payload')
  state[n]={'before':receipt.encode(p.read_bytes() if p.exists() else None),'after':receipt.encode(b)}
 receipt.write(r,json.dumps(state,sort_keys=True).encode());receipt.transition(core,state,'after')
def reset(core):
 r=core/RECEIPT
 if r.exists():
  receipt.transition(core,json.loads(r.read_text()),'before')
  directory=core/'components/sandium_ubo/sandium_ubo/assets/sandium-offline'
  if directory.exists():directory.rmdir()
  r.unlink()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);p.add_argument('--reset',action='store_true');a=p.parse_args();(reset if a.reset else apply)(a.core.resolve())
