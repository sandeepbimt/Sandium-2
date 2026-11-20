// SPDX-License-Identifier: MPL-2.0
// Derived from components/brave_shields/content/browser/ad_block_engine.cc.
// Copyright (c) 2021 The Brave Authors. See LICENSE-MPL-2.0 and NOTICE.md.
#ifndef COMPONENTS_SANDIUM_ADBLOCK_REQUEST_MATCHER_H_
#define COMPONENTS_SANDIUM_ADBLOCK_REQUEST_MATCHER_H_

#include <string>

#include "brave/components/brave_shields/core/common/adblock/rs/src/lib.rs.h"
#include "third_party/blink/public/mojom/loader/resource_load_info.mojom-shared.h"
#include "url/gurl.h"
#include "url/origin.h"

namespace sandium::adblock_native {
// Invoke on the sequence owning |engine|. This is a single engine pass, not
// Brave's final Standard policy. Never cancel a request from `matched` alone.
adblock::BlockerResult MatchPass(const adblock::Engine& engine,
                                 const GURL& url,
                                 blink::mojom::ResourceType resource,
                                 const url::Origin& initiator,
                                 const std::string& method,
                                 bool prior_match,
                                 bool prior_exception);
// Global Standard rule-collection evaluation; returns the full structured
// action. The network caller must still enforce it and handle CNAME redirects.
adblock::BlockerResult MatchStandard(const adblock::Engine& default_engine,
                                     const adblock::Engine& additional_engine,
                                     const GURL& url,
                                     blink::mojom::ResourceType resource,
                                     const url::Origin& initiator,
                                     const std::string& method,
                                     bool prior_match = false,
                                     bool prior_exception = false);
}  // namespace sandium::adblock_native
#endif  // COMPONENTS_SANDIUM_ADBLOCK_REQUEST_MATCHER_H_
