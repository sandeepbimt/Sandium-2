"""#1426: match native-blur fallback to an explicitly managed destination.

This runs *after* the pinned Chromium blur, optional darken, and blur-level
transforms. It changes only the color of the existing solid fallback layer;
Chromium retains complete ownership of navigation, presentation, and timeout.
Unknown/native/error/opaque destinations retain the upstream theme fallback.
"""
from pathlib import Path

PATH = 'content/browser/navigation_transitions/blur_transition_animation_manager.cc'
MARKER = 'SANDIUM_1426_DESTINATION_FALLBACK'
INCLUDE_ANCHOR = '#include "content/public/common/content_features.h"\n'
INCLUDE_BLOCK = (INCLUDE_ANCHOR
    + '#include "content/browser/renderer_host/navigation_request.h"\n'
    + '#include "content/public/browser/content_browser_client.h"\n'
    + '#include "content/public/common/content_client.h"\n'
    + '#include "third_party/blink/public/mojom/navigation/navigation_params.mojom.h"\n')
# Exact include block owned by native-navigation/diagnostics.py.
DIAGNOSTIC_INCLUDES = ('#include "base/metrics/histogram_functions.h"\n'
    '#include <vector>\n#include "base/time/time.h"\n'
    '#include "content/public/browser/content_browser_client.h"\n'
    '#include "content/public/common/content_client.h"\n')
DIAGNOSTIC_ADDITIONS = (INCLUDE_ANCHOR
    + '#include "content/browser/renderer_host/navigation_request.h"\n'
    + '#include "third_party/blink/public/mojom/navigation/navigation_params.mojom.h"\n')

OLD = '''  SkColor4f background_color = SkColors::kWhite;
  if (auto theme_color = delegate->GetThemeColor()) {
    background_color = SkColor4f::FromColor(*theme_color);
  }
'''
NEW = '''  // SANDIUM_1426_DESTINATION_FALLBACK: only change the existing backing color.
  // ReadyToCommit observes the final URL after redirects, not the outgoing NTP.
  const auto origin_to_commit = navigation_handle->GetOriginToCommit();
  const auto* sandium_request = NavigationRequest::From(navigation_handle);
  const bool managed_destination =
      sandium_request && navigation_handle->GetURL().SchemeIsHTTPOrHTTPS() &&
      !navigation_handle->IsErrorPage() && !navigation_handle->IsPdf() &&
      !sandium_request->commit_params().is_view_source &&
      origin_to_commit.has_value() && !origin_to_commit->opaque();
  // The Sandium commit params are populated later in CommitNavigation;
  // they are not authoritative at this ReadyToCommit callback. Reuse the
  // existing browser policy endpoint. This changes no navigation timing gate.
  const int sandium_dark_policy = managed_destination
      ? GetContentClient()->browser()->GetSandiumDarkPageFlagsForNavigation(
            web_contents(), navigation_handle->GetURL())
      : -1;
  SkColor4f background_color = SkColors::kWhite;
  if (sandium_dark_policy == 1) {
    background_color = SkColors::kBlack;
  } else if (sandium_dark_policy < 0) {
    // Unmanaged, native, PDF and error documents retain upstream behavior.
    if (auto theme_color = delegate->GetThemeColor()) {
      background_color = SkColor4f::FromColor(*theme_color);
    }
  }
'''


def transform(source):
    """Accept only raw pinned includes or the exact owned diagnostic block."""
    diagnostic = source.count(DIAGNOSTIC_INCLUDES) == 1
    required = (
        'content/browser/renderer_host/navigation_request.h',
        'content/public/browser/content_browser_client.h',
        'content/public/common/content_client.h',
        'third_party/blink/public/mojom/navigation/navigation_params.mojom.h')
    counts = [source.count('#include "' + header + '"') for header in required]
    include_block = DIAGNOSTIC_ADDITIONS if diagnostic else INCLUDE_BLOCK
    if MARKER in source:
        if (source.count(MARKER) != 1 or source.count(NEW) != 1
                or source.count(include_block) != 1 or OLD in source
                or counts != [1, 1, 1, 1]):
            raise ValueError('Partial or duplicate #1426 destination fallback')
        return source
    expected = [0, 1, 1, 0] if diagnostic else [0, 0, 0, 0]
    if (source.count(OLD) != 1 or source.count(INCLUDE_ANCHOR) != 1
            or 'SANDIUM_DESTINATION_FALLBACK_V1' in source
            or counts != expected):
        raise ValueError('Unexpected native blur fallback source; no #1426 write')
    return source.replace(INCLUDE_ANCHOR, include_block, 1).replace(OLD, NEW, 1)


def plan(root):
    path = Path(root) / PATH
    return {path: transform(path.read_text())}
