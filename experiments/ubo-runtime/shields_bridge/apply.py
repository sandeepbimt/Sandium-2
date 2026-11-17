#!/usr/bin/env python3
"""Compose restricted observation API after EXT0 and runtime loader overlays.
Does not enable filtering, change Shields preferences or suppress Brave.
"""
import argparse
import importlib.util
import base64
import tempfile
import shutil
import os
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parent
EXTENSION_ID = 'hadlbhndhhkkeandhhmnhkobiananclk'
ID_HASH = hashlib.sha1(EXTENSION_ID.encode()).hexdigest().upper()

def replace_once(text, old, new):
    if new in text:
        return text
    if text.count(old) != 1:
        raise ValueError('Missing/ambiguous bridge source anchor: ' + old[:80])
    return text.replace(old,new,1)

DESKTOP_THEME_TESTS = """source_set("unit_tests") {
  testonly = true

  sources = [ "brave_theme_api_unittest.cc" ]

  deps = [
    "//brave/browser/extensions",
    "//chrome/browser/themes",
    "//chrome/test:test_support",
    "//testing/gtest",
  ]
}"""

def guard_desktop_theme_tests(text):
    # EXT0 intentionally has only :core on Android, not desktop :extensions.
    # GN resolves all targets in this file when the private bridge is requested,
    # even though these unrelated theme tests are not in the APK dependency path.
    guarded='if (!is_android) {\n'+'\n'.join('  '+line if line else '' for line in DESKTOP_THEME_TESTS.splitlines())+'\n}'
    return replace_once(text, DESKTOP_THEME_TESTS, guarded)

def plan_native(core):
    inputs = {}
    def edit(path,old,new):
        p=core/path
        text=inputs.get(p,p.read_text())
        inputs[p]=replace_once(text,old,new)
    edit('common/extensions/api/api_sources.gni',
         'schema_sources_ = [ "brave_theme.json" ]',
         'schema_sources_ = [ "brave_theme.json", "sandium_ubo.json" ]')
    # Core-only Android is UNSPECIFIED_PLATFORM in pinned Chromium; android is
    # invalid and desktop_android would deny this API. Enforce Android in the
    # native capability guard, retaining fixed identity/context restrictions.
    feature = json.dumps({
        'channel':'stable','component_extensions_auto_granted':False,
        'contexts':['privileged_extension'],'allowlist':[ID_HASH]},indent=2)
    # Explicit identity is the authority boundary, not automatic component trust.
    edit('common/extensions/api/_api_features.json',
         '  "braveTheme": [{', '  "sandiumUbo": '+feature+',\n  "braveTheme": [{')
    edit('browser/extensions/api/BUILD.gn',
         'custom_impl_schemas = [ "brave_theme" ]',
         'custom_impl_schemas = [ "brave_theme", "sandium_ubo" ]')
    edit('browser/extensions/api/BUILD.gn',
         'inputs = [ "//brave/browser/extensions/api/brave_theme_api.h" ]',
         'inputs = [ "//brave/browser/extensions/api/brave_theme_api.h",\n'
         '             "//brave/browser/extensions/api/sandium_ubo_api.h" ]')
    p=core/'browser/extensions/api/BUILD.gn'
    inputs[p]=guard_desktop_theme_tests(inputs[p])
    block='''
# Isolated Android experiment; registration is explicit in its component loader.
source_set("sandium_ubo_bridge") {
  sources = [ "sandium_ubo_api.cc", "sandium_ubo_api.h" ]
  deps = [
    "//base",
    "//crypto",
    "//brave/components/brave_shields/core/browser",
    "//brave/components/sandium_ubo:identity",
    "//brave/components/sandium_ubo_routing",
    "//chrome/browser:browser_process",
    "//components/sessions",
    "//brave/components/brave_shields/core/common",
    "//chrome/browser/content_settings:content_settings_factory",
    "//chrome/browser/profiles:profile",
    "//components/prefs",
    "//components/content_settings/core/browser",
    "//components/content_settings/core/common",
    "//content/public/browser",
    "//extensions/browser",
    "//extensions/common",
    "//url",
  ]
}
'''
    if 'source_set("sandium_ubo_bridge")' not in inputs[p]: inputs[p]+=block
    for name,dest in [('sandium_ubo_api.h','browser/extensions/api'),
                      ('sandium_ubo_api.cc','browser/extensions/api'),
                      ('sandium_ubo.json','common/extensions/api')]:
        inputs[core/dest/name]=(ROOT/name).read_text()
    edit('browser/extensions/resources.gni',
         '    "//brave/components/sandium_ubo:identity",',
         '    "//brave/components/sandium_ubo:identity",\n'
         '    "//brave/browser/extensions/api:sandium_ubo_bridge",')
    edit('chromium_src/chrome/browser/extensions/component_loader_factory.cc',
         '#include "brave/components/sandium_ubo/identity.h"',
         '#include "brave/components/sandium_ubo/identity.h"\n'
         '#include "brave/browser/extensions/api/sandium_ubo_api.h"\n'
         '#include "chrome/browser/profiles/profile.h"')
    factory=core/'chromium_src/chrome/browser/extensions/component_loader_factory.cc'
    marker='// SANDIUM_UBO_PROFILE_INITIALIZATION'
    if marker in inputs[factory]:
        inputs[factory]=replace_once(inputs[factory],marker,marker+'\n'
            '    api::RegisterSandiumUboFunctions();\n'
            '    api::ResetSandiumUboRuntimePhase(profile);')
    else:
        edit('chromium_src/chrome/browser/extensions/component_loader_factory.cc',
             '  explicit BraveComponentLoader(Profile* profile) : ComponentLoader(profile) {}',
             '  explicit BraveComponentLoader(Profile* profile) : ComponentLoader(profile) {\n'
             '    api::RegisterSandiumUboFunctions();\n'
             '    api::ResetSandiumUboRuntimePhase(profile);\n'
             '  }')
    identity=core/'components/sandium_ubo/identity.h'
    if not identity.exists() or EXTENSION_ID not in identity.read_text():
        raise ValueError('Pinned loader identity must be installed first')
    for p in inputs:
        if p.is_symlink(): raise ValueError('Symlink bridge target refused')
    return inputs

def patch_background(bundle):
    """Input must already pass pinned bundle validation; no network here."""
    manifest=json.loads((bundle/'manifest.json').read_text())
    if manifest.get('version') != '1.76.4' or manifest.get('manifest_version') != 2:
        raise ValueError('Unexpected uBO version or runtime')
    start=bundle/'js/start.js';text=start.read_text()
    hook="    webRequest.start();"
    ready='    µb.readyToFilter = true;'
    if text.index(ready) > text.index('await initializeTabs();') or text.index('await initializeTabs();') > text.index(hook):
        raise ValueError('uBO startup ordering changed')
    preflight='''    // Sandium native user rules reconcile before filtering and tab restore.
    // Any rejected startup remains gated; native coordinator owns timeout/unload.
    const { startSandiumBridge } = await import('./sandium-bridge.js');
    globalThis.sandiumNativeBridge = await startSandiumBridge(chrome.sandiumUbo, µb);
    if (!globalThis.sandiumNativeBridge.available) {
        throw new Error('Sandium native capability unavailable');
    }
'''+ready
    text=replace_once(text,ready,preflight)
    text=replace_once(text,hook,hook+'''
    await globalThis.sandiumNativeBridge.reportListenersReady();''')
    start.write_text(text)
    for name in ('sandium-bridge.js','sandium-user-filters.js','sandium-lists.js'):
        (bundle/'js'/name).write_bytes((ROOT/name).read_bytes())

def patch_filter_policy(bundle):
    # Actual upstream filtering paths; never fabricate extension runtime results.
    p=bundle/'js/traffic.js';text=p.read_text()
    text=replace_once(text,"import µb from './background.js';", "import µb from './background.js';\nimport { allowsNetwork as sandiumAllowsNetwork } from './sandium-policy.js';")
    for name in ('onBeforeRequest','onHeadersReceived','onResponseStarted'):
        anchor=f'function {name}(details) {{'
        text=replace_once(text,anchor,anchor+'\n    if ( !sandiumAllowsNetwork(details) ) { return; }')
    p.write_text(text)
    p=bundle/'js/messaging.js';text=p.read_text()
    text=replace_once(text,"import µb from './background.js';", "import µb from './background.js';\nimport { allowsTab as sandiumAllowsTab } from './sandium-policy.js';")
    anchor='const retrieveContentScriptParameters = async function(sender, request) {'
    text=replace_once(text,anchor,anchor+\
        '\n    if ( !await sandiumAllowsTab(sender.tabId, sender.frameId, sender.frameURL, true, undefined, sender.documentId) ) { return; }')
    anchor='''    case 'retrieveGenericCosmeticSelectors':
        request.tabId = sender.tabId;
        request.frameId = sender.frameId;
        response = {
            result: cosmeticFilteringEngine.retrieveGenericSelectors(request),
        };
        break;'''
    replacement='''    case 'retrieveGenericCosmeticSelectors':
        return sandiumAllowsTab(sender.tabId, sender.frameId, sender.frameURL, true, undefined, sender.documentId).then(allowed => {
            if (!allowed) { callback({ result: {} }); return; }
            request.tabId = sender.tabId;
            request.frameId = sender.frameId;
            callback({ result: cosmeticFilteringEngine.retrieveGenericSelectors(request) });
        });'''
    text=replace_once(text,anchor,replacement);p.write_text(text)
    p=bundle/'js/vapi-scripting.js';text=p.read_text()
    # MV2 programmatic scriptlets must honor the same native top-frame policy.
    anchor='function onCommitted(details) {'
    text=replace_once(text,anchor,'async function onCommitted(details) {')
    anchor='    const entry = contentScriptDict.get(hostname);'
    text=replace_once(text,anchor,'    if ( !await sandiumAllowsTab(tabId, frameId, details.url, false, undefined, details.documentId) ) { return; }\n'+anchor)
    anchor='        if ( code ) {'
    text=replace_once(text,anchor,'        if ( code && await sandiumAllowsTab(id, 0, url) ) {')
    if "import { allowsTab as sandiumAllowsTab }" not in text:
        text="import { allowsTab as sandiumAllowsTab } from './sandium-policy.js';\n"+text
    p.write_text(text)
    p=bundle/'js/vapi-background.js';text=p.read_text()
    text=replace_once(text,"import webext from './webext.js';", "import webext from './webext.js';\nimport { allowsTab as sandiumAllowsTab } from './sandium-policy.js';")
    text=replace_once(text,'        portDetails.frameURL = url;',
        '        portDetails.frameURL = url;\n        portDetails.documentId = sender.documentId;')
    text=replace_once(text,'onFrameworkMessage: function(request, port, callback) {',
        'onFrameworkMessage: async function(request, port, callback) {')
    text=replace_once(text,'            if ( msg.add ) {',
        '            if ( msg.add && await sandiumAllowsTab(tabId, portDetails.frameId, portDetails.frameURL, true, undefined, portDetails.documentId) ) {')
    p.write_text(text)
    (bundle/'js/sandium-policy.js').write_bytes((ROOT/'sandium-policy.js').read_bytes())

def patch_popup_policy(bundle):
    p=bundle/'js/tab.js';text=p.read_text()
    text=replace_once(text,"import µb from './background.js';", "import µb from './background.js';\nimport { allowsPopup as sandiumAllowsPopup } from './sandium-policy.js';")
    anchor='            const result = onPopupUpdated(tabId, candidate.opener);'
    replacement="""            const openerContext = µb.tabContextManager.lookup(candidate.opener.tabId);
            const targetContext = µb.tabContextManager.lookup(tabId);
            const openerURL = openerContext?.rawURL;
            const targetURL = targetContext?.rawURL;
            const allowed = await sandiumAllowsPopup(candidate.opener,
                { tabId, url: targetURL });
            // A tab can navigate/close while the native permission reply is in
            // flight. Never close a new document using a stale popup decision.
            if (!allowed || popupCandidates.get(tabId) !== candidate ||
                µb.tabContextManager.lookup(candidate.opener.tabId)?.rawURL !== openerURL ||
                µb.tabContextManager.lookup(tabId)?.rawURL !== targetURL) {
                continue;
            }
            const result = onPopupUpdated(tabId, candidate.opener);"""
    text=replace_once(text,anchor,replacement);p.write_text(text)

def patch_installed_bundle(core):
    root=core/'components/sandium_ubo'
    patch_background(root/'sandium_ubo')
    patch_filter_policy(root/'sandium_ubo')
    patch_popup_policy(root/'sandium_ubo')
    spec=importlib.util.spec_from_file_location('sandium_stats_patch',ROOT/'patch_stats.py')
    stats=importlib.util.module_from_spec(spec);spec.loader.exec_module(stats)
    stats.patch_stats(root/'sandium_ubo',ROOT)
    grd=root/'resources.grd';text=grd.read_text()
    line='      <include name="IDR_SANDIUM_UBO_BRIDGE" file="sandium_ubo/js/sandium-bridge.js" type="BINDATA" />\n'
    text=replace_once(text,'  </includes></release>',line+'  </includes></release>')
    line='      <include name="IDR_SANDIUM_UBO_USER_FILTERS" file="sandium_ubo/js/sandium-user-filters.js" type="BINDATA" />\n'
    text=replace_once(text,'  </includes></release>',line+'  </includes></release>')
    line='      <include name="IDR_SANDIUM_UBO_POLICY" file="sandium_ubo/js/sandium-policy.js" type="BINDATA" />\n'
    text=replace_once(text,'  </includes></release>',line+'  </includes></release>')
    line='      <include name="IDR_SANDIUM_UBO_STATS" file="sandium_ubo/js/sandium-stats.js" type="BINDATA" />\n'
    text=replace_once(text,'  </includes></release>',line+'  </includes></release>')
    line='      <include name="IDR_SANDIUM_UBO_LISTS" file="sandium_ubo/js/sandium-lists.js" type="BINDATA" />\n'
    text=replace_once(text,'  </includes></release>',line+'  </includes></release>')
    grd.write_text(text)
    mapping=root/'resource_map.h';text=mapping.read_text()
    line='    {"sandium_ubo/js/sandium-bridge.js", IDR_SANDIUM_UBO_BRIDGE},\n'
    text=replace_once(text,'};',line+'};')
    line='    {"sandium_ubo/js/sandium-user-filters.js", IDR_SANDIUM_UBO_USER_FILTERS},\n'
    text=replace_once(text,'};',line+'};')
    line='    {"sandium_ubo/js/sandium-policy.js", IDR_SANDIUM_UBO_POLICY},\n'
    text=replace_once(text,'};',line+'};')
    line='    {"sandium_ubo/js/sandium-stats.js", IDR_SANDIUM_UBO_STATS},\n'
    text=replace_once(text,'};',line+'};')
    line='    {"sandium_ubo/js/sandium-lists.js", IDR_SANDIUM_UBO_LISTS},\n'
    text=replace_once(text,'};',line+'};')
    mapping.write_text(text)

RECEIPT='.sandium-ubo-shields-receipt.json'
def encode(data):
    return None if data is None else base64.b64encode(data).decode()
def decode(data):
    return None if data is None else base64.b64decode(data,validate=True)
def install(p,data):
    if data is None:
        if p.exists(): p.unlink()
        return
    p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(p.name+'.sandium-bridge-tmp')
    tmp.write_bytes(data);os.replace(tmp,p)
def owned_path(core,name):
    rel=Path(name)
    if rel.is_absolute() or '..' in rel.parts: raise ValueError('Unsafe receipt path')
    p=core/rel
    if p.is_symlink() or any(a.is_symlink() for a in p.parents if a!=core.parent):
        raise ValueError('Symlink receipt target')
    return p
def reset(core):
    r=core/RECEIPT
    if not r.exists(): return
    if r.is_symlink(): raise ValueError('Symlink receipt')
    receipt=json.loads(r.read_text())
    if receipt.get('schema')!=1: raise ValueError('Unknown bridge receipt')
    changes=[]
    for name,item in receipt['files'].items():
        p=owned_path(core,name);old=decode(item['before']);new=decode(item['after'])
        current=p.read_bytes() if p.exists() else None
        if current not in (old,new): raise ValueError('Unowned bridge change: '+name)
        changes.append((p,old))
    for p,data in changes: install(p,data)
    r.unlink()
def apply(core,include_bundle=True):
    reset(core)
    proposed={p:text.encode() for p,text in plan_native(core).items()}
    if include_bundle:
        root=core/'components/sandium_ubo'
        with tempfile.TemporaryDirectory() as td:
            staged=Path(td)/'core';dest=staged/'components/sandium_ubo'
            # Copy the complete bundle so localization inventory hashes include
            # untouched assets as well as this overlay's adapter and start hook.
            shutil.copytree(root,dest)
            patch_installed_bundle(staged)
            changed=['sandium_ubo/js/sandium-lists.js','sandium_ubo/js/sandium-stats.js','sandium_ubo/js/tab.js','sandium_ubo/js/vapi-background.js','sandium_ubo/js/traffic.js','sandium_ubo/js/messaging.js','sandium_ubo/js/vapi-scripting.js','sandium_ubo/js/sandium-policy.js','sandium_ubo/js/start.js','sandium_ubo/js/sandium-user-filters.js','sandium_ubo/js/sandium-bridge.js','resources.grd','resource_map.h']
            if (root/'disk_resources.h').exists():
                helper=ROOT.parent/'loader/apply.py'
                spec=importlib.util.spec_from_file_location('sandium_loader_inventory',helper)
                loader=importlib.util.module_from_spec(spec);spec.loader.exec_module(loader)
                (dest/'disk_resources.h').write_text(loader.build_disk_inventory(staged))
                changed.append('disk_resources.h')
            for name in changed:
                proposed[root/name]=(dest/name).read_bytes()
    entries={}
    for p,data in proposed.items():
        owned_path(core,str(p.relative_to(core)))
        entries[str(p.relative_to(core))]={'before':encode(p.read_bytes() if p.exists() else None),'after':encode(data)}
    install(core/RECEIPT,json.dumps({'schema':1,'files':entries},sort_keys=True).encode())
    for p,data in proposed.items(): install(p,data)
    return proposed
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--core',type=Path)
    p.add_argument('--bundle',type=Path);p.add_argument('--reset',action='store_true');a=p.parse_args()
    if a.reset:
        if not a.core: p.error('--reset requires --core')
        reset(a.core.resolve())
    elif a.core: apply(a.core.resolve())
    if a.bundle: patch_background(a.bundle.resolve())
