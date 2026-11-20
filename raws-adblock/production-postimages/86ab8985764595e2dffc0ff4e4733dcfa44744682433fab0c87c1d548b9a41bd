// SPDX-License-Identifier: MPL-2.0
// Adapted from Sandium #1442 ad-redirects/popup.py and filter-compat/popup_matcher.py.
#ifndef COMPONENTS_SANDIUM_ADBLOCK_PORT1442_POLICY_H_
#define COMPONENTS_SANDIUM_ADBLOCK_PORT1442_POLICY_H_
#include <string_view>
namespace sandium::port1442 {
template<class Result, class Next>
bool PopupMatch(const Result& first, Next next) {
  if (first.important) return true;
  const auto extra = next(first.matched || first.has_exception, !first.has_exception);
  return extra.important || ((first.matched || extra.matched) &&
                             !first.has_exception && !extra.has_exception);
}
}  // namespace sandium::port1442
#endif
