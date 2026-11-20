// SPDX-License-Identifier: MPL-2.0
// Adapted from Brave's ad_block_engine_wrapper.cc. Copyright The Brave Authors.
#ifndef COMPONENTS_SANDIUM_ADBLOCK_STANDARD_MERGE_H_
#define COMPONENTS_SANDIUM_ADBLOCK_STANDARD_MERGE_H_
#include <utility>
namespace sandium::adblock_native::internal {
// Compile-time seam for tests. Both rule collections belong to one blocking
// service. Standard here means the pinned Android default (no aggressive or
// field-trial 1p override). Page-level overrides are deliberately not a parameter.
template <class Result, class Additional>
Result MergeStandard(Result first, bool keep_default_match, bool previous_match,
                     bool previous_exception, Additional&& additional) {
  // Brave intentionally ignores removeparam from the default ruleset.
  first.rewritten_url.has_value = false;
  if (keep_default_match) {
    if (first.important) return first;
  } else {
    Result keep{};
    keep.has_exception = first.has_exception;
    keep.exception = std::move(first.exception);
    first = std::move(keep);
  }
  auto out = additional(previous_match || first.matched,
                        previous_exception || first.has_exception);
  out.matched |= first.matched;
  out.has_exception |= first.has_exception;
  out.important |= first.important;
  if (!out.filter) out.filter = std::move(first.filter);
  if (!out.exception) out.exception = std::move(first.exception);
  if (!out.redirect.has_value && first.redirect.has_value)
    out.redirect = std::move(first.redirect);
  return out;  // A rewrite from the additional engine is retained.
}
}  // namespace sandium::adblock_native::internal
#endif
