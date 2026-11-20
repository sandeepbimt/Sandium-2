"""Select the Android Chromium branches of external uBO-format filter lists."""
import argparse
from pathlib import Path


PROVIDER = Path("components/brave_shields/content/browser/ad_block_subscription_filters_provider.cc")
INCLUDE = "#include <string>\n"
INCLUDES = "#include <cstring>\n#include <optional>\n" + INCLUDE + "#include <string_view>\n#include <vector>\n"
FUNCTION = "// static\nvoid AddDATBufferToFilterSet("
PARSE = "  auto result = (*filter_set)->add_filter_list(buffer);"
CALL = "  PruneSandiumSubscription(buffer);\n" + PARSE

HELPERS = r'''// uBO list dialect on Chromium Android. Extension identity here selects list
// syntax; the native engine remains authoritative for individual rules and
// scriptlet permissions. See uBlock's static-filtering-parser.js preparser.
std::string_view TrimSubscriptionSpace(std::string_view text) {
  constexpr std::string_view spaces = " \t\v\f\r";
  const auto start = text.find_first_not_of(spaces);
  if (start == text.npos) {
    return {};
  }
  return text.substr(start, text.find_last_not_of(spaces) - start + 1);
}

std::optional<bool> SubscriptionConditionToken(std::string_view token) {
  const bool invert = token.starts_with('!');
  if (invert) {
    token.remove_prefix(1);
  }
  if (token == "ext_ublock" || token == "env_chromium" ||
      token == "env_brave" || token == "env_mobile" ||
      token == "adguard_ext_chromium" || token == "adguard_ext_opera") {
    return !invert;
  }
  // Like uBO, unknown cap_* values are false. Unknown ordinary names are
  // indeterminate, so unfamiliar directives do not silently drop both arms.
  constexpr std::string_view absent[] = {
      "ext_ubol", "ext_devbuild", "env_edge", "env_firefox", "env_legacy",
      "env_mv3", "env_safari", "false", "ext_abp", "adguard",
      "adguard_app_android", "adguard_app_cli", "adguard_app_ios",
      "adguard_app_mac", "adguard_app_windows", "adguard_ext_android_cb",
      "adguard_ext_chromium_mv3", "adguard_ext_edge", "adguard_ext_firefox",
      "adguard_ext_safari"};
  if (token.starts_with("cap_")) {
    return invert;
  }
  for (const auto name : absent) {
    if (token == name) {
      return invert;
    }
  }
  return std::nullopt;
}

std::optional<bool> EvaluateSubscriptionCondition(std::string_view expression) {
  expression = TrimSubscriptionSpace(expression);
  if (expression.starts_with('(') && expression.ends_with(')')) {
    expression = TrimSubscriptionSpace(expression.substr(1, expression.size() - 2));
  }
  constexpr std::string_view spaces = " \t\v\f\r";
  const auto next_word = [&expression, spaces]() {
    const auto end = expression.find_first_of(spaces);
    auto word = expression.substr(0, end);
    expression.remove_prefix(word.size());
    return word;
  };
  const auto first = next_word();
  if (first.empty() || first.starts_with('|') || first.starts_with('&')) {
    return std::nullopt;
  }
  auto result = SubscriptionConditionToken(first);
  while (!(expression = TrimSubscriptionSpace(expression)).empty()) {
    const auto op = next_word();
    if ((op != "&&" && op != "||") || !expression.starts_with(' ')) {
      return std::nullopt;
    }
    const auto start = expression.find_first_not_of(' ');
    if (start == expression.npos) {
      return std::nullopt;
    }
    expression.remove_prefix(start);
    const auto value = SubscriptionConditionToken(next_word());
    if (!value) {
      return std::nullopt;
    }
    // The maintainer's grammar evaluates operators left to right.
    if (op == "||") {
      result = result.value_or(false) || *value;
    } else if (result.has_value()) {
      result = *result && *value;
    }
  }
  return result;
}

void PruneSandiumSubscription(DATFileDataBuffer& buffer) {
  if (buffer.empty()) {
    return;
  }
  const std::string_view text(reinterpret_cast<const char*>(buffer.data()),
                              buffer.size());
  const auto first = text.find("!#if");
  if (first == text.npos) {
    return;
  }
  const auto preceding_lf = text.rfind('\n', first);
  size_t read = preceding_lf == text.npos ? 0 : preceding_lf + 1;
  size_t written = read;
  std::vector<std::optional<bool>> branches;
  size_t disabled = 0;

  while (read < text.size()) {
    const auto lf = text.find('\n', read);
    const size_t end = lf == text.npos ? text.size() : lf + 1;
    auto line = text.substr(read, (lf == text.npos ? end : lf) - read);
    if (line.starts_with("!#")) {
      line.remove_prefix(2);
      const auto word_end = line.find_first_not_of(
          "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_");
      const auto directive = line.substr(0, word_end);
      if (directive == "if") {
        const auto state = EvaluateSubscriptionCondition(line.substr(2));
        branches.push_back(state);
        if (state == false) {
          ++disabled;
        }
      } else if (!branches.empty() && directive == "else") {
        auto& state = branches.back();
        if (state.has_value()) {
          if (*state) {
            ++disabled;
          } else {
            --disabled;
          }
          state = !*state;
        }
      } else if (!branches.empty() && directive == "endif") {
        if (branches.back() == false) {
          --disabled;
        }
        branches.pop_back();
      }
    }

    // Rewrite in place, retaining LF/CRLF and original line numbers for
    // metadata and rule diagnostics. Reuse the original bytes on enabled spans.
    size_t from = read;
    if (disabled) {
      from = lf == text.npos ? end : lf;
      if (from > read && text[from - 1] == '\r') {
        --from;
      }
    }
    const size_t count = end - from;
    if (count && written != from) {
      std::memmove(buffer.data() + written, buffer.data() + from, count);
    }
    written += count;
    read = end;
  }
  buffer.resize(written);
}

'''


def transform(source):
    edits = ((INCLUDE, INCLUDES), (FUNCTION, HELPERS + FUNCTION), (PARSE, CALL))
    for old, new in edits:
        if source.count(old) != 1 or source.count(new) > 1:
            raise ValueError("Unexpected Brave subscription source")
    if any(new in source for _, new in edits):
        if all(new in source for _, new in edits):
            return source
        raise ValueError("Partial subscription condition integration")
    if "PruneSandiumSubscription" in source:
        raise ValueError("Conflicting subscription condition integration")
    for old, new in edits:
        source = source.replace(old, new, 1)
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("core", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    path = args.core / PROVIDER
    original = path.read_text()
    updated = transform(original)
    if updated != original:
        if args.verify_only:
            parser.error("Sandium subscription condition handling is missing")
        path.write_text(updated)


if __name__ == "__main__":
    main()
