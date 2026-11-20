// SPDX-License-Identifier: MPL-2.0
// Copyright (c) The Brave Authors. Sandium adaptation of the decision step in
// browser/net/brave_ad_block_tp_network_delegate_helper.cc at bd6d26d1.
#ifndef COMPONENTS_SANDIUM_ADBLOCK_NETWORK_DECISION_H_
#define COMPONENTS_SANDIUM_ADBLOCK_NETWORK_DECISION_H_

#include <optional>
#include <string>
#include <string_view>
#include <utility>

#include "components/sandium_adblock/request_matcher.h"

namespace sandium::adblock_native {
// One request only: these flags survive an alias check, never a new request.
struct MatchHistory {
  bool rule = false;
  bool exception = false;
  bool important = false;
  bool blocked() const { return important || (rule && !exception); }
};

struct NetworkDecision {
  MatchHistory history;
  std::optional<std::string> rewritten_url;
  std::string mock_data_url;
};

// Decision only, no DNS or I/O. The caller retains the original URL and must
// not treat the canonical matching URL as a redirect or persist either host.
inline NetworkDecision ResolveDecision(const adblock::BlockerResult& match,
                                       MatchHistory prior,
                                       std::string_view method,
                                       bool checking_alias) {
  NetworkDecision out{{prior.rule || match.matched,
                       prior.exception || match.has_exception,
                       prior.important || match.important}, std::nullopt, {}};
  if (match.redirect.has_value) {
    out.mock_data_url = std::string(match.redirect.value);
  }
  if (!checking_alias && match.rewritten_url.has_value &&
      (method == "GET" || method == "HEAD" || method == "OPTIONS")) {
    std::string spec(match.rewritten_url.value);
    if (GURL(spec).is_valid()) out.rewritten_url = std::move(spec);
  }
  return out;
}
}  // namespace sandium::adblock_native
#endif  // COMPONENTS_SANDIUM_ADBLOCK_NETWORK_DECISION_H_
