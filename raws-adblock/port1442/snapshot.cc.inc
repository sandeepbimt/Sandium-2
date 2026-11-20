  bool Install(std::vector<std::string> bodies) {
    // Build off to the side: malformed input never clears the live engine.
    auto fs = adblock::new_filter_set(false);
    size_t left = 96u << 20;
    auto add = [&](const std::string& text, bool preprocess) {
      if (text.empty() || text.size() > left || text.size() > kMaxRulesBytes ||
          !base::IsStringUTF8(text) || text.find('\0') != std::string::npos) return false;
      left -= text.size();
      DATFileDataBuffer bytes(text.begin(),text.end());
      if (preprocess) PruneSandiumSubscription(bytes);
      return fs->add_filter_list_with_permissions(bytes, 0).result_kind == adblock::ResultKind::Success;
    };
    if (!add("! Title: Sandium player ad resources\n||ohjpfawpaap.in^$third-party,script,subdocument,image\n",false)) return false;
    for (const auto& body : bodies) if (!add(body,true)) return false;
    auto result = adblock::engine_from_filter_set(std::move(fs));
    if (result.result_kind != adblock::ResultKind::Success) return false;
    additional_.emplace(std::move(result.value));
    return true;
  }
  bool Popup(GURL target, GURL frame) {
    if (!primary_ || !additional_ || !target.SchemeIsHTTPOrHTTPS() || !frame.SchemeIsHTTPOrHTTPS()) return false;
    namespace d = net::registry_controlled_domains;
    const bool third = !d::SameDomainOrHost(target,frame,d::INCLUDE_PRIVATE_REGISTRIES);
    auto pass = [&](const adblock::Engine& e, bool matched, bool check_exceptions) {
      return e.matches(target.spec(),std::string(target.host()),std::string(frame.host()),
                       "popup",third,"GET",matched,check_exceptions);
    };
    return ::sandium::port1442::PopupMatch(pass(**primary_,false,true),
        [&](bool matched,bool exceptions){ return pass(**additional_,matched,exceptions); });
  }
  std::string Style(GURL url) {
    if (!primary_ || !additional_ || !url.SchemeIsHTTPOrHTTPS()) return {};
    std::set<std::string> hide, except;
    bool suppress_generic = false;
    for (const adblock::Engine* engine : {&**primary_, &**additional_}) {
      auto raw = engine->url_cosmetic_resources(url.spec());
      auto info = base::JSONReader::ReadDict(std::string_view(raw.data(),raw.size()),base::JSON_PARSE_RFC);
      if (!info) return {};
      suppress_generic |= info->FindBool("generichide").value_or(false);
      for (auto pair : {std::pair{"hide_selectors", &hide}, std::pair{"exceptions", &except}}) {
        if (auto* items=info->FindList(pair.first)) for (const auto& item : *items)
          if (item.is_string()) pair.second->insert(item.GetString());
      }
    }
    // The worker asks only the verified packaged engine for positive generic
    // rules. A subscribed list may supply an exception, not a new static rule.
    ::sandium::port1442::AppendPackagedGenericHide(
        suppress_generic, except, hide,
        [&](const auto& classes, const auto& ids, const auto& exceptions) {
          std::vector<std::string> matches;
          auto result = (**primary_).hidden_class_id_selectors(
              classes, ids, exceptions);
          if (result.result_kind == adblock::ResultKind::Success) {
            for (const auto& selector : result.value) {
              matches.emplace_back(selector);
            }
          }
          return matches;
        });
    return ::sandium::port1442::HideStyles(hide,except);
  }
