#!/usr/bin/env python3
"""Dormant native routing overlay; deliberately not invoked by CI yet."""
import argparse,base64,json,os,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
RECEIPT='.sandium-ubo-routing-receipt.json'
def edit(s,old,new):
 if s.count(old)!=1:raise ValueError('Routing anchor mismatch: '+old[:80])
 return s.replace(old,new,1)
def plan(core):
 result={}
 include='#include "brave/components/sandium_ubo_routing/routing.h"\n'
 entries={
 'browser/net/brave_ad_block_tp_network_delegate_helper.cc':(
 '  OnBeforeURLRequestAdBlockTP(next_callback, ctx);',
 '  if ((!ctx->request_initiator() || ctx->request_initiator()->scheme() != \"chrome-extension\") &&\n      !sandium_ubo::SealAndUseNativeAdEngine(ctx->browser_context()))\n    return net::OK;\n'),
 'browser/net/brave_ad_block_csp_network_delegate_helper.cc':(
 '  if (!response_headers || !ctx->allow_brave_shields() || ctx->allow_ads()) {',
 '  if (ctx->request_url().SchemeIsHTTPOrHTTPS() &&\n      (!ctx->request_initiator() || ctx->request_initiator()->scheme() != \"chrome-extension\") &&\n      !sandium_ubo::SealAndUseNativeAdEngine(ctx->browser_context()))\n    return net::OK;\n'),
 'components/brave_shields/content/browser/domain_block_navigation_throttle.cc':(
 '  content::NavigationHandle* handle = navigation_handle();\n  DCHECK(handle->IsInMainFrame());',
 '  if (navigation_handle()->GetURL().SchemeIsHTTPOrHTTPS() &&\n      !sandium_ubo::SealAndUseNativeAdEngine(\n          navigation_handle()->GetWebContents()->GetBrowserContext()))\n    return PROCEED;\n'),

 }
 for name,(anchor,gate) in entries.items():
  text=(core/name).read_text();result[name]=(include+edit(text,anchor,gate+anchor)).encode()
 # The picker binder is deliberately untouched. Capture filtering ownership on
 # UI, then pass an immutable bool to the existing worker-owned resource service.
 name='browser/brave_content_browser_client.cc';text=(core/name).read_text()
 text=include+edit(text,'void BindCosmeticFiltersResourcesOnTaskRunner(\n','void BindCosmeticFiltersResourcesOnTaskRunner(\n    bool use_native_ad_engine,\n')
 text=edit(text,'          engine_wrapper),','          engine_wrapper, use_native_ad_engine),')
 text=edit(text,'  g_brave_browser_process->ad_block_service()->AsyncCall(base::BindOnce(\n      &BindCosmeticFiltersResourcesOnTaskRunner, std::move(receiver)));',
   '  const bool use_native_ad_engine =\n      !frame_host->GetLastCommittedURL().SchemeIsHTTPOrHTTPS() ||\n      sandium_ubo::SealAndUseNativeAdEngine(frame_host->GetBrowserContext());\n  g_brave_browser_process->ad_block_service()->AsyncCall(base::BindOnce(\n      &BindCosmeticFiltersResourcesOnTaskRunner, use_native_ad_engine, std::move(receiver)));')
 result[name]=text.encode()
 name='components/cosmetic_filters/browser/cosmetic_filters_resources.h';text=(core/name).read_text()
 text=edit(text,'      brave_shields::AdBlockEngineWrapper* engine_wrapper);','      brave_shields::AdBlockEngineWrapper* engine_wrapper,\n      bool use_native_ad_engine = true);')
 text=edit(text,' private:\n',' private:\n  const bool use_native_ad_engine_;\n')
 result[name]=text.encode()
 name='components/cosmetic_filters/browser/cosmetic_filters_resources.cc';text=(core/name).read_text()
 text=edit(text,'    brave_shields::AdBlockEngineWrapper* engine_wrapper)\n    : engine_wrapper_(engine_wrapper) {}','    brave_shields::AdBlockEngineWrapper* engine_wrapper, bool use_native_ad_engine)\n    : use_native_ad_engine_(use_native_ad_engine), engine_wrapper_(engine_wrapper) {}')
 text=edit(text,'    HiddenClassIdSelectorsCallback callback) {','    HiddenClassIdSelectorsCallback callback) {\n  if (!use_native_ad_engine_) {\n    std::move(callback).Run(base::DictValue());\n    return;\n  }')
 text=edit(text,'    UrlCosmeticResourcesCallback callback) {','    UrlCosmeticResourcesCallback callback) {\n  if (!use_native_ad_engine_) {\n    std::move(callback).Run(base::Value(base::DictValue()));\n    return;\n  }')
 result[name]=text.encode()
 name='browser/sources.gni';text=(core/name).read_text()
 result[name]=edit(text,'brave_chrome_browser_deps = [','brave_chrome_browser_deps = [\n  "//brave/components/sandium_ubo_routing",').encode()
 name='components/brave_shields/content/browser/BUILD.gn';text=(core/name).read_text()
 result[name]=edit(text,'  deps = [','  deps = [\n    "//brave/components/sandium_ubo_routing",').encode()
 for name in ['routing.h','routing.cc','owner_state.h','BUILD.gn']:
  result['components/sandium_ubo_routing/'+name]=(HERE/name).read_bytes()
 return result

def data(value):return None if value is None else base64.b64decode(value)
def encode(value):return None if value is None else base64.b64encode(value).decode()
def path(core,name):
 p=core/name
 if Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('Unsafe path')
 for node in [p,*p.parents]:
  if node==core:break
  if node.is_symlink():raise ValueError('Symlink path')
 return p
def write(p,b):
 p.parent.mkdir(parents=True,exist_ok=True)
 fd,t=tempfile.mkstemp(dir=p.parent)
 try:
  with os.fdopen(fd,'wb') as f:f.write(b);f.flush();os.fsync(f.fileno())
  os.replace(t,p)
 finally:
  if os.path.exists(t):os.unlink(t)
def transition(core,receipt,key):
 for name,e in receipt.items():
  p=path(core,name);current=p.read_bytes() if p.exists() else None
  if current not in [data(e['before']),data(e['after'])]:raise ValueError('Unowned edit: '+name)
 for name,e in receipt.items():
  p=path(core,name);b=data(e[key])
  if b is None:
   if p.exists():p.unlink()
  else:write(p,b)
def apply(core):
 r=core/RECEIPT
 if r.exists():transition(core,json.loads(r.read_text()),'after');return
 changes=plan(core);receipt={}
 for name,b in changes.items():
  p=path(core,name)
  if name.startswith('components/sandium_ubo_routing/') and p.exists():raise ValueError('Unowned routing input')
  receipt[name]={'before':encode(p.read_bytes() if p.exists() else None),'after':encode(b)}
 write(r,json.dumps(receipt,sort_keys=True).encode());transition(core,receipt,'after')
def reset(core):
 r=core/RECEIPT
 if not r.exists():return
 transition(core,json.loads(r.read_text()),'before');r.unlink()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--core',type=Path,required=True);p.add_argument('--reset',action='store_true');a=p.parse_args()
 (reset if a.reset else apply)(a.core.resolve())
