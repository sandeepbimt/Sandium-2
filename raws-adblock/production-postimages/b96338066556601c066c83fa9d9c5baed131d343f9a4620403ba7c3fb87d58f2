// SPDX-License-Identifier: MPL-2.0
#ifndef COMPONENTS_SANDIUM_ADBLOCK_1442_STYLE_H_
#define COMPONENTS_SANDIUM_ADBLOCK_1442_STYLE_H_
#include <array>
#include <set>
#include <string>
#include <string_view>
#include <vector>
namespace sandium::port1442 {
// Narrow static subset of the pinned, bundled EasyList's generic rules. Keep
// these exact simple ad-slot selectors; a returned compound selector matched
// through one of the same class/ID keys is deliberately not accepted.
inline constexpr std::array<std::string_view, 10> kPackagedGenericAdSlots = {
    ".Ad728x90", ".Advert300x250", ".ad-160x600", ".ad-300x250",
    ".ad-728x90", ".ad-970x250", "#Adsense300x250", "#ad-160x600",
    "#ad-300x250", "#ad-728x90",
};

template <typename QueryPackagedEngine>
void AppendPackagedGenericHide(
    bool suppress_generic,
    const std::set<std::string>& exceptions,
    std::set<std::string>& hide,
    QueryPackagedEngine query) {
  if (suppress_generic) {
    return;
  }
  std::vector<std::string> classes, ids;
  for (auto selector : kPackagedGenericAdSlots) {
    (selector.front() == '.' ? classes : ids).emplace_back(selector.substr(1));
  }
  std::vector<std::string> exception_list(exceptions.begin(), exceptions.end());
  for (const auto& match : query(classes, ids, exception_list)) {
    for (auto selector : kPackagedGenericAdSlots) {
      if (match == selector && !exceptions.contains(match)) {
        hide.insert(match);
        break;
      }
    }
  }
}

// Only immutable declarations; do not embed styles, scripts, at-rules or network
// loads supplied by a list. Invalid selectors are isolated in individual rules.
inline std::string HideStyles(const std::set<std::string>& hide,const std::set<std::string>& exceptions) {
  std::string css;
  for (const auto& s : hide) {
    if (s.empty() || s.size()>2048 || s.find_first_of("{};@\\\r\n")!=s.npos ||
        s.find('\0')!=s.npos || s.find("/*")!=s.npos || exceptions.contains(s)) continue;
    if (css.size()+s.size()+32 > 256*1024) break;
    css+=s;css+=" { display:none !important; }\n";
  }
  return css;
}
}
#endif
