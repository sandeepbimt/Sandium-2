// SPDX-License-Identifier: MPL-2.0
// Real CXX bridge and two upstream Rust engines; lab inputs, not shipping lists.
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <utility>
#include <vector>

#include "components/sandium_adblock/subresource_decision.h"

namespace {
using R = blink::mojom::ResourceType;
auto Build(const std::string& text) {
  auto filters = adblock::new_filter_set(false);
  const std::vector<uint8_t> rules(text.begin(), text.end());
  const auto added = filters->add_filter_list(rules);
  if (added.result_kind != adblock::ResultKind::Success) {
    std::fputs("filter input was rejected\n", stderr);
    std::exit(2);
  }
  return adblock::engine_from_filter_set(std::move(filters));
}
}  // namespace

int main() {
  if (!adblock::set_domain_resolver()) return 1;
  auto primary = Build("||ads.example.test^$script\n"
                       "||youtube.com/house.js$script\n"
                       "||youtube.com/third.js$script,third-party\n"
                       "||youtube.com.example.test/house.js$script\n"
                       "||ads.example.test/urgent.js$script,important\n");
  auto extra = Build("@@||ads.example.test/allowed.js$script\n"
                     "@@||ads.example.test/urgent.js$script\n"
                     "||example.test/local-extra.js$script\n");
  if (primary.result_kind != adblock::ResultKind::Success ||
      extra.result_kind != adblock::ResultKind::Success) return 3;
  struct Case { const char* name; const char* url; const char* site; R type;
                bool block; };
  const Case cases[] = {
    {"third-party", "https://ads.example.test/ad.js", "https://publisher.test", R::kScript, true},
    {"exception", "https://ads.example.test/allowed.js", "https://publisher.test", R::kScript, false},
    {"important", "https://ads.example.test/urgent.js", "https://publisher.test", R::kScript, true},
    {"type", "https://ads.example.test/ad.js", "https://publisher.test", R::kImage, false},
    {"ordinary-first-party", "https://ads.example.test/ad.js", "https://www.example.test", R::kScript, false},
    {"additional-first-party", "https://example.test/local-extra.js", "https://www.example.test", R::kScript, true},
    {"youtube-initiator", "https://youtube.com/house.js", "https://m.youtube.com", R::kScript, true},
    {"not-fake-third-party", "https://youtube.com/third.js", "https://m.youtube.com", R::kScript, false},
    {"lookalike", "https://youtube.com.example.test/house.js", "https://youtube.com.example.test", R::kScript, false},
  };
  for (const auto& c : cases) {
    auto matched = sandium::adblock_native::MatchStandard(*primary.value, *extra.value,
        GURL(c.url), c.type, url::Origin::Create(GURL(c.site)), "GET");
    auto decision = sandium::adblock_native::ResolveDecision(matched, {}, "GET", false);
    const auto action = sandium::adblock_native::DecideDocumentSubresource(
        &*primary.value, &*extra.value, GURL(c.url), c.type,
        url::Origin::Create(GURL(c.site)), "GET");
    using A = sandium::adblock_native::SubresourceAction;
    if (action != (c.block ? A::kBlock : A::kAllow) ||
        decision.history.blocked() != c.block ||
        (std::string(c.name) == "exception" && !decision.history.exception) ||
        (std::string(c.name) == "important" && !decision.history.important)) {
      std::fprintf(stderr, "FAIL %s: match=%d exception=%d important=%d\n", c.name,
                   decision.history.rule, decision.history.exception, decision.history.important);
      return 4;
    }
    std::printf("ok %s\n", c.name);
  }
  std::puts("RAWS_ENGINE_SMOKE_V2_PASS");
  return 0;
}
