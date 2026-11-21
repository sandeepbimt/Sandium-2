#if BUILDFLAG(IS_ANDROID)
  if (ShouldBlockSandiumAdTab(opener, opener_url, opener_top_level_frame_url,
                              target_url, disposition)) return false;
  // Reject the *first* captured ad hop even before the async matcher is ready.
  // Identify the issuer by its committed origin, not by a renderer-supplied URL.
  // This runs after Chromium has made its own popup decision. It never handles
  // ordinary navigation, a media request, form submission in the current tab,
  // or an Android intent. Do not generalize /5/, psid, or a gesture in isolation.
  if (opener && opener->GetParent() && opener_top_level_frame_url.SchemeIsHTTPOrHTTPS() &&
      opener_top_level_frame_url.DomainIs("xmaza.tv") && target_url.SchemeIsHTTPOrHTTPS() &&
      target_url.host() == "cartographicalrunafoulstreet.com" &&
      (disposition == WindowOpenDisposition::kNewForegroundTab ||
       disposition == WindowOpenDisposition::kNewBackgroundTab ||
       disposition == WindowOpenDisposition::kNewPopup ||
       disposition == WindowOpenDisposition::kNewWindow)) {
    const auto issuer = opener->GetLastCommittedOrigin().GetURL();
    const auto path = target_url.path();
    if (issuer.SchemeIsHTTPOrHTTPS() &&
        (issuer.DomainIs("caseyseemavoid.com") || issuer.DomainIs("atdzfavz.in")) &&
        path.starts_with("/5/") && path.size() == 35 &&
        path.substr(3).find_first_not_of("0123456789abcdefABCDEF") == path.npos) {
      for (net::QueryIterator it(target_url); !it.IsAtEnd(); it.Advance()) {
        const auto value = it.GetValue();
        if (it.GetKey() != "psid" || value.empty() ||
            value.find_first_not_of("0123456789") != value.npos) continue;
        auto* map = HostContentSettingsMapFactory::GetForProfile(profile);
        if (map && map->GetContentSetting(opener_top_level_frame_url, opener_top_level_frame_url,
                                          ContentSettingsType::POPUPS) != CONTENT_SETTING_ALLOW)
          return false;
        break;
      }
    }
  }
#endif
