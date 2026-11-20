// SPDX-License-Identifier: MPL-2.0
// Copyright (c) 2021 The Brave Authors. Sandium adaptation of ad_block_engine.cc.
#include "components/sandium_adblock/request_matcher.h"

#include "components/sandium_adblock/standard_merge.h"
#include "net/base/registry_controlled_domains/registry_controlled_domain.h"

namespace sandium::adblock_native {
namespace {
using R = blink::mojom::ResourceType;
const char* Token(R resource) {
  switch (resource) {
    case R::kMainFrame: return "main_frame";
    case R::kSubFrame: return "sub_frame";
    case R::kStylesheet: return "stylesheet";
    case R::kScript: return "script";
    case R::kFavicon:
    case R::kImage: return "image";
    case R::kFontResource: return "font";
    case R::kSubResource: return "other";
    case R::kObject: return "object";
    case R::kMedia: return "media";
    case R::kXhr: return "xhr";
    case R::kPing: return "ping";
    default: return "";  // The pinned Brave adapter also leaves other types empty.
  }
}
}  // namespace

adblock::BlockerResult MatchPass(const adblock::Engine& engine,
                                 const GURL& url,
                                 R resource,
                                 const url::Origin& initiator,
                                 const std::string& method,
                                 bool prior_match,
                                 bool prior_exception) {
  namespace domains = net::registry_controlled_domains;
  const bool third_party = !domains::SameDomainOrHost(
      url, initiator, domains::INCLUDE_PRIVATE_REGISTRIES);
  return engine.matches(url.spec(), std::string(url.host()), initiator.host(),
                        Token(resource), third_party, method,
                        prior_match || prior_exception, !prior_exception);
}
adblock::BlockerResult MatchStandard(const adblock::Engine& primary,
                                     const adblock::Engine& additional,
                                     const GURL& url, R resource,
                                     const url::Origin& initiator,
                                     const std::string& method,
                                     bool prior_match, bool prior_exception) {
  namespace domains = net::registry_controlled_domains;
  const bool third_party = !domains::SameDomainOrHost(
      url, initiator, domains::INCLUDE_PRIVATE_REGISTRIES);
  const std::string host(url.host());
  const std::string sender = initiator.host();
  const std::string type(Token(resource));
  auto pass = [&](const adblock::Engine& engine, bool matched, bool excepted) {
    return engine.matches(url.spec(), host, sender, type, third_party, method,
                          matched || excepted, !excepted);
  };
  // Brave's network caller forces the aggressive *matching policy* for a
  // YouTube initiator even in Standard. This must not change the third-party
  // bit supplied to Rust; e.g. a $third-party rule still cannot match 1P.
  const bool keep_default_match = third_party || domains::SameDomainOrHost(
      initiator, url::Origin::CreateFromNormalizedTuple("https", "youtube.com", 443),
      domains::INCLUDE_PRIVATE_REGISTRIES);
  return internal::MergeStandard(pass(primary, prior_match, prior_exception),
      keep_default_match, prior_match, prior_exception, [&](bool m, bool e) {
        return pass(additional, m, e);
      });
}
}  // namespace sandium::adblock_native
