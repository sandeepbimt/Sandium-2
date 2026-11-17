#!/usr/bin/env python3
"""Authoritative fixed-component policy on both native webRequest dispatch paths.
Apply after loader/bridge/routing; reset BEFORE those overlays and EXT0.
Does not activate an engine. Native compilation/runtime remain separate gates.
"""
import argparse,base64,json,os,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
RECEIPT='.sandium-ubo-request-policy.json'
def replace_once(s,a,b):
    if s.count(a)!=1:raise ValueError('Missing/ambiguous policy anchor: '+a[:90])
    return s.replace(a,b,1)
def plan(src):
    changes={}
    def edit(n,a,b):
        p=src/n;s=changes.get(p,p.read_text());changes[p]=replace_once(s,a,b)
    client='extensions/browser/api/extensions_api_client.h'
    edit(client,'#include "base/memory/raw_ptr.h"','#include "base/memory/raw_ptr.h"\n#include "base/values.h"')
    anchor='  // Notifies that an extension failed to act on a network request because the'
    method='''  virtual bool SupportsPrivateWebRequestPolicy(const ExtensionId&) const { return false; }

  // Embedder-only augmentation after permission filtering, per recipient.
  // Default is no-op; embedders must authorize identity and context themselves.
  virtual void AugmentWebRequestEventForExtension(
      content::BrowserContext* context, const WebRequestInfo& request,
      const ExtensionId& extension_id, bool crosses_incognito,
      base::DictValue& details) const {}

'''
    edit(client,anchor,method+anchor)
    header='extensions/browser/api/web_request/extension_web_request_event_router.h'
    a='''  void DispatchEventToListeners(
      content::BrowserContext* browser_context,
      std::unique_ptr<ListenerIDs> listener_ids,
      uint64_t request_id,'''
    edit(header,a,a.replace('uint64_t request_id','const WebRequestInfo* request'))
    router='extensions/browser/api/web_request/extension_web_request_event_router.cc'
    edit(router,'request->id, std::move(event_details));','request, std::move(event_details));')
    a='''    std::unique_ptr<ListenerIDs> listener_ids,
    uint64_t request_id,
    std::unique_ptr<WebRequestEventDetails> event_details) {'''
    b=a.replace('uint64_t request_id','const WebRequestInfo* request')+'\n  const uint64_t request_id = request->id;'
    edit(router,a,b)
    a='''    args_filtered->data.Append(event_details->GetFilteredDict(
        listener->extra_info_spec, PermissionHelper::Get(browser_context),
        listener->id.extension_id, crosses_incognito));'''
    b='''    auto private_details = event_details->GetFilteredDict(
        listener->extra_info_spec, PermissionHelper::Get(browser_context),
        listener->id.extension_id, crosses_incognito);
    ExtensionsAPIClient::Get()->AugmentWebRequestEventForExtension(
        browser_context, *request, listener->id.extension_id,
        crosses_incognito, private_details);
    args_filtered->data.Append(std::move(private_details));'''
    edit(router,a,b)
    a='''    args->data.Append(event_details.GetFilteredDict(
        union_spec_all, PermissionHelper::Get(browser_context),
        key.extension_id, crosses_incognito));'''
    b='''    auto private_details = event_details.GetFilteredDict(
        union_spec_all, PermissionHelper::Get(browser_context),
        key.extension_id, crosses_incognito);
    ExtensionsAPIClient::Get()->AugmentWebRequestEventForExtension(
        browser_context, *request, key.extension_id, crosses_incognito,
        private_details);
    args->data.Append(std::move(private_details));'''
    edit(router,a,b)
    header='brave/browser/extensions/api/brave_extensions_api_client.h'
    edit(header,'  friend class BraveExtensionsAPIClientTests;','''  bool SupportsPrivateWebRequestPolicy(const ExtensionId& extension_id) const override;

  void AugmentWebRequestEventForExtension(
      content::BrowserContext* context, const WebRequestInfo& request,
      const ExtensionId& extension_id, bool crosses_incognito,
      base::DictValue& details) const override;

  friend class BraveExtensionsAPIClientTests;''')
    cc='brave/browser/extensions/api/brave_extensions_api_client.cc'
    includes='''#include "base/values.h"
#include "brave/components/brave_shields/core/browser/brave_shields_utils.h"
#include "brave/components/sandium_ubo/identity.h"
#include "brave/components/sandium_ubo_routing/routing.h"
#include "chrome/browser/content_settings/host_content_settings_map_factory.h"
#include "chrome/browser/profiles/profile.h"
#include "content/public/browser/browser_context.h"
#include "content/public/browser/browser_thread.h"
#include "content/public/browser/render_frame_host.h"
#include "content/public/browser/web_contents.h"
#include "content/public/browser/navigation_controller.h"
#include "content/public/browser/navigation_entry.h"
#include "extensions/browser/extension_registry.h"
#include "extensions/common/extension.h"
#include "extensions/common/manifest.h"
#include "extensions/common/api/web_request/web_request_resource_type.h"
'''
    edit(cc,'#include <string_view>','#include <string_view>\n#include <utility>\n'+includes)
    edit(cc,'}  // namespace extensions',(HERE/'native_method.cc').read_text()+'\n}  // namespace extensions')
    gn='brave/browser/extensions/BUILD.gn'
    s=(src/gn).read_text();start=s.index('source_set("core")');dep=s.index('  deps = [',start)
    inject='''
    "//brave/components/brave_shields/core/browser",
    "//brave/components/sandium_ubo:identity",
    "//brave/components/sandium_ubo_routing",
    "//chrome/browser/content_settings:content_settings_factory",'''
    changes[src/gn]=s[:dep]+s[dep:].replace('  deps = [','  deps = ['+inject,1)
    return changes

def encode(b):return None if b is None else base64.b64encode(b).decode()
def decode(s):return None if s is None else base64.b64decode(s,validate=True)
def path(src,n):
    p=Path(n)
    if p.is_absolute() or '..' in p.parts:raise ValueError('Unsafe policy receipt path')
    p=src/p
    if any(q.is_symlink() for q in [p,*p.parents] if q!=src.parent):raise ValueError('Symlink policy target')
    return p
def write(p,b):
    if b is None:
        if p.exists():p.unlink()
    else:
        p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.ubo-policy-tmp');tmp.write_bytes(b);os.replace(tmp,p)
def reset(src):
    rp=path(src,RECEIPT)
    if not rp.exists():return
    r=json.loads(rp.read_text());assert r['schema']==1
    ops=[]
    for n,e in r['files'].items():
        p=path(src,n);old=decode(e['before']);new=decode(e['after']);cur=p.read_bytes() if p.exists() else None
        if cur not in (old,new):raise ValueError('Unowned policy modification: '+n)
        ops.append((p,old))
    for p,b in ops:write(p,b)
    rp.unlink()
def apply(src):
    reset(src)
    changes=plan(src);files={}
    for p,s in changes.items():
        path(src,str(p.relative_to(src)));files[str(p.relative_to(src))]={'before':encode(p.read_bytes() if p.exists() else None),'after':encode(s.encode())}
    write(src/RECEIPT,json.dumps({'schema':1,'files':files},sort_keys=True).encode())
    for p,s in changes.items():write(p,s.encode())
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--src',type=Path,required=True);p.add_argument('--reset',action='store_true');a=p.parse_args();(reset if a.reset else apply)(a.src.resolve())
