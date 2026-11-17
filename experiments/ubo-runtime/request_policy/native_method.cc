// Copyright 2026 Sandium. SPDX-License-Identifier: MPL-2.0
bool BraveExtensionsAPIClient::SupportsPrivateWebRequestPolicy(
    const ExtensionId& extension_id) const {
  return extension_id == sandium_ubo::kExtensionId;
}

void BraveExtensionsAPIClient::AugmentWebRequestEventForExtension(
    content::BrowserContext* context,
    const WebRequestInfo& request,
    const ExtensionId& extension_id,
    bool crosses_incognito,
    base::DictValue& details) const {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  if (!context || context->IsOffTheRecord() || crosses_incognito ||
      extension_id != sandium_ubo::kExtensionId)
    return;
  auto* registry = ExtensionRegistry::Get(context);
  const Extension* extension = registry
      ? registry->enabled_extensions().GetByID(extension_id) : nullptr;
  if (!extension || !Manifest::IsComponentLocation(extension->location()) ||
      extension->version().GetString() != sandium_ubo::kVersion)
    return;

  // A navigation is evaluated against its destination, never the old page.
  // Other requests use their real top-frame origin. Worker requests without
  // a frame fall back to their native initiator, like BraveRequestInfo.
  GURL first_party;
  int page_epoch = 0;
  std::string page_document_id;
  const char* source = "default";
  if (request.web_request_type == WebRequestResourceType::MAIN_FRAME) {
    first_party = url::Origin::Create(request.url).GetURL();
    source = "navigation";
  } else {
    auto* frame = content::RenderFrameHost::FromID(request.global_id);
    if (!frame) frame = content::RenderFrameHost::FromID(request.parent_routing_id);
    if (frame && frame->GetOutermostMainFrame()) {
      first_party = frame->GetOutermostMainFrame()->GetLastCommittedOrigin().GetURL();
      if (!first_party.is_empty()) source = "top-frame";
      page_document_id = ExtensionApiFrameIdMap::GetDocumentId(
          frame->GetOutermostMainFrame()).ToString();
      if (auto* contents = content::WebContents::FromRenderFrameHost(frame)) {
        if (auto* entry = contents->GetController().GetLastCommittedEntry())
          page_epoch = entry->GetUniqueID();
      }
    }
    if (first_party.is_empty() && request.initiator &&
        !request.initiator->opaque()) {
      first_party = request.initiator->GetURL();
      source = "initiator";
    }
  }
  auto* profile = Profile::FromBrowserContext(context);
  auto* map = HostContentSettingsMapFactory::GetForProfile(profile);
  if (!map) return;
  // Empty first_party deliberately uses the same native default-policy lookup
  // as frameless Brave requests; never guess a hostname from an ad URL.
  base::DictValue policy;
  policy.Set("protocol", 1);
  // Zero for main-frame navigations and frameless requests: do not attribute
  // their blocked counters to the previous committed document.
  policy.Set("pageEpoch", page_epoch);
  policy.Set("pageDocumentId", page_document_id);
  policy.Set("generation", static_cast<double>(sandium_ubo::SelectedOwnerGeneration(context)));
  policy.Set("engineOwned", sandium_ubo::IsUboOwnerChosen(context));
  policy.Set("runtimeAvailable", !sandium_ubo::MustBlockAdRequest(context));
  policy.Set("shieldsEnabled", brave_shields::IsBraveShieldsEnabled(map, first_party));
  policy.Set("adControl", brave_shields::ControlTypeToString(
      brave_shields::GetAdControlType(map, first_party)));
  policy.Set("cosmeticControl", brave_shields::ControlTypeToString(
      brave_shields::GetCosmeticFilteringControlType(map, first_party)));
  policy.Set("contextSource", source);
  details.Set("sandiumShields", std::move(policy));
}

// Bridge caller has already checked request generation, page epoch and dedup.
// Repeat capability/context checks at the native observer boundary.
bool BraveExtensionsAPIClient::ReportPrivateBlockedResource(
    const ExtensionId& extension_id, content::WebContents* contents,
    const GURL& url) const {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  if (!contents || extension_id != sandium_ubo::kExtensionId ||
      !url.SchemeIsHTTPOrHTTPS()) return false;
  auto* context = contents->GetBrowserContext();
  if (!context || context->IsOffTheRecord() ||
      !sandium_ubo::IsUboOwnerChosen(context) ||
      sandium_ubo::MustBlockAdRequest(context)) return false;
  auto* registry = ExtensionRegistry::Get(context);
  const Extension* extension = registry
      ? registry->enabled_extensions().GetByID(extension_id) : nullptr;
  if (!extension || !Manifest::IsComponentLocation(extension->location()) ||
      extension->version().GetString() != sandium_ubo::kVersion) return false;
  brave_shields::BraveShieldsWebContentsObserver::DispatchBlockedEventForWebContents(
      brave_shields::kAds, url.spec(), contents);
  return true;
}

namespace {
bool CanReadFilterLists(content::BrowserContext* context, const ExtensionId& id) {
  if (!context || context->IsOffTheRecord() || id != sandium_ubo::kExtensionId) return false;
  auto* registry = ExtensionRegistry::Get(context);
  const Extension* extension = registry ? registry->enabled_extensions().GetByID(id) : nullptr;
  return extension && Manifest::IsComponentLocation(extension->location()) &&
      extension->version().GetString() == sandium_ubo::kVersion;
}
}
base::DictValue BraveExtensionsAPIClient::GetPrivateFilterLists(
    content::BrowserContext* context, const ExtensionId& extension_id) const {
  DCHECK_CURRENTLY_ON(content::BrowserThread::UI);
  base::DictValue snapshot;
  snapshot.Set("ready", false);
  snapshot.Set("revision", "");
  snapshot.Set("entries", base::ListValue());
  if (!CanReadFilterLists(context, extension_id) ||
      !g_browser_process || !g_browser_process->local_state()) return snapshot;
  // The existing service owns asynchronous subscription migration. Initialize
  // its lazy singleton before waiting for that migration; never seed here.
  if (!g_brave_browser_process || !g_brave_browser_process->ad_block_service())
    return snapshot;
  auto* prefs = g_browser_process->local_state();
  // Only the product's completed native seeding migration permits cutover.
  // Afterwards an empty map is a valid user choice; never reseed deleted lists.
  const bool migrated = prefs->FindPreference(brave_shields::prefs::kSandiumDefaultFilterListsMigrated) &&
      prefs->GetBoolean(brave_shields::prefs::kSandiumDefaultFilterListsMigrated);
  bool ready = migrated;
  snapshot.Set("mode", "sandium-subscriptions-only");
  base::ListValue entries;
  size_t total_bytes = 0;
  auto append = [&](const std::string& id, const std::string& text,
                    bool enabled, const char* kind) {
    total_bytes += id.size() + text.size();
    if (entries.size() >= 4096 || total_bytes > 4 * 1024 * 1024) {
      ready = false;
      return;
    }
    const GURL url(text);
    const bool available = url.is_valid() && url.SchemeIsHTTPOrHTTPS() &&
        !url.has_username() && !url.has_password() && text.size() <= 8192;
    if (enabled && !available) ready = false;
    base::DictValue entry;
    entry.Set("id", id); entry.Set("url", text);
    entry.Set("enabled", enabled); entry.Set("kind", kind);
    entry.Set("available", available);
    entries.Append(std::move(entry));
  };
  const auto& subscriptions = g_browser_process->local_state()->GetDict(
      brave_shields::prefs::kAdBlockListSubscriptions);
  for (const auto item : subscriptions) {
    const auto* settings = item.second.GetIfDict();
    if (!settings) { ready = false; continue; }
    append(std::string(item.first), std::string(item.first),
        settings->FindBool("enabled").value_or(false), "subscription");
  }
  snapshot.Set("ready", ready);
  snapshot.Set("entries", std::move(entries));
  auto serialized = base::WriteJson(snapshot);
  if (!serialized) { snapshot.Set("ready", false); return snapshot; }
  snapshot.Set("revision", base::ToLowerASCII(base::HexEncode(crypto::SHA256HashString(*serialized))));
  return snapshot;
}
