"""Install the Android ad-tab check in Brave's existing window creation hook."""
import argparse
import hashlib
from pathlib import Path

CLIENT = Path("browser/brave_content_browser_client.cc")
INCLUDE_ANCHOR = '#if BUILDFLAG(IS_ANDROID)\n#include "base/files/memory_mapped_file.h"\n'
V1_INCLUDES = INCLUDE_ANCHOR + '''#include "brave/components/brave_shields/core/browser/brave_shields_utils.h"
#include "net/base/url_util.h"
'''
INCLUDES = V1_INCLUDES
METHOD = 'bool BraveContentBrowserClient::CanCreateWindow(\n'
BEFORE_RETURN = '''  return can_create_window && google_sign_in_permission::CanCreateWindow(
                                  opener, opener_url, target_url);'''
V1_GUARD = '''#if BUILDFLAG(IS_ANDROID)
  if (can_create_window && ShouldBlockSandiumAdTab(
          opener, opener_top_level_frame_url, target_url, disposition)) {
    return false;
  }
#endif
'''
GUARD = V1_GUARD.replace(
    "opener, opener_top_level_frame_url, target_url, disposition",
    "opener, opener_url, opener_top_level_frame_url, target_url, disposition")
V1_HELPERS_SHA256 = "3d9fc572b75ac4a823af5993c21138e59a53d118a27bc5d80fdca2e7e06fbea2"
HELPERS = '''#if BUILDFLAG(IS_ANDROID)
namespace {

// AdGuard Base matches /?scontext_r=*&nrb= across ad hosts. The observed
// tab-up auction also carries nrb=1, nortb_fallback and click metadata.
// https://github.com/uBlockOrigin/uAssets/issues/28058
// Leave the encoded click metadata opaque.
bool IsSandiumAdTabTarget(const GURL& target) {
  if (!target.SchemeIsHTTPOrHTTPS() || !target.path().ends_with("/") ||
      !target.query().starts_with("scontext_r=")) {
    return false;
  }
  net::QueryIterator fields(target);
  if (fields.IsAtEnd() || fields.GetValue().empty()) {
    return false;
  }
  bool has_nrb_flag = false;
  bool has_auction_fallback = false;
  bool has_metadata = false;
  for (fields.Advance(); !fields.IsAtEnd(); fields.Advance()) {
    const auto key = fields.GetKey();
    if (key == "nrb") {
      has_nrb_flag = fields.GetValue() == "1";
    } else if (key == "param_3") {
      has_auction_fallback = fields.GetValue() == "nortb_fallback";
    } else if (key == "md") {
      has_metadata = !fields.GetValue().empty();
    }
  }
  return has_nrb_flag && has_auction_fallback && has_metadata;
}

bool SameSandiumSite(const GURL& a, const GURL& b) {
  return net::registry_controlled_domains::SameDomainOrHost(
      a, b, net::registry_controlled_domains::INCLUDE_PRIVATE_REGISTRIES);
}

// The recorded ad exchange used this route even before video playback began.
// Never classify a popup from the psid query key alone.
bool IsSandiumAdExchangeTarget(const GURL& target) {
  const auto path = target.path();
  if (!path.starts_with("/10/") || path.size() != 4 + 32 ||
      path.substr(4).find_first_not_of("0123456789abcdefABCDEF") != path.npos) {
    return false;
  }
  for (net::QueryIterator fields(target); !fields.IsAtEnd(); fields.Advance()) {
    const auto value = fields.GetValue();
    if (fields.GetKey() == "psid" && !value.empty() &&
        value.find_first_not_of("0123456789") == value.npos) {
      return true;
    }
  }
  return false;
}

// Keep the recognized exchange hop on the early path. The mere presence
// of media is not an ad signal; other scripted windows can consult native
// popup rules during navigation, including list exceptions.
bool IsSandiumEmbeddedAdTab(content::RenderFrameHost* opener,
                            const GURL& opener_url,
                            const GURL& top_url,
                            const GURL& target) {
  if (!opener->GetParent()) {
    return false;
  }
  // An initial about:blank/srcdoc frame can inherit its parent's origin.
  const GURL source = opener_url.SchemeIsHTTPOrHTTPS()
                          ? opener_url
                          : opener->GetLastCommittedOrigin().GetURL();
  if (!source.SchemeIsHTTPOrHTTPS() || SameSandiumSite(source, top_url)) {
    return false;
  }
  return target.SchemeIsHTTPOrHTTPS() && !SameSandiumSite(source, target) &&
         IsSandiumAdExchangeTarget(target);
}

bool ShouldBlockSandiumAdTab(content::RenderFrameHost* opener,
                             const GURL& opener_url,
                             const GURL& top_url,
                             const GURL& target,
                             WindowOpenDisposition disposition) {
  switch (disposition) {
    case WindowOpenDisposition::NEW_FOREGROUND_TAB:
    case WindowOpenDisposition::NEW_BACKGROUND_TAB:
    case WindowOpenDisposition::NEW_WINDOW:
    case WindowOpenDisposition::NEW_POPUP:
      break;
    default:
      return false;
  }
  if (!top_url.SchemeIsHTTPOrHTTPS() || SameSandiumSite(top_url, target) ||
      (!IsSandiumAdTabTarget(target) &&
       !IsSandiumEmbeddedAdTab(opener, opener_url, top_url, target))) {
    return false;
  }
  auto* profile = Profile::FromBrowserContext(opener->GetBrowserContext());
  auto* map = HostContentSettingsMapFactory::GetForProfile(profile);
  return map && brave_shields::IsBraveShieldsEnabled(map, top_url) &&
         map->GetContentSetting(top_url, top_url, ContentSettingsType::POPUPS) !=
             CONTENT_SETTING_ALLOW &&
         brave_shields::ShouldBlockAdRedirect(*profile->GetPrefs(), top_url);
}

}  // namespace
#endif  // BUILDFLAG(IS_ANDROID)

'''


def transform(source):
    # Checkpoints can contain the previously installed Android hook. Accept its
    # exact generated helper and guard, then use the same clean install path.
    if V1_GUARD in source:
        start = source.find("#if BUILDFLAG(IS_ANDROID)\nnamespace {\n\n// AdGuard Base")
        end = source.find(METHOD, start)
        previous = source[start:end]
        if (start < 0 or end < 0 or source.count(V1_GUARD) != 1
                or hashlib.sha256(previous.encode()).hexdigest() != V1_HELPERS_SHA256
                or source.count(V1_INCLUDES) != 1):
            raise ValueError("Unexpected previous Sandium ad-tab check")
        source = (source[:start] + source[end:]).replace(V1_GUARD, "", 1)
        source = source.replace(V1_INCLUDES, INCLUDE_ANCHOR, 1)
    edits = ((INCLUDE_ANCHOR, INCLUDES), (METHOD, HELPERS + METHOD),
             (BEFORE_RETURN, GUARD + BEFORE_RETURN))
    if any(new in source for _, new in edits):
        if all(source.count(new) == 1 and source.count(old) == 1 for old, new in edits):
            return source
        raise ValueError("Incomplete Sandium ad-tab check")
    if ("ShouldBlockSandiumAdTab" in source or "IsSandiumAdTabTarget" in source
            or any(source.count(old) != 1 for old, _ in edits)):
        raise ValueError("Unexpected Brave window creation source")
    for old, new in edits:
        source = source.replace(old, new, 1)
    return source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("core", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    path = args.core / CLIENT
    before = path.read_text()
    after = transform(before)
    if before != after:
        if args.verify_only:
            parser.exit(1, "Sandium ad-tab check missing\n")
        path.write_text(after)


if __name__ == "__main__":
    main()
