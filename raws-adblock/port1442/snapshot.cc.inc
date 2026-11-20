  static std::vector<std::string> ResolveGenericKeys(
      const adblock::Engine& engine,
      const ::sandium::port1442::SimpleGenericCensus& keys) {
    return keys.Resolve([&](const auto& classes, const auto& ids) {
      // An empty exception vector is correct at compile time: the exact
      // exception union is enforced when this document's CSS is generated.
      std::vector<std::string> matches;
      auto result = engine.hidden_class_id_selectors(
          classes, ids, std::vector<std::string>{});
      if (result.result_kind == adblock::ResultKind::Success) {
        for (const auto& selector : result.value) {
          matches.emplace_back(selector);
        }
      }
      return matches;
    });
  }

  std::vector<std::string> generic_selectors_;

  bool Install(std::vector<std::string> bodies) {
    // Build off to the side: malformed input never clears the live engine.
    auto fs = adblock::new_filter_set(false);
    ::sandium::port1442::SimpleGenericCensus keys(
        ::sandium::port1442::kSubscriptionGenericCandidateLimit);
    size_t left = 96u << 20;
    auto add = [&](const std::string& text, bool preprocess) {
      if (text.empty() || text.size() > left || text.size() > kMaxRulesBytes ||
          !base::IsStringUTF8(text) || text.find('\0') != std::string::npos) return false;
      left -= text.size();
      DATFileDataBuffer bytes(text.begin(),text.end());
      if (preprocess) PruneSandiumSubscription(bytes);
      if (fs->add_filter_list_with_permissions(bytes, 0).result_kind !=
          adblock::ResultKind::Success) return false;
      if (preprocess && !bytes.empty()) {
        keys.AddList(
            std::string_view(reinterpret_cast<const char*>(bytes.data()), bytes.size()),
            ::sandium::port1442::kSubscriptionGenericPerList);
      }
      return true;
    };
    if (!add("! Title: Sandium player ad resources\n||ohjpfawpaap.in^$third-party,script,subdocument,image\n",false)) return false;
    for (const auto& body : bodies) if (!add(body,true)) return false;
    auto result = adblock::engine_from_filter_set(std::move(fs));
    if (result.result_kind != adblock::ResultKind::Success) return false;
    generic_selectors_ = ResolveGenericKeys(*result.value, keys);
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
    auto css = ::sandium::port1442::HideStyles(hide, except);
    ::sandium::port1442::AppendSimpleGenericStyles(
        css, suppress_generic, generic_selectors_, hide, except);
    return css;
  }
