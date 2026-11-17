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
  policy.Set("generation", static_cast<double>(sandium_ubo::SelectedOwnerGeneration(context)));
  policy.Set("engineOwned", sandium_ubo::IsUboOwnerChosen(context));
  policy.Set("shieldsEnabled", brave_shields::IsBraveShieldsEnabled(map, first_party));
  policy.Set("adControl", brave_shields::ControlTypeToString(
      brave_shields::GetAdControlType(map, first_party)));
  policy.Set("cosmeticControl", brave_shields::ControlTypeToString(
      brave_shields::GetCosmeticFilteringControlType(map, first_party)));
  policy.Set("contextSource", source);
  details.Set("sandiumShields", std::move(policy));
}
