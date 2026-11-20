// SPDX-License-Identifier: MPL-2.0
#ifndef COMPONENTS_SANDIUM_ADBLOCK_1442_GENERIC_STYLE_H_
#define COMPONENTS_SANDIUM_ADBLOCK_1442_GENERIC_STYLE_H_

#include <algorithm>
#include <cstddef>
#include <functional>
#include <utility>
#include <set>
#include <string>
#include <string_view>
#include <vector>

namespace sandium::port1442 {

// Match only an exact ASCII simple class/ID. This syntax cannot introduce a
// declaration, pseudo-selector, combinator, attribute, or selector group.
inline bool IsSimpleGenericSelector(std::string_view selector) {
  constexpr auto letter = [](char c) {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_';
  };
  return selector.size() >= 2 && selector.size() <= 65 &&
         (selector[0] == '.' || selector[0] == '#') && letter(selector[1]) &&
         std::all_of(selector.begin() + 2, selector.end(), [letter](char c) {
           return letter(c) || (c >= '0' && c <= '9') || c == '-';
         });
}

inline constexpr size_t kPackagedGenericCandidateLimit = 1536;
inline constexpr size_t kSubscriptionGenericCandidateLimit = 2048;
inline constexpr size_t kSubscriptionGenericPerList = 96;
inline constexpr size_t kGenericStylesByteLimit = 64 * 1024;
inline constexpr size_t kGenericGroupSize = 64;

// Collect index keys when constructing the rule snapshot, not on document
// commit. Preserve input order and cap each download separately so a large
// first list cannot consume the whole subscription budget.
class SimpleGenericCensus {
 public:
  explicit SimpleGenericCensus(size_t max_count);
  SimpleGenericCensus(size_t max_count, size_t max_per_kind);
  ~SimpleGenericCensus();

  bool Add(std::string_view selector) {
    if (!IsSimpleGenericSelector(selector) || ordered_.size() >= max_count_) {
      return false;
    }
    size_t& count = selector.front() == '.' ? class_count_ : id_count_;
    if (count >= max_per_kind_ || !exact_.emplace(selector).second) {
      return false;
    }
    ++count;
    ordered_.emplace_back(selector);
    return true;
  }

  size_t AddList(std::string_view text, size_t list_limit) {
    size_t accepted = 0;
    while (!text.empty() && accepted < list_limit &&
           ordered_.size() < max_count_) {
      const size_t n = text.find('\n');
      auto line = text.substr(0, n);
      if (n == text.npos) {
        text = {};
      } else {
        text.remove_prefix(n + 1);
      }
      if (!line.empty() && line.back() == '\r') {
        line.remove_suffix(1);
      }
      if (line.starts_with("##") && Add(line.substr(2))) {
        ++accepted;
      }
    }
    return accepted;
  }

  // The exact adblock-rust engine remains authoritative: a line that its parser
  // ignored cannot introduce a selector. Complex matches returned for a key
  // are rejected. Resolve once and preserve deterministic source order.
  template <typename QueryEngine>
  std::vector<std::string> Resolve(QueryEngine query) const {
    if (ordered_.empty()) {
      return {};
    }
    std::vector<std::string> classes;
    std::vector<std::string> ids;
    classes.reserve(ordered_.size());
    ids.reserve(ordered_.size());
    for (const auto& selector : ordered_) {
      (selector.front() == '.' ? classes : ids).push_back(selector.substr(1));
    }
    std::set<std::string, std::less<>> matched;
    for (const auto& result : query(classes, ids)) {
      const std::string_view selector(result.data(), result.size());
      if (IsSimpleGenericSelector(selector) && exact_.contains(selector)) {
        matched.emplace(selector);
      }
    }
    std::vector<std::string> ordered_matches;
    ordered_matches.reserve(matched.size());
    for (const auto& selector : ordered_) {
      if (matched.contains(selector)) {
        ordered_matches.push_back(selector);
      }
    }
    return ordered_matches;
  }

 private:
  size_t max_count_;
  size_t max_per_kind_;
  size_t class_count_ = 0;
  size_t id_count_ = 0;
  std::vector<std::string> ordered_;
  std::set<std::string, std::less<>> exact_;
};

// Deduplicate once at snapshot construction, preserving packaged precedence.
inline std::vector<std::string> MergeSimpleGeneric(
    std::vector<std::string> packaged,
    std::vector<std::string> subscriptions) {
  const std::set<std::string, std::less<>> known(packaged.begin(), packaged.end());
  packaged.reserve(packaged.size() + subscriptions.size());
  for (auto& selector : subscriptions) {
    if (!known.contains(selector)) {
      packaged.push_back(std::move(selector));
    }
  }
  return packaged;
}

// One document stylesheet handles both initial and later DOM nodes. Honor
// the union of both engines' URL-specific exceptions and $generichide. Keep
// existing scoped rules first and preserve their independent budget.
inline void AppendSimpleGenericStyles(
    std::string& css,
    bool suppress_generic,
    const std::vector<std::string>& selectors,
    const std::set<std::string>& scoped,
    const std::set<std::string>& exceptions) {
  if (suppress_generic) {
    return;
  }
  constexpr std::string_view declaration = " { display:none !important; }\n";
  constexpr size_t kExistingTotalByteLimit = 256 * 1024;
  constexpr size_t kGenericByteLimit = kGenericStylesByteLimit;
  if (css.size() >= kExistingTotalByteLimit) {
    return;
  }
  const size_t end = css.size() +
      std::min(kGenericByteLimit, kExistingTotalByteLimit - css.size());
  size_t group = 0;
  for (const auto& selector : selectors) {
    if (!IsSimpleGenericSelector(selector) || exceptions.contains(selector) ||
        scoped.contains(selector)) {
      continue;
    }
    if (css.size() + selector.size() + (group != 0) + declaration.size() >
        end) {
      continue;
    }
    if (group != 0) {
      css += ',';
    }
    css += selector;
    if (++group == kGenericGroupSize) {
      css += declaration;
      group = 0;
    }
  }
  if (group != 0) {
    css += declaration;
  }
}

}  // namespace sandium::port1442
#endif
