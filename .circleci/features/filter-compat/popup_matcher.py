"""Handle popup requests and document exclusions in the pinned native engines."""

import argparse
from pathlib import Path

VENDOR = "third_party/rust/chromium_crates_io/vendor/adblock-v0_13/src/"
BROWSER = "components/brave_shields/content/browser/"


def edits():
    result = {}

    def replace(path, before, after):
        result.setdefault(path, []).append((before, after))

    def after(path, anchor, addition):
        replace(path, anchor, anchor + addition)

    def before(path, anchor, addition):
        replace(path, anchor, addition + anchor)

    path = VENDOR + "request.rs"
    # Tokenize the normalized URL before moving it into the request. The
    # pinned implementation allocated a second copy for every nonempty URL.
    replace(
        path,
        """            url_lower_cased: url_lower_cased.to_owned(),
            hostname: hostname.to_owned(),
            request_tokens: calculate_tokens(&url_lower_cased),""",
        """            request_tokens: calculate_tokens(&url_lower_cased),
            url_lower_cased,
            hostname: hostname.to_owned(),""",
    )
    after(path, "    Ping,\n", "    Popup,\n")
    after(
        path,
        '        "ping" => RequestType::Ping,\n',
        '        "popup" => RequestType::Popup,\n',
    )
    path = VENDOR + "filters/abstract_network.rs"
    after(path, "    Document,\n", "    ExcludeDocument,\n")
    after(
        path,
        "            Self::Document\n",
        "                | Self::ExcludeDocument\n",
    )
    replace(
        path,
        '("document", true) | ("doc", true) => return Err(NetworkFilterError::NegatedDocument),',
        '("document", true) | ("doc", true) => NetworkFilterOption::ExcludeDocument,',
    )
    after(path, "    Ping(bool),\n", "    Popup(bool),\n")
    after(
        path,
        "                | Self::Ping(..)\n",
        "                | Self::Popup(..)\n",
    )
    after(
        path,
        '            ("ping", negated) | ("beacon", negated) => NetworkFilterOption::Ping(!negated),\n',
        '            ("popup", negated) => NetworkFilterOption::Popup(!negated),\n',
    )
    path = VENDOR + "filters/network.rs"
    after(
        path,
        "        const FROM_DOCUMENT = 1 << 29;\n",
        "        // Explicit ~document also disables the implicit document exception.\n"
        "        const EXCLUDES_DOCUMENT = 1 << 31;\n",
    )
    after(
        path,
        """                    NetworkFilterOption::Document => {
                        cpt_mask_positive.set(NetworkFilterMask::FROM_DOCUMENT, true)
                    }
""",
        """                    NetworkFilterOption::ExcludeDocument => {
                        cpt_mask_negative.set(NetworkFilterMask::FROM_DOCUMENT, true);
                        mask.set(NetworkFilterMask::EXCLUDES_DOCUMENT, true);
                    }
""",
    )
    after(
        path,
        "        const MATCH_CASE = 1 << 14;\n",
        "        const FROM_POPUP = 1 << 15;\n",
    )
    replace(
        path,
        "        // TODO Could also include popup, inline-font, inline-script\n",
        "        // Popup is matched explicitly. Generic network and hostname rules exclude it.\n",
    )
    replace(
        path,
        "            Self::FROM_DOCUMENT.bits();",
        "            Self::FROM_DOCUMENT.bits() | Self::FROM_POPUP.bits();",
    )
    replace(
        path,
        "                self.has_flag(NetworkFilterMask::FROM_DOCUMENT) || self.is_exception()",
        """                self.has_flag(NetworkFilterMask::FROM_DOCUMENT)
                    || (self.is_exception()
                        && !self.has_flag(NetworkFilterMask::FROM_POPUP)
                        && !self.has_flag(NetworkFilterMask::EXCLUDES_DOCUMENT))""",
    )
    after(
        path,
        "            request::RequestType::Ping => NetworkFilterMask::FROM_PING,\n",
        "            request::RequestType::Popup => NetworkFilterMask::FROM_POPUP,\n",
    )
    after(
        path,
        "                    NetworkFilterOption::Ping(enabled) => apply_content_type!(FROM_PING, enabled),\n",
        "                    NetworkFilterOption::Popup(enabled) => apply_content_type!(FROM_POPUP, enabled),\n",
    )
    replace(
        path,
        "            mask |= NetworkFilterMask::FROM_ALL_TYPES;",
        "            mask |= NetworkFilterMask::FROM_NETWORK_TYPES | NetworkFilterMask::FROM_DOCUMENT;",
    )
    replace(
        path,
        "            | NetworkFilterMask::FROM_ALL_TYPES\n",
        "            | NetworkFilterMask::FROM_DOCUMENT\n",
    )
    path = BROWSER + "ad_block_engine.h"
    before(
        path,
        "  std::optional<std::string> GetCspDirectives(",
        """  adblock::BlockerResult MatchSandiumPopup(const GURL& target,
                                          const GURL& source,
                                          bool already_matched,
                                          bool check_exceptions);
""",
    )
    path = BROWSER + "ad_block_engine.cc"
    before(
        path,
        "std::optional<std::string> AdBlockEngine::GetCspDirectives(",
        """adblock::BlockerResult AdBlockEngine::MatchSandiumPopup(const GURL& target,
                                                       const GURL& source,
                                                       bool already_matched,
                                                       bool check_exceptions) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  return ad_block_client_->matches(
      target.spec(), std::string(target.host()), std::string(source.host()),
      "popup", !SameDomainOrHost(target, source, INCLUDE_PRIVATE_REGISTRIES),
      "GET", already_matched, check_exceptions);
}

""",
    )
    path = BROWSER + "ad_block_engine_wrapper.h"
    before(
        path,
        "  adblock::BlockerResult ShouldStartRequest(",
        "  bool ShouldBlockSandiumPopup(const GURL& target, const GURL& source);\n\n",
    )
    path = BROWSER + "ad_block_engine_wrapper.cc"
    before(
        path,
        "adblock::BlockerResult AdBlockEngineWrapper::ShouldStartRequest(",
        """// Popup is an exact request type. Keep list, exception and important-rule
// precedence on the existing ad-block sequence without inspecting other loads.
bool AdBlockEngineWrapper::ShouldBlockSandiumPopup(const GURL& target,
                                                  const GURL& source) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  const auto base_result =
      default_engine_->MatchSandiumPopup(target, source, false, true);
  if (base_result.important) {
    return true;
  }
  const auto extra_result = additional_filters_engine_->MatchSandiumPopup(
      target, source, base_result.matched || base_result.has_exception,
      !base_result.has_exception);
  return extra_result.important ||
         ((base_result.matched || extra_result.matched) &&
          !base_result.has_exception && !extra_result.has_exception);
}

""",
    )

    return result


def plan(core):
    changes = {}
    for name, replacements in edits().items():
        path = core / name
        original = path.read_text()
        installed = []
        for before, after in replacements:
            if original.count(after) == 1 and before not in original.replace(
                after, "", 1
            ):
                installed.append(True)
            elif after not in original and original.count(before) == 1:
                installed.append(False)
            else:
                raise ValueError(f"Unexpected native popup matcher source in {name}")
        if all(installed):
            continue
        if any(installed):
            raise ValueError(f"Incomplete native popup matcher source in {name}")
        updated = original
        for before, after in replacements:
            updated = updated.replace(before, after, 1)
        changes[path] = updated
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("core", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    changes = plan(args.core)
    if changes and args.verify_only:
        parser.error("native popup matcher is missing")
    for path, text in changes.items():
        path.write_text(text)


if __name__ == "__main__":
    main()
