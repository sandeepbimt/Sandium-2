#!/usr/bin/env python3
"""Pinned, fail-closed destination-aware back preview and trace diagnostics.

Does not change BFCache, screenshot eligibility, insets or animation timing.
"""
from pathlib import Path
import subprocess
import sys

CHROMIUM_SHA = "d331de35ca8ab1358c7a17e4bd41627d55eaef51"
BRAVE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
CHANGES = [
    (
        'content/browser/navigation_transitions/back_forward_transition_animator.cc',
        '  CHECK(new_render_widget_host_);\n  CHECK_NE(primary_main_frame_navigation_entry_item_sequence_number_',
        '''  CHECK(new_render_widget_host_);
  const auto& sandium_metadata = new_render_widget_host_->render_frame_metadata_provider()
                                     ->LastRenderFrameMetadata();
  TRACE_EVENT("navigation", "SandiumBackActivatedGeometry",
              "viewport_width", sandium_metadata.viewport_size_in_pixels.width(),
              "viewport_height", sandium_metadata.viewport_size_in_pixels.height(),
              "scale", sandium_metadata.page_scale_factor,
              "destination_matches", sandium_metadata.primary_main_frame_item_sequence_number ==
                  primary_main_frame_navigation_entry_item_sequence_number_);
  TRACE_EVENT("navigation", "SandiumBackActivatedControls",
              "top_height", sandium_metadata.browser_controls_metadata.top_controls_height,
              "top_ratio", sandium_metadata.browser_controls_metadata.top_controls_shown_ratio,
              "top_min_offset", sandium_metadata.browser_controls_metadata.top_controls_min_height_offset);
  if (sandium_metadata.root_scroll_offset) {
    TRACE_EVENT("navigation", "SandiumBackActivatedScroll",
                "x", sandium_metadata.root_scroll_offset->x(),
                "y", sandium_metadata.root_scroll_offset->y());
  }
  CHECK_NE(primary_main_frame_navigation_entry_item_sequence_number_'''
    ),
    (
        'content/browser/renderer_host/navigation_transitions/navigation_transition_utils.cc',
        '#include "content/browser/renderer_host/navigation_request.h"',
        '#include "content/browser/renderer_host/navigation_request.h"\n#include "content/browser/renderer_host/page_impl.h"'
    ),
    (
        'content/browser/renderer_host/navigation_transitions/navigation_transition_data.h',
'''  const SkBitmap& favicon() const { return favicon_; }''',
'''  // Sandium: session-only opaque rendered page background, not theme-color.
  std::optional<SkColor> sandium_page_background() const {
    return sandium_page_background_;
  }
  void set_sandium_page_background(std::optional<SkColor> color) {
    sandium_page_background_ = color && SkColorGetA(*color) == 255
                                   ? color : std::nullopt;
  }
  std::optional<bool> sandium_page_is_dark() const {
    return sandium_page_is_dark_;
  }
  void set_sandium_page_is_dark(std::optional<bool> is_dark) {
    sandium_page_is_dark_ = is_dark;
  }

  const SkBitmap& favicon() const { return favicon_; }'''
    ),
    (
        'content/browser/renderer_host/navigation_transitions/navigation_transition_data.h',
'''  // The favicon used to compose the fallback UX.''',
'''  std::optional<SkColor> sandium_page_background_;
  std::optional<bool> sandium_page_is_dark_;

  // The favicon used to compose the fallback UX.'''
    ),
    (
        'content/browser/renderer_host/navigation_transitions/navigation_transition_utils.cc',
'''bool ShouldSkipScreenshotWithMissReason(''',
'''// Sandium: sample only the outgoing primary document while its entry and RFH
// still agree. Never use the currently displayed outgoing site's color when
// constructing a destination fallback. No pixels, URL or history are persisted.
void SandiumCapturePageBackground(NavigationRequest& request,
                                 NavigationEntryImpl* entry) {
  if (!entry || !request.IsInPrimaryMainFrame() ||
      request.frame_tree_node()->GetParentOrOuterDocumentOrEmbedder()) {
    return;
  }
  entry->navigation_transition_data().set_sandium_page_background(std::nullopt);
  entry->navigation_transition_data().set_sandium_page_is_dark(std::nullopt);
  auto* frame = request.frame_tree_node()->current_frame_host();
  if (entry->GetPageType() != PAGE_TYPE_NORMAL ||
      !entry->GetURL().SchemeIsHTTPOrHTTPS() || !frame->IsRenderFrameLive() ||
      frame->GetLastCommittedURL() != entry->GetURL()) {
    return;
  }
  entry->navigation_transition_data().set_sandium_page_background(
      frame->GetPage().background_color());
  if (const auto scheme = frame->GetPage().inferred_color_scheme()) {
    entry->navigation_transition_data().set_sandium_page_is_dark(
        *scheme == blink::mojom::PreferredColorScheme::kDark);
  }
}

bool ShouldSkipScreenshotWithMissReason('''
    ),
    (
        'content/browser/renderer_host/navigation_transitions/navigation_transition_utils.cc',
'''  auto* last_committed_entry = navigation_controller.GetLastCommittedEntry();''',
'''  auto* last_committed_entry = navigation_controller.GetLastCommittedEntry();
  SandiumCapturePageBackground(navigation_request, last_committed_entry);'''
    ),
    (
        'content/browser/renderer_host/navigation_transitions/navigation_transition_utils.cc',
'''  auto* last_committed_entry = nav_controller.GetLastCommittedEntry();''',
'''  auto* last_committed_entry = nav_controller.GetLastCommittedEntry();
  SandiumCapturePageBackground(navigation_request, last_committed_entry);'''
    ),
    (
        'content/browser/navigation_transitions/back_forward_transition_animator.cc',
'''  return use_fallback_screenshot;''',
'''  TRACE_EVENT("navigation", "SandiumBackPreviewSelection",
              "fallback", use_fallback_screenshot,
              "cache_reason", static_cast<int>(cache_hit_or_miss_reason.value_or(
                                  CacheHitOrMissReason::kCacheMissColdStart)));
  return use_fallback_screenshot;'''
    ),
    (
        'content/browser/navigation_transitions/back_forward_transition_animator.cc',
'''        .end_px = CalculateRRectEndPx(),
    };
  }
  state_ = State::kStarted;''',
'''        .end_px = CalculateRRectEndPx(),
    };
    const auto page_color = destination_entry->navigation_transition_data()
                                .sandium_page_background();
    const auto page_is_dark = destination_entry->navigation_transition_data()
                                  .sandium_page_is_dark();
    int color_source = 0;  // Neutral browser context when destination is unknown.
    if (destination_entry->GetPageType() == PAGE_TYPE_NORMAL &&
        destination_entry->GetURL().SchemeIsHTTPOrHTTPS()) {
      if (page_color) {
        fallback_ux_->color_config.background_color = SkColor4f::FromColor(*page_color);
        color_source = 1;
      } else if (page_is_dark.has_value()) {
        fallback_ux_->color_config.background_color = SkColor4f::FromColor(
            *page_is_dark ? SkColorSetRGB(0x12, 0x12, 0x12)
                          : SkColorSetRGB(0xFA, 0xFA, 0xFA));
        color_source = 2;
      }
    }
    TRACE_EVENT("navigation", "SandiumBackFallbackColor",
                "color_source", color_source,
                "argb", fallback_ux_->color_config.background_color.toSkColor());
  }
  const auto sandium_size = web_contents_view_android->GetNativeView()
                                ->GetPhysicalBackingSize();
  TRACE_EVENT("navigation", "SandiumBackPreviewBounds",
              "width", sandium_size.width(), "height", sandium_size.height());
  state_ = State::kStarted;'''
    ),
    (
        'content/browser/navigation_transitions/back_forward_transition_animator.cc',
'''  CREATE_SCOPED_CRASH_KEYS();
  switch (state_) {''',
'''  CREATE_SCOPED_CRASH_KEYS();
  const auto sandium_bounds = animation_manager_->web_contents_view_android()
                                  ->GetNativeView()->GetPhysicalBackingSize();
  TRACE_EVENT("navigation", "SandiumBackHandoffState",
              "state", static_cast<int>(state_),
              "width", sandium_bounds.width(), "height", sandium_bounds.height());
  switch (state_) {'''
    ),
    (
        'chrome/android/java/src/org/chromium/chrome/browser/tab/TabWebContentsDelegateAndroidImpl.java',
'''    public int getBackForwardTransitionFallbackUXPageBackgroundColor() {
        return SemanticColorUtils.getColorSurfaceContainerHigh(mTab.getContext());
    }''',
'''    public int getBackForwardTransitionFallbackUXPageBackgroundColor() {
        // Sandium: safe neutral if no destination background was captured.
        // Do not resolve a dynamic-color surface that may itself be tinted.
        boolean dark = mTab.isIncognitoBranded()
                || (mTab.getContext().getResources().getConfiguration().uiMode
                        & android.content.res.Configuration.UI_MODE_NIGHT_MASK)
                        == android.content.res.Configuration.UI_MODE_NIGHT_YES;
        return dark ? 0xFF121212 : 0xFFFAFAFA;
    }'''
    ),
]

def transform(source, old, new):
    if source.count(new) == 1:
        if old in source.replace(new, "", 1):
            raise RuntimeError("back-transition duplicate old anchor")
        return source
    if source.count(old) != 1:
        raise RuntimeError("back-transition anchor mismatch")
    return source.replace(old, new, 1)

def plan(root):
    result = {}
    for relative, old, new in CHANGES:
        path = root / relative
        result[path] = transform(result.get(path, path.read_text()), old, new)
    return result

def main():
    root = Path(sys.argv[1]).resolve()
    for directory, pin in ((root, CHROMIUM_SHA), (root / "brave", BRAVE_SHA)):
        actual = subprocess.check_output(["git", "-C", str(directory), "rev-parse", "HEAD"], text=True).strip()
        if actual != pin:
            raise RuntimeError("back-transition pinned revision mismatch")
    # Validate every file before writing any file.
    for path, source in plan(root).items():
        path.write_text(source)
    print("SANDIUM_BACK_TRANSITION=APPLIED; runtime validation pending")

if __name__ == "__main__":
    main()
