#if BUILDFLAG(IS_ANDROID)
namespace {

// AdGuard Base matches /?scontext_r=*&nrb= across ad hosts. The observed
// tab-up auction also carries nrb=1, nortb_fallback and click metadata.
// https://github.com/uBlockOrigin/uAssets/issues/28058
// Leave the encoded click metadata opaque.
bool IsSandiumAdTabTarget(const GURL& target) {
  if (!target.SchemeIsHTTPOrHTTPS() || !target.path().ends_with("/") ||
      !target.query().starts_with("scontext_r=")) {
    return false;
  }
  net::QueryIterator fields(target);
  if (fields.IsAtEnd() || fields.GetValue().empty()) {
    return false;
  }
  bool has_nrb_flag = false;
  bool has_auction_fallback = false;
  bool has_metadata = false;
  for (fields.Advance(); !fields.IsAtEnd(); fields.Advance()) {
    const auto key = fields.GetKey();
    if (key == "nrb") {
      has_nrb_flag = fields.GetValue() == "1";
    } else if (key == "param_3") {
      has_auction_fallback = fields.GetValue() == "nortb_fallback";
    } else if (key == "md") {
      has_metadata = !fields.GetValue().empty();
    }
  }
  return has_nrb_flag && has_auction_fallback && has_metadata;
}

bool SameSandiumSite(const GURL& a, const GURL& b) {
  return net::registry_controlled_domains::SameDomainOrHost(
      a, b, net::registry_controlled_domains::INCLUDE_PRIVATE_REGISTRIES);
}

// The recorded ad exchange used this route even before video playback began.
// Never classify a popup from the psid query key alone.
bool IsSandiumAdExchangeTarget(const GURL& target) {
  const auto path = target.path();
  if (!path.starts_with("/10/") || path.size() != 4 + 32 ||
      path.substr(4).find_first_not_of("0123456789abcdefABCDEF") != path.npos) {
    return false;
  }
  for (net::QueryIterator fields(target); !fields.IsAtEnd(); fields.Advance()) {
    const auto value = fields.GetValue();
    if (fields.GetKey() == "psid" && !value.empty() &&
        value.find_first_not_of("0123456789") == value.npos) {
      return true;
    }
  }
  return false;
}

// Keep the recognized exchange hop on the early path. The mere presence
// of media is not an ad signal; other scripted windows can consult native
// popup rules during navigation, including list exceptions.
bool IsSandiumEmbeddedAdTab(content::RenderFrameHost* opener,
                            const GURL& opener_url,
                            const GURL& top_url,
                            const GURL& target) {
  if (!opener->GetParent()) {
    return false;
  }
  // An initial about:blank/srcdoc frame can inherit its parent's origin.
  const GURL source = opener_url.SchemeIsHTTPOrHTTPS()
                          ? opener_url
                          : opener->GetLastCommittedOrigin().GetURL();
  if (!source.SchemeIsHTTPOrHTTPS() || SameSandiumSite(source, top_url)) {
    return false;
  }
  return target.SchemeIsHTTPOrHTTPS() && !SameSandiumSite(source, target) &&
         IsSandiumAdExchangeTarget(target);
}

bool ShouldBlockSandiumAdTab(content::RenderFrameHost* opener,
                             const GURL& opener_url,
                             const GURL& top_url,
                             const GURL& target,
                             WindowOpenDisposition disposition) {
  switch (disposition) {
    case WindowOpenDisposition::NEW_FOREGROUND_TAB:
    case WindowOpenDisposition::NEW_BACKGROUND_TAB:
    case WindowOpenDisposition::NEW_WINDOW:
    case WindowOpenDisposition::NEW_POPUP:
      break;
    default:
      return false;
  }
  if (!top_url.SchemeIsHTTPOrHTTPS() || SameSandiumSite(top_url, target) ||
      (!IsSandiumAdTabTarget(target) &&
       !IsSandiumEmbeddedAdTab(opener, opener_url, top_url, target))) {
    return false;
  }
  auto* profile = Profile::FromBrowserContext(opener->GetBrowserContext());
  auto* map = HostContentSettingsMapFactory::GetForProfile(profile);
  return map && brave_shields::IsBraveShieldsEnabled(map, top_url) &&
         map->GetContentSetting(top_url, top_url, ContentSettingsType::POPUPS) !=
             CONTENT_SETTING_ALLOW &&
         brave_shields::ShouldBlockAdRedirect(*profile->GetPrefs(), top_url);
}

}  // namespace
#endif  // BUILDFLAG(IS_ANDROID)

