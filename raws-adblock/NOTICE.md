The experimental matcher is adapted from Brave Software's MPL-2.0
`components/brave_shields/content/browser/ad_block_engine.cc` and the Standard
network result composition in `ad_block_engine_wrapper.cc` at
`bd6d26d1bced03c17a98baa86d2cd3425d543d1b`. The bridge build-file fixture is
from the same Brave release; its copyright is preserved. See LICENSE-MPL-2.0.
Other independently written files in this directory are provided under MPL-2.0.
The source-preparation command copies only selected, versioned third-party files;
it does not relicense them. Retain their notices, audit all transitive crates,
filter data and scriptlets separately, and publish the exact covered source for
each distributed build. No Brave trademarks, service credentials, filter
component redistributions, or uBlock Origin extension are supplied here.

The global initiator policy and network action resolution in request_matcher.cc
and network_decision.h also adapt the pinned Brave helper
`browser/net/brave_ad_block_tp_network_delegate_helper.cc`, Git blob
`22b123bc93c898e2fc4ed0f87b83e8587cbdd43c`, under MPL-2.0.
