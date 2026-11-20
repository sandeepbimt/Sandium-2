#!/usr/bin/env python3
"""Emit an isolated source delta for the *prepared* #1462 tree, never patch it in place.

Reads original Git objects, including the exact #1442 product transforms. Refuses
unexpected source. No network, git checkout, CI, restore, or checkpoint operation.
"""
from __future__ import annotations
import argparse, ast, hashlib, json, os, re, subprocess, tempfile, types
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = 'c86ff1a8575e49c0dff22610315004c0c1a48a95'
REF = 'd3e82450867d3be2c5724244c4077b0457814d55'
CHROME = '52bdd21723d5db0c9ab11716d38feac74828cf84'
CORE = 'bd6d26d1bced03c17a98baa86d2cd3425d543d1b'
PREFIX = 'components/sandium_adblock/'
F = PREFIX + 'document_subresource_factory.cc'
H = PREFIX + 'document_subresource_factory.h'
REFS = {
 'catalog': ('.circleci/scripts/apply-sandium-filter-subscriptions.py','1ef52bb1f189c0907a3f79c2487a0efed5055436'),
 'popup': ('.circleci/features/ad-redirects/popup.py','fa3a0aa94f6c70f67e57b2f8abec7baa6fb7fdfe'),
 'media': ('.circleci/features/ad-redirects/media_popup.py','e19211c4ea749d31f25d799182be427366692b90'),
 'pre': ('.circleci/features/filter-compat/subscriptions.py','1c4be66cea768fd413463e8b16e755e6782910e6'),
 'nav': ('.circleci/features/filter-compat/popup_navigation.py','035c411233e9537e8c4ac2f7e7ebe18660858f24'),
 'inc': ('.circleci/features/filter-compat/popup_navigation.cc.inc','185a0aca25d0ef9e03fead4a070bf588182fc60b'),
 'matcher': ('.circleci/features/filter-compat/popup_matcher.py','959cb1b8d37422763b38b5ceeffc96773949d518'),
 'modifier': ('.circleci/features/filter-compat/modifier.py','be02f68f0eef22231a6d95a418532c816e160d28'),
 'denyallow': ('.circleci/features/filter-compat/denyallow.py','9a5f4a458366a2629c71ac43ca9d9e1c0b15bc9d'),
 'index': ('.circleci/features/filter-compat/token_index.py','020b308968f1e48ffbf5e2b22af744ba6aa12ab7'),
 'resources': ('.circleci/features/ad-redirects/ad_resources.py','b23757eb7648463422c1e8d89dc7bf644fc912cc')}

def git(p,*args):return subprocess.check_output(['git','-C',str(p),*args])
def blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def sha(b):return hashlib.sha256(b).hexdigest()
def local(name):return (HERE/name).read_text()
def once(s,a,b):
    if s.count(a)!=1:raise ValueError(f'missing/ambiguous source anchor: {a[:100]!r}')
    return s.replace(a,b,1)
def lit(s,key):
    for n in ast.parse(s).body:
        if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id==key:return ast.literal_eval(n.value)
    raise ValueError(key)
def defs(s,names,ns=None):
    # Only definitions are loaded from an exact digest-locked reference. Never
    # invoke upstream main(), shell hooks, git restore or its file-writing APIs.
    nodes=[n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name in names];ctx=dict(ns or {})
    exec(compile(ast.Module(nodes,[]),'<pinned reference>','exec'),ctx);return ctx

def verify_catalog(source):
    rows=json.loads(local('catalog.json'))
    if [(r['url'],r['title']) for r in rows]!=list(lit(source,'FILTERS')):raise ValueError('catalog differs from Sandium')
    if len({r['url'] for r in rows})!=len(rows) or not all(r['enabled_on_first_create'] for r in rows):raise ValueError('invalid defaults')
    return rows

def catalog_header(rows):
    out=['// Generated from Sandium #1442. Metadata only; no remote list is redistributed.', '#pragma once','namespace sandium::port1442 {', 'struct CatalogEntry { const char* url; const char* key; };','inline constexpr CatalogEntry kCatalog[] = {']
    return '\n'.join(out+['  {'+json.dumps(r['url'])+', "'+sha(r['url'].encode())+'"},' for r in rows]+['};','}', ''])

def factory(s,pre):
    s=once(s,'#include <vector>','#include <vector>\n#include <set>\n#include <string_view>\n#include "base/containers/span.h"\n#include "base/json/json_reader.h"\n#include "base/logging.h"\n#include "base/task/sequenced_task_runner.h"\n#include "components/sandium_adblock/policy.h"\n#include "components/sandium_adblock/style.h"\n#include "net/base/registry_controlled_domains/registry_controlled_domain.h"')
    s=once(s,'class RuleSnapshot {','using DATFileDataBuffer = std::vector<uint8_t>;\n'+pre+'\nclass RuleSnapshot {')
    s=once(s,'  bool Initialize(std::string text) {',
           '  bool Initialize(std::string text, std::vector<std::string> additional, bool initialize_resolver) {')
    s=once(s,'        !adblock::set_domain_resolver()) {',
           '        (initialize_resolver && !adblock::set_domain_resolver())) {')
    s=once(s,'    primary_.emplace(std::move(primary_engine.value));\n    additional_.emplace(adblock::new_engine());','    if (!Install(std::move(additional))) return false;\n    primary_.emplace(std::move(primary_engine.value));')
    s=once(s,'  Action Evaluate(',local('snapshot.cc.inc')+'\n  Action Evaluate(')
    s=once(s,'Resource::kFontResource})','Resource::kFontResource, Resource::kXhr, Resource::kMedia, Resource::kPing})')
    s=once(s,'      response->OnComplete(\n          network::URLLoaderCompletionStatus(net::ERR_BLOCKED_BY_CLIENT));', "      network::URLLoaderCompletionStatus status(net::ERR_BLOCKED_BY_CLIENT);\n      // Preserve Chromium's native collapse behavior only for a definite blocked image.\n      status.should_collapse_initiator = request.resource_type == static_cast<int>(Resource::kImage);\n      response->OnComplete(status);")
    s=once(s,'  bool failed = false;', '''  bool failed = false;
  bool ready = false;
  std::string packaged_rules;
  std::optional<std::vector<std::string>> queued_refresh;
  uint64_t refresh_revision = 0;
  bool refresh_in_flight = false;
  base::SequenceBound<RuleSnapshot> refresh_candidate;''')
    s=once(s,'if (!state.attempted || state.failed || state.pending', 'if (!state.ready || state.pending')
    s=once(s,'void OnInitialized(bool ready) { GetState().failed = !ready; }',
           local('refresh.cc.inc').rstrip())
    s=once(s,'  state.attempted = true;', '  state.attempted = true;\n  state.packaged_rules = std::move(verified_rules);')
    s=once(s,'      .WithArgs(std::move(verified_rules))',
           '      .WithArgs(state.packaged_rules, std::vector<std::string>{}, true)')
    return once(s,'void MaybeAppendDocumentSubresourceFactory(',local('native_api.cc.inc')+'\nvoid MaybeAppendDocumentSubresourceFactory(')

def header(s):
    s=once(s,'#include <string>','#include <string>\n#include <optional>\n#include <vector>\n#include "base/functional/callback.h"\n#include "url/gurl.h"')
    return once(s,'// Browser startup only;', '''// Browser-owned additional rules only. Replies run on the UI sequence.
bool CheckSubframe(GURL,const url::Origin&,base::OnceCallback<void(bool)>);
bool OfflineRulesReady();
// Synchronous parser check: call only on the subscription worker.
std::optional<int> InspectSubscription(const std::string&);
void InstallAdditionalRules(std::vector<std::string>);
void QueryPopup(GURL,GURL,base::OnceCallback<void(bool)>);
void QueryHideStyles(GURL,base::OnceCallback<void(std::string)>);

// Browser startup only;''')

def after_function_open(s,signature,extra,params=()):
    if s.count(signature)!=1:raise ValueError('unexpected function '+signature)
    at=s.index(signature); end=s.index(') {',at)+3
    if end-at>2200 or any(not re.search(r'\b'+p+r'\b',s[at:end]) for p in params):raise ValueError('unexpected signature '+signature)
    return s[:end]+'\n'+extra+s[end:]

def adapt_early(s):
    if s!=local('tests/reference/early_helpers.inc'):raise ValueError('tested #1442 guards differ from source')
    s=once(s,'map && brave_shields::IsBraveShieldsEnabled(map, top_url) &&','map &&')
    return once(s,'CONTENT_SETTING_ALLOW &&\n         brave_shields::ShouldBlockAdRedirect(*profile->GetPrefs(), top_url);','CONTENT_SETTING_ALLOW;')

def adapt_throttle(s):
    # Exactly the source's one-shot navigation lifetime and 100 ms budget. The
    # only replaced pieces are the Brave service and policy accessors.
    s=once(s,'         brave_shields::IsBraveShieldsEnabled(settings, publisher) &&\n         brave_shields::IsBraveShieldsEnabled(settings, destination) &&\n','')
    s=once(s,'CONTENT_SETTING_ALLOW &&\n         brave_shields::ShouldBlockAdRedirect(*profile->GetPrefs(), publisher);','CONTENT_SETTING_ALLOW;')
    s=once(s,'    auto* service = g_brave_browser_process->ad_block_service();\n','')
    s=once(s,'if (!service || remaining_budget_', 'if (!sandium::adblock_native::OfflineRulesReady() || remaining_budget_')
    a=s.index('    service->AsyncCallAndReplyWithResult<bool>(');b=s.index('        base::BindOnce(&SandiumPopupNavigationThrottle::OnChecked,',a)
    s=s[:a]+'    sandium::adblock_native::QueryPopup(target, frame_,\n'+s[b:]
    return once(s,'void BraveContentBrowserClient::OnSandiumScriptedPopupCreated(', 'void ChromeContentBrowserClient::OnSandiumScriptedPopupCreated(')

def compose(repo,src,core,out):
    if out.exists() or out.is_symlink():raise ValueError('output must be a new directory')
    if git(src,'rev-parse','HEAD').decode().strip()!=CHROME or git(core,'rev-parse','HEAD').decode().strip()!=CORE:raise ValueError('incorrect source checkout')
    if git(repo,'rev-parse',BASE+'^{tree}').decode().strip()!='fe2e5d47e4a93744644ba74454bf73b0c860c339':raise ValueError('incorrect RawS base')
    ref={}
    for k,(path,oid) in REFS.items():
        b=git(repo,'show',REF+':'+path)
        if blob(b)!=oid:raise ValueError('incorrect reference '+path)
        ref[k]=b.decode()
    rows=verify_catalog(ref['catalog']); before={}; files={}
    recipe=json.loads(git(repo,'show',BASE+':raws-adblock/production-restore-recipe.json'))['files']
    def read(name):
        if name in files:return files[name]
        p=src/name
        if not p.is_file() or p.resolve()!=p:raise ValueError('missing or symlink '+name)
        b=p.read_bytes()
        if name in recipe: expected=recipe[name]['after_sha256']
        elif name.startswith('brave/'):
            expected=sha(git(core,'show',CORE+':'+name[6:]))
        else:expected=sha(git(src,'show',CHROME+':'+name))
        if sha(b)!=expected:raise ValueError('not the reviewed preimage: '+name)
        before[name]=expected;files[name]=b.decode();return files[name]
    def change(n,fn):files[n]=fn(read(n))
    def new(n,value):
        if (src/n).exists() or (src/n).is_symlink():raise ValueError('unexpected existing file '+n)
        before[n]=None;files[n]=value
    def apply(n,pairs):
        for a,b in pairs:change(n,lambda s:once(s,a,b))
    pre=lit(ref['pre'],'HELPERS');rule=lit(ref['resources'],'RULE')
    if rule not in local('snapshot.cc.inc'):raise ValueError('player rule mismatch')
    change(F,lambda s:factory(s,pre));change(H,header)
    change(PREFIX+'subresource_decision.cc',lambda s:once(s,'    case Resource::kFontResource:', '    case Resource::kSubFrame:\n    case Resource::kXhr:\n    case Resource::kMedia:\n    case Resource::kPing:\n    case Resource::kFontResource:'))
    for n in ['policy.h','style.h']:new(PREFIX+n,local(n))
    for n in ['subscription_service.h','subscription_policy.h']:new('chrome/browser/raws/'+n,local(n))
    new('chrome/browser/raws/catalog_generated.h',catalog_header(rows))
    new(PREFIX+'smoke1442.cc',local('smoke1442.cc'))
    def gn(s):
        s=once(s,'    "network_decision.h",','    "network_decision.h",\n    "policy.h",')
        s=once(s,'    sources = [ "document_subresource_factory.cc" ]','    sources = [ "document_subresource_factory.cc", "style.h" ]')
        return s+'\nexecutable("engine_smoke1442") {\n  testonly = true\n  sources = [ "smoke1442.cc" ]\n  deps = [ ":request_matcher", "//base" ]\n}\ngroup("host_smoke1442") {\n  testonly = true\n  deps = [ ":engine_smoke1442($host_toolchain)", ":engine_smoke($host_toolchain)" ]\n}\n'
    change(PREFIX+'BUILD.gn',gn)
    # Sandium's exact vendored parser/matcher edits; none of its Brave UI targets.
    vendor='third_party/rust/chromium_crates_io/vendor/adblock-v0_13/src/'
    for k in ['modifier','denyallow','index']:
        ns=defs(ref[k],{'edits'});edits=ns['edits']()
        for path,a,b in edits:apply('brave/'+vendor+str(path),[(a,b)])
    for path,edits in defs(ref['matcher'],{'edits'},{'VENDOR':vendor,'BROWSER':'components/brave_shields/content/browser/'})['edits']().items():
        if path.startswith(vendor):apply('brave/'+path,edits)
    # Exact reference mojo/renderer provenance, with no navigation ownership changes.
    with tempfile.TemporaryDirectory() as scratch:
        tmp=Path(scratch);(tmp/'popup_navigation.cc.inc').write_text(ref['inc'])
        for k in ['media','nav']:
            mod=types.ModuleType('pinned_'+k);mod.__file__=str(tmp/'port.py')
            exec(compile(ref[k],mod.__file__,'exec'),mod.__dict__)
            mapping=mod.EDITS if k=='media' else mod.edits()
            for path,edits in mapping.items():
                if not path.startswith('brave/'):apply(path,edits)
    cl='chrome/browser/chrome_content_browser_client.cc'; ch=cl[:-2]+'h'
    def client(s):
        incl=['base/timer/timer.h','base/supports_user_data.h','chrome/common/chrome_render_frame.mojom.h','content/public/browser/navigation_handle.h','content/public/browser/navigation_throttle.h','content/public/browser/navigation_throttle_registry.h','content/public/browser/web_contents_user_data.h','content/public/browser/render_frame_host.h','chrome/browser/content_settings/host_content_settings_map_factory.h','components/content_settings/core/browser/host_content_settings_map.h','mojo/public/cpp/bindings/associated_remote.h','net/base/url_util.h','net/base/registry_controlled_domains/registry_controlled_domain.h','third_party/blink/public/common/associated_interfaces/associated_interface_provider.h']
        guarded='#if BUILDFLAG(IS_ANDROID)\n'+''.join('#include "'+h+'"\n' for h in incl)+'#endif\n';s=once(s,'#include "build/build_config.h"\n','#include "build/build_config.h"\n'+guarded)
        tail = '  return !blocked_content::ConsiderForPopupBlocking(disposition) ||\n         blocked_content::MaybeBlockPopup(\n             web_contents, &opener_top_level_frame_url,\n             (*g_popup_navigation_delegate_factory)(std::move(nav_params)),\n             nullptr /*=open_url_params*/, blocked_params.features(),\n             HostContentSettingsMapFactory::GetForProfile(profile)) != nullptr;'
        s=once(s,'bool ChromeContentBrowserClient::CanCreateWindow(',adapt_early(lit(ref['popup'],'HELPERS'))+'bool ChromeContentBrowserClient::CanCreateWindow(')
        s=once(s,tail,tail.replace('  return ','  const bool chromium_allows = ',1)+'\n  if (!chromium_allows) return false;\n'+local('early.cc.inc')+'  return true;')
        sig='void ChromeContentBrowserClient::CreateThrottlesForNavigation('
        s=after_function_open(s,sig,'#if BUILDFLAG(IS_ANDROID)\n  if (registry.GetNavigationHandle().GetParentFrame()) registry.AddThrottle(std::make_unique<RawSSubframeFilter>(registry));\n  RawSCosmeticObserver::CreateForWebContents(registry.GetNavigationHandle().GetWebContents());\n  SandiumPopupNavigationThrottle::MaybeCreateAndAdd(registry);\n#endif\n',('registry',))
        return once(s,sig,local('subframe.cc.inc')+'\n'+local('cosmetic.cc.inc')+'\n'+adapt_throttle(ref['inc'])+'\n'+sig)
    change(cl,client)
    change(ch,lambda s:once(s,'  bool CanCreateWindow(', '#if BUILDFLAG(IS_ANDROID)\n  void OnSandiumScriptedPopupCreated(content::RenderFrameHost*,content::WebContents*) override;\n#endif\n  bool CanCreateWindow('))
    main='chrome/browser/chrome_browser_main_android.cc'
    apply(main,[('#include "components/sandium_adblock/document_subresource_factory.h"','#include "components/sandium_adblock/document_subresource_factory.h"\n#include "chrome/browser/raws/subscription_service.h"'),('  ChromeBrowserMainParts::PostProfileInit(profile, is_initial_profile);','  if (is_initial_profile) sandium::port1442::StartSubscriptions(profile);\n  ChromeBrowserMainParts::PostProfileInit(profile, is_initial_profile);')])
    apply('chrome/common/chrome_render_frame.mojom',[('interface ChromeRenderFrame {','interface ChromeRenderFrame {\n  [EnableIf=is_android] ApplyRawSHideStyles(url.mojom.Url document_url, string css);')])
    apply('chrome/renderer/chrome_render_frame_observer.h',[('  void SetCCTClientHeader(', '  void ApplyRawSHideStyles(const GURL&, const std::string&) override;\n  void SetCCTClientHeader(')])
    apply('chrome/renderer/chrome_render_frame_observer.cc',[('void ChromeRenderFrameObserver::SetCCTClientHeader(','''void ChromeRenderFrameObserver::ApplyRawSHideStyles(const GURL& url,
                                                   const std::string& css) {
  auto* frame = render_frame()->GetWebFrame();
  if (!frame || frame->IsProvisional() || css.empty()) {
    return;
  }
  auto doc = frame->GetDocument();
  if (doc.IsNull() || !doc.IsActive() || !doc.IsHTMLDocument() ||
      GURL(doc.Url()) != url) {
    return;
  }
  doc.InsertStyleSheet(blink::WebString::FromUtf8(css), nullptr,
                       blink::WebCssOrigin::kUser);
}

void ChromeRenderFrameObserver::SetCCTClientHeader(''')])
    # Publish once only after all source/digest/anchor checks succeed. Never
    # write either checkout. Refuse symlinked output paths and partial reruns.
    if out.parent.resolve()!=out.parent or any(out.is_relative_to(p) for p in (src,core,repo)):raise ValueError('output must be outside source trees')
    with tempfile.TemporaryDirectory(dir=out.parent) as td:
        dest=Path(td)/'delta';dest.mkdir(); manifest={}
        for n,text in sorted(files.items()):
            p=dest/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(text.encode());manifest[n]={'before':before[n],'after':sha(p.read_bytes())}
        (dest/'delta-receipt.json').write_text(json.dumps({'raws':BASE,'reference':REF,'chromium':CHROME,'brave':CORE,'files':manifest},indent=2)+'\n');dest.rename(out)
    return len(files)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('repo','chromium','brave','output'):ap.add_argument(name,type=Path)
    a=ap.parse_args();print('Generated files:',compose(a.repo.resolve(),a.chromium.resolve(),a.brave.resolve(),a.output.absolute()))
