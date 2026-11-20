// SPDX-License-Identifier: MPL-2.0
#ifndef COMPONENTS_SANDIUM_ADBLOCK_SUBRESOURCE_DECISION_H_
#define COMPONENTS_SANDIUM_ADBLOCK_SUBRESOURCE_DECISION_H_

#include "components/sandium_adblock/network_decision.h"

namespace sandium::adblock_native {

enum class SubresourceAction {
  kNotEvaluated,
  kAllow,
  kBlock,
  // This adapter cannot safely fulfill a rule requiring a response substitute
  // or a URL rewrite. Do not convert it into a blanket cancellation.
  kUnsupportedAction,
};

// Call on the sequence owning both engines. Supply null unless both collections
// belong to a single ready snapshot. The caller must independently verify that
// the factory is kDocumentSubResource and that the initiator is trustworthy.
// Call separately per redirect; never carry prior match flags between URLs.
SubresourceAction DecideDocumentSubresource(
    const adblock::Engine* default_engine,
    const adblock::Engine* additional_engine,
    const GURL& url,
    blink::mojom::ResourceType resource,
    const url::Origin& initiator,
    const std::string& method);

}  // namespace sandium::adblock_native

#endif  // COMPONENTS_SANDIUM_ADBLOCK_SUBRESOURCE_DECISION_H_
