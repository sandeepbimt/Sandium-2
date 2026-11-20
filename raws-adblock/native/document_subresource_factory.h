// SPDX-License-Identifier: MPL-2.0
#ifndef COMPONENTS_SANDIUM_ADBLOCK_DOCUMENT_SUBRESOURCE_FACTORY_H_
#define COMPONENTS_SANDIUM_ADBLOCK_DOCUMENT_SUBRESOURCE_FACTORY_H_

#include <string>

namespace network {
class URLLoaderFactoryBuilder;
}

namespace url {
class Origin;
}

namespace sandium::adblock_native {

// Browser startup only; call on the browser UI sequence. Supply an approved,
// locally embedded and integrity-checked UTF-8 rules asset. This API does not
// read from URLs, files, preferences, renderer messages, or command-line flags.
// Empty, malformed or repeated inputs do not enable or replace the engine.
void InitializeDocumentSubresourceRules(std::string verified_rules);

// Browser UI only. Caller must supply only the document-subresource factory
// and the browser-supplied non-opaque origin of that document factory.
void MaybeAppendDocumentSubresourceFactory(
    network::URLLoaderFactoryBuilder& builder,
    const url::Origin& document_origin);

}  // namespace sandium::adblock_native
#endif  // COMPONENTS_SANDIUM_ADBLOCK_DOCUMENT_SUBRESOURCE_FACTORY_H_
