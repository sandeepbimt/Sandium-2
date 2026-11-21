// SPDX-License-Identifier: MPL-2.0
// Adapted from Sandium #1442 ad-redirects/popup.py and filter-compat/popup_matcher.py.
#ifndef COMPONENTS_SANDIUM_ADBLOCK_PORT1442_POLICY_H_
#define COMPONENTS_SANDIUM_ADBLOCK_PORT1442_POLICY_H_
#include <string_view>
namespace sandium::port1442 {
// Audit: #1471's player frame loaded two scripts, an ad iframe and push-creative GIFs.
// Feed the rules to the existing additional engine at startup AND on every refresh.
// Never block a player host, a media CDN, playlist API, or a payment application.
inline constexpr char kPlayerIncidentRules[] = R"raws(! RawS #1471 player abuse
||atdzfavz.in^$script,subdocument,image,other,third-party,domain=caseyseemavoid.com|xmaza.tv
||cartographicalrunafoulstreet.com/5/*?psid=$popup,third-party,domain=caseyseemavoid.com|atdzfavz.in|xmaza.tv
||ablelaunchshorts.com/2060440?$popup,third-party,domain=caseyseemavoid.com|atdzfavz.in|xmaza.tv
||g2288.com/afu.php?$popup,third-party,domain=caseyseemavoid.com|atdzfavz.in|xmaza.tv
caseyseemavoid.com##img[src^="https://www.atdzfavz.in/static/image/pn/"]
caseyseemavoid.com##iframe[src^="https://atdzfavz.in/nca/"]
caseyseemavoid.com##a[href^="https://cartographicalrunafoulstreet.com/5/"]
)raws";

template<class Result, class Next>
bool PopupMatch(const Result& first, Next next) {
  if (first.important) return true;
  const auto extra = next(first.matched || first.has_exception, !first.has_exception);
  return extra.important || ((first.matched || extra.matched) &&
                             !first.has_exception && !extra.has_exception);
}
}  // namespace sandium::port1442
#endif
