#!/usr/bin/env python3
"""Apply after routing, localized loader and eligibility bridge; feature stays off."""
import argparse,importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('routing_overlay',HERE/'apply.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
RECEIPT='.sandium-ubo-startup-receipt.json'
def plan(core):
 out={}
 def edit(name,old,new):
  s=out.get(name,(core/name).read_bytes()).decode();out[name]=m.edit(s,old,new).encode()
 for src,dest in [('startup.cc','sandium_ubo_startup.cc'),('startup.h','sandium_ubo_startup.h')]:
  out['browser/extensions/'+dest]=(HERE/src).read_bytes()
 edit('browser/sources.gni','brave_chrome_browser_sources = [','brave_chrome_browser_sources = [\n  "//brave/browser/extensions/sandium_ubo_startup.cc",\n  "//brave/browser/extensions/sandium_ubo_startup.h",')
 edit('browser/sources.gni','brave_chrome_browser_deps = [','brave_chrome_browser_deps = [\n  "//brave/browser/extensions/api:sandium_ubo_bridge",\n  "//brave/components/sandium_ubo:identity",')
 name='browser/brave_content_browser_client.cc'
 edit(name,'#include "brave/browser/brave_content_browser_client.h"','#include "brave/browser/brave_content_browser_client.h"\n#include "brave/browser/extensions/sandium_ubo_startup.h"')
 edit(name,'  ChromeContentBrowserClient::CreateThrottlesForNavigation(registry);','  sandium_ubo::AddStartupNavigationThrottle(registry);\n  ChromeContentBrowserClient::CreateThrottlesForNavigation(registry);')
 name='chromium_src/chrome/browser/extensions/component_loader_factory.cc'
 edit(name,'#include "brave/components/sandium_ubo/identity.h"','#include "brave/components/sandium_ubo/identity.h"\n#include "brave/components/sandium_ubo_routing/routing.h"')
 edit(name,'    materialization_pending_ = false;','    materialization_pending_ = false;\n    if (sandium_ubo::IsRuntimeStartupAborted(profile_)) return;')
 edit(name,'        materialization_pending_)','        materialization_pending_ || sandium_ubo::IsRuntimeStartupAborted(profile_))')
 edit('browser/extensions/resources.gni','    "//brave/components/sandium_ubo:identity",','    "//brave/components/sandium_ubo:identity",\n    "//brave/components/sandium_ubo_routing",')
 return out

def apply(core):
 r=core/RECEIPT
 if r.exists():m.transition(core,json.loads(r.read_text()),'after');return
 receipt={}
 for name,b in plan(core).items():
  p=m.path(core,name)
  if name.endswith(('sandium_ubo_startup.cc','sandium_ubo_startup.h')) and p.exists():raise ValueError('Unowned startup source')
  receipt[name]={'before':m.encode(p.read_bytes() if p.exists() else None),'after':m.encode(b)}
 m.write(r,json.dumps(receipt,sort_keys=True).encode());m.transition(core,receipt,'after')
def reset(core):
 r=core/RECEIPT
 if not r.exists():return
 m.transition(core,json.loads(r.read_text()),'before');r.unlink()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);p.add_argument('--reset',action='store_true');a=p.parse_args();(reset if a.reset else apply)(a.core.resolve())
