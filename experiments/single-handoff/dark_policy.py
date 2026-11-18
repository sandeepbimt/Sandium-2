"""Dormant document/revision authority over already-applied Sandium dark transport.

Never changes ordinary Chromium paint-holding timeouts or delays navigation.
"""
from pathlib import Path
import json
HERE=Path(__file__).parent
BASE=json.loads((HERE.parents[1]/'.circleci/features/dark-pages/renderer/patches.json').read_text())
HELPER='content/public/browser/sandium_dark_policy_authority.h'
HEADER='third_party/blink/public/common/web_preferences/web_preferences.h'
MOJOM='third_party/blink/public/mojom/webpreferences/web_preferences.mojom'
TRAITS='third_party/blink/public/common/web_preferences/web_preferences_mojom_traits.h'
READ='third_party/blink/common/web_preferences/web_preferences_mojom_traits.cc'
CLIENT='chrome/browser/chrome_content_browser_client.cc'
VIEW='third_party/blink/renderer/core/exported/web_view_impl.cc'
SETTINGS='third_party/blink/renderer/build/scripts/templates/settings_base.h.tmpl'
NAV='content/browser/renderer_host/navigation_request.cc'
BF='content/browser/renderer_host/render_frame_host_manager.cc'
PR='content/browser/renderer_host/page_impl.cc'
MARKER='SANDIUM_DARK_POLICY_AUTHORITY_V1'

def old_block(path, contains):
    found=[p['new'] for p in BASE if p['path']==path and contains in p['new']]
    if len(found)!=1:raise ValueError('Ambiguous underlying dark patch: '+path+' '+contains)
    return found[0]

SETTINGS_METHODS='''  // SANDIUM_DARK_POLICY_AUTHORITY_V1: commit installs authority before Document/style.
  void SetSandiumDarkPageFlagsForCommit(int flags, uint64_t revision) {
    sandium_dark_page_flags_ = flags < 0 ? -1 : (flags & 1);
    sandium_dark_policy_revision_ = revision;
  }
  void ApplySandiumDarkPagePolicy(int flags, uint64_t revision) {
    if (revision == 0 || revision <= sandium_dark_policy_revision_) return;
    sandium_dark_policy_revision_ = revision;
    SetSandiumDarkPageFlags(flags < 0 ? -1 : (flags & 1));
  }
  uint64_t GetSandiumDarkPolicyRevision() const { return sandium_dark_policy_revision_; }

  void SetFromStrings(const String& name, const String& value);'''
PREF_BLOCK='''  settings->SetForceDarkModeEnabled(prefs.force_dark_mode_enabled);
  // SANDIUM_DARK_POLICY_AUTHORITY_V1: metadata rejects stale documents; it never routes IPC.
  auto* sandium_frame = DynamicTo<LocalFrame>(web_view_impl->GetPage()->MainFrame());
  if (prefs.sandium_dark_page_flags >= -1 && prefs.sandium_dark_document_token &&
      sandium_frame && sandium_frame->GetDocument() &&
      sandium_frame->GetDocument()->Token().value() == *prefs.sandium_dark_document_token) {
    web_view_impl->GetPage()->GetSettings().ApplySandiumDarkPagePolicy(
        prefs.sandium_dark_page_flags, prefs.sandium_dark_policy_revision);
  }'''
CLIENT_BLOCK='''#if BUILDFLAG(IS_ANDROID)
// SANDIUM_DARK_POLICY_AUTHORITY_V1: flags and identity belong to one query epoch.
bool ApplySandiumCommittedDarkPolicy(WebContents* contents,
                                    content::SiteInstance& main_frame_site,
                                    WebPreferences* prefs) {
  const int previous_flags = prefs->sandium_dark_page_flags;
  const auto previous_token = prefs->sandium_dark_document_token;
  const uint64_t previous_revision = prefs->sandium_dark_policy_revision;
  auto* frame = contents->GetPrimaryMainFrame();
  auto* client = night_mode::WebContentsThemeClient::FromWebContents(contents);
  auto token = content::GetSandiumPrimaryDocumentToken(*contents, main_frame_site);
  if (!client || !frame || !token) {
    prefs->sandium_dark_page_flags = -2;
    prefs->sandium_dark_document_token.reset();
    prefs->sandium_dark_policy_revision = 0;
    return previous_flags != -2 || previous_token.has_value() || previous_revision != 0;
  }
  scoped_refptr<content::SiteInstance> expected_site(&main_frame_site);
  auto weak_contents = contents->GetWeakPtr();
  const uint64_t query_revision = content::BeginSandiumDarkPolicyQuery(*contents);
  int flags = -1;
  if (!frame->IsErrorDocument() && !frame->GetLastCommittedOrigin().opaque() &&
      frame->GetLastCommittedURL().SchemeIsHTTPOrHTTPS()) {
    const GURL document_url = frame->GetLastCommittedURL();
    flags = client->SandiumDarkPageFlags(document_url);
  }
  // A nested query wins. Do not overwrite prefs mutated by that query, and do
  // not touch the former RFH/client after calling the policy provider.
  if (!weak_contents || !content::IsCurrentSandiumDarkPolicyQuery(*weak_contents, query_revision) ||
      content::GetSandiumPrimaryDocumentToken(*weak_contents, *expected_site) != token) {
    return false;
  }
  const bool changed = flags != previous_flags || token != previous_token || previous_revision == 0;
  prefs->sandium_dark_page_flags = flags;
  prefs->sandium_dark_document_token = token;
  prefs->sandium_dark_policy_revision = changed ? query_revision : previous_revision;
  return changed;
}
#endif

void ChromeContentBrowserClient::OverrideWebPreferences('''

def patches():
    p={}
    def add(path,old,new):p.setdefault(path,[]).append((old,new))
    add(HEADER,'#include <map>','#include <map>\n#include <optional>\n#include <cstdint>\n#include "base/unguessable_token.h"')
    add(HEADER,'  int sandium_dark_page_flags = -2;','  int sandium_dark_page_flags = -2;\n  std::optional<base::UnguessableToken> sandium_dark_document_token;\n  uint64_t sandium_dark_policy_revision = 0;')
    add(MOJOM,'import "mojo/public/mojom/base/time.mojom";','import "mojo/public/mojom/base/time.mojom";\nimport "mojo/public/mojom/base/unguessable_token.mojom";')
    add(MOJOM,'  int32 sandium_dark_page_flags = -2;','  int32 sandium_dark_page_flags = -2;\n  mojo_base.mojom.UnguessableToken? sandium_dark_document_token;\n  uint64 sandium_dark_policy_revision = 0;')
    anchor='  static int32_t sandium_dark_page_flags('
    add(TRAITS,anchor,'  static const std::optional<base::UnguessableToken>& sandium_dark_document_token(\n      const blink::web_pref::WebPreferences& r) { return r.sandium_dark_document_token; }\n  static uint64_t sandium_dark_policy_revision(\n      const blink::web_pref::WebPreferences& r) { return r.sandium_dark_policy_revision; }\n'+anchor)
    add(READ,'#include "mojo/public/cpp/base/string16_mojom_traits.h"','#include "mojo/public/cpp/base/string16_mojom_traits.h"\n#include "mojo/public/cpp/base/unguessable_token_mojom_traits.h"')
    anchor='  out->sandium_dark_page_flags = data.sandium_dark_page_flags() < -1 ? -2 :\n      (data.sandium_dark_page_flags() < 0 ? -1 : (data.sandium_dark_page_flags() & 1));'
    add(READ,anchor,anchor+'\n  if (!data.ReadSandiumDarkDocumentToken(&out->sandium_dark_document_token)) return false;\n  out->sandium_dark_policy_revision = data.sandium_dark_policy_revision();')
    add(CLIENT,old_block(CLIENT,'bool ApplySandiumCommittedDarkPolicy'),CLIENT_BLOCK)
    # Existing standard includes are present across all baseline variants.
    add(CLIENT,'#include "content/public/browser/browser_context.h"','#include "content/public/browser/browser_context.h"\n#include "'+HELPER+'"')
    add(VIEW,old_block(VIEW,'SandiumDarkPolicyPreferences'),PREF_BLOCK)
    add(SETTINGS,'#include "third_party/blink/renderer/core/core_export.h"','#include <cstdint>\n#include "third_party/blink/renderer/core/core_export.h"')
    # Typography inserts its own methods before SetFromStrings. Own only the
    # existing dark method, never the shared insertion anchor or adjacent policy.
    old_settings=old_block(SETTINGS,'void SetSandiumDarkPageFlagsForCommit').split('  void SetFromStrings')[0]
    add(SETTINGS,old_settings,SETTINGS_METHODS.split('  void SetFromStrings')[0])
    add(SETTINGS,'  SettingsDelegate* delegate_;','  SettingsDelegate* delegate_;\n  uint64_t sandium_dark_policy_revision_ = 0;')
    navmojo='third_party/blink/public/mojom/navigation/navigation_params.mojom'
    add(navmojo,'  int32 sandium_dark_page_flags = -1;','  int32 sandium_dark_page_flags = -1;\n  uint64 sandium_dark_policy_revision = 0;')
    webnav='third_party/blink/public/web/web_navigation_params.h'
    add(webnav,'  int sandium_dark_page_flags = -1;','  int sandium_dark_page_flags = -1;\n  uint64_t sandium_dark_policy_revision = 0;')
    render='content/renderer/render_frame_impl.cc'
    anchor='  navigation_params->sandium_dark_page_flags = commit_params.sandium_dark_page_flags;'
    add(render,anchor,anchor+'\n  navigation_params->sandium_dark_policy_revision = commit_params.sandium_dark_policy_revision;')
    frame='third_party/blink/renderer/core/loader/frame_loader.cc'
    add(frame,'settings->SetSandiumDarkPageFlagsForCommit(policy >= 0 ? (policy & 1) : -1);','settings->SetSandiumDarkPageFlagsForCommit(policy >= 0 ? (policy & 1) : -1,\n          navigation_params->sandium_dark_policy_revision);')
    for path in (NAV,BF,PR):
        add(path,'#include "content/public/browser/content_browser_client.h"','#include "content/public/browser/content_browser_client.h"\n#include "'+HELPER+'"')
    old=old_block(NAV,'SanitizeRedirectsForCommit(common_params, commit_params);')
    add(NAV,'  SanitizeRedirectsForCommit(common_params, commit_params);',
        '  SanitizeRedirectsForCommit(common_params, commit_params);\n'
        '  auto sandium_weak_this = weak_factory_.GetWeakPtr();\n'
        '  commit_params->sandium_dark_policy_revision = NextSandiumDarkPolicyRevision();')
    # Page-text owns adjacent setup; only append after the existing dark query.
    dark_query=old[old.index('  if (IsInOutermostMainFrame()'):].rstrip()
    add(NAV,dark_query,dark_query+'\n  if (!sandium_weak_this) return;')
    for path in (NAV,'content/browser/renderer_host/navigation_entry_impl.cc','content/browser/renderer_host/navigation_controller_impl.cc'):
        add(path,'/*sandium_dark_page_flags=*/-1,','/*sandium_dark_page_flags=*/-1, /*sandium_dark_policy_revision=*/0,')
    page='third_party/blink/public/mojom/page/page.mojom'
    # This field occurs in both restore and activation structs, intentionally exactly twice.
    add(page,'  int32 sandium_dark_page_flags = -1;','  int32 sandium_dark_page_flags = -1;\n  uint64 sandium_dark_policy_revision = 0;')
    bf_old=old_block(BF,'auto* restored_main_frame = current_frame_host();')
    bf_new=bf_old.replace('      int sandium_policy = -1;', '      auto sandium_weak_this = GetWeakPtr();\n      uint64_t sandium_revision = NextSandiumDarkPolicyRevision();\n      int sandium_policy = -1;')
    bf_new=bf_new.replace('      auto* restored_main_frame = current_frame_host();', '      auto* restored_main_frame = current_frame_host();\n      auto sandium_target = restored_main_frame->GetWeakPtr();\n      const auto sandium_document = restored_main_frame->GetDocumentToken();')
    bf_new=bf_new.replace('      for (const auto& rvh : render_view_hosts_to_restore) {', '      if (!sandium_weak_this) return;\n      if (!sandium_target || current_frame_host() != sandium_target.get() ||\n          sandium_target->GetDocumentToken() != sandium_document) {\n        sandium_policy = -2;\n        sandium_revision = 0;\n      }\n      for (const auto& rvh : render_view_hosts_to_restore) {')
    add(BF,bf_old,bf_new)
    add(BF,'        page_restore_params->sandium_dark_page_flags = sandium_policy;','        page_restore_params->sandium_dark_page_flags = sandium_policy;\n        page_restore_params->sandium_dark_policy_revision = sandium_revision;')
    pr_old=old_block(PR,'bool view_transition_state_consumed = false;')
    pr_new=pr_old.replace('  int sandium_policy = -1;', '  auto sandium_weak_this = weak_factory_.GetWeakPtr();\n  uint64_t sandium_revision = NextSandiumDarkPolicyRevision();\n  int sandium_policy = -1;')
    pr_new=pr_new.replace('  int sandium_policy = -1;', '  auto sandium_target = main_document_->GetWeakPtr();\n  const auto sandium_document = main_document_->GetDocumentToken();\n  int sandium_policy = -1;')
    pr_new=pr_new.replace('  for (const auto& rvh : render_view_hosts) {', '  if (!sandium_weak_this) return;\n  if (!sandium_target || &main_document_.get() != sandium_target.get() ||\n      sandium_target->GetDocumentToken() != sandium_document) {\n    sandium_policy = -2;\n    sandium_revision = 0;\n  }\n  for (const auto& rvh : render_view_hosts) {')
    add(PR,pr_old,pr_new)
    add(PR,'    params->sandium_dark_page_flags = sandium_policy;','    params->sandium_dark_page_flags = sandium_policy;\n    params->sandium_dark_policy_revision = sandium_revision;')
    add(VIEW,'page->GetSettings().SetSandiumDarkPageFlags(policy < 0 ? -1 : (policy & 1));','if (policy >= -1) page->GetSettings().ApplySandiumDarkPagePolicy(\n        policy < 0 ? -1 : (policy & 1), page_restore_params->sandium_dark_policy_revision);')
    add(VIEW,'GetPage()->GetSettings().SetSandiumDarkPageFlags(\n      sandium_policy < 0 ? -1 : (sandium_policy & 1));','if (sandium_policy >= -1) GetPage()->GetSettings().ApplySandiumDarkPagePolicy(\n      sandium_policy < 0 ? -1 : (sandium_policy & 1),\n      prerender_page_activation_params->sandium_dark_policy_revision);')
    return p

def transform(path,text):
    for old,new in patches()[path]:
        count=2 if (path=='third_party/blink/public/mojom/page/page.mojom' and old=='  int32 sandium_dark_page_flags = -1;') or (path==NAV and old=='/*sandium_dark_page_flags=*/-1,') else 1
        if text.count(new)==count and old not in text.replace(new,''):continue
        if text.count(old)!=count or new in text:raise ValueError('Dark authority anchor drift: '+path+' '+old[:70])
        text=text.replace(old,new)
    return text

def plan(root):
    root=Path(root)
    return {root/path:transform(path,(root/path).read_text()) for path in patches()}

# Registration remains separately planned: this authority is referenced by cross-platform
# navigation code, so its sources must not be placed inside an Android-only GN block.
REGISTRATION={
 'content/browser/BUILD.gn': ('    "renderer_host/render_frame_host_impl.cc",\n','    "renderer_host/sandium_dark_policy_authority.cc",\n'),
 'content/public/browser/BUILD.gn': ('    "site_instance.h",\n','    "sandium_dark_policy_authority.h",\n'),
}
def registration_transform(path,text):
    anchor,addition=REGISTRATION[path]
    if text.count(anchor)!=1:raise ValueError('Dark authority GN drift: '+path)
    if addition in text:
        if text.count(addition)!=1 or anchor+addition not in text:raise ValueError('Dark authority GN partial/reordered: '+path)
        return text
    return text.replace(anchor,anchor+addition,1)
def registration_plan(root):
    root=Path(root)
    result={root/p:registration_transform(p,(root/p).read_text()) for p in REGISTRATION}
    for p in (HELPER,'content/browser/renderer_host/sandium_dark_policy_authority.cc'):
        source=(HERE/'components'/p).read_text();target=root/p
        if target.exists() and target.read_text()!=source:raise ValueError('Existing authority component differs: '+p)
        result[target]=source
    return result
