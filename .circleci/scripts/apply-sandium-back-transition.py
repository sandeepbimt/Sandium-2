#!/usr/bin/env python3
"""Pinned, fail-closed destination-aware back preview and trace diagnostics.

Keeps BFCache and screenshot safety guards; captures native pages independently
of renderer surfaces and blurs only the current visible page on cache misses.
"""
from pathlib import Path
import subprocess
import sys

CHROMIUM_SHA = "d331de35ca8ab1358c7a17e4bd41627d55eaef51"
BRAVE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
CHANGES = [
    (
        'content/browser/renderer_host/navigation_transitions/navigation_transition_utils.cc',
'''  if (!rwhv->IsSurfaceAvailableForCopy()) {
    // See https://crbug.com/368289857: If we hide the WebContents after a
    // same-RFH navigation starts, we invalidate the `viz::LocalSurfaceID`
    // and the browser UI will not be embedding a new ID when the navigation
    // finishes (`WebContentsImpl::DidNavigateMainFramePreCommit()` and
    // `RenderWidgetHostViewAndroid::DidNavigate()`). We won't be able to
    // screenshot the page if we navigate the WebContents again before the UI
    // embeds
    InvokeTestCallbackForNoScreenshot(navigation_request);
    last_committed_entry->navigation_transition_data()
        .set_cache_hit_or_miss_reason(
            CacheHitOrMissReason::kBrowserNotEmbeddingValidSurfaceId);
    return false;
  }

  // https://crbug.com/369356401: It's possible to issue two CopyOutputRequests
  // against the last committed entry. Bump the `copy_output_request_sequence()`
  // to prevent double-caching the screenshot.
  last_committed_entry->navigation_transition_data()
      .increment_copy_output_request_sequence();
  int request_sequence = last_committed_entry->navigation_transition_data()
                             .copy_output_request_sequence();
  bool copied_via_delegate;
  if (EnableNativePageScreenshotIntoHardwareBuffer()) {
    copied_via_delegate =
        navigation_request.GetDelegate()->MaybeCopyContentAreaAsHardwareBuffer(
            base::BindOnce(
                &CacheScreenshotHardwareBufferImpl,
                navigation_controller.GetWeakPtr(),
                navigation_request.GetWeakPtr(),
                last_committed_entry->navigation_transition_data().unique_id(),
                request_sequence,
                SupportsETC1NonPowerOfTwo(navigation_request)));
  } else {
    copied_via_delegate =
        navigation_request.GetDelegate()->MaybeCopyContentAreaAsBitmap(
            base::BindOnce(
                &CacheScreenshotImpl, navigation_controller.GetWeakPtr(),
                navigation_request.GetWeakPtr(),
                last_committed_entry->navigation_transition_data().unique_id(),
                /*is_copied_from_embedder=*/true, request_sequence,
                SupportsETC1NonPowerOfTwo(navigation_request)));
  }

  if (!copied_via_delegate && only_use_embedder_screenshot) {
    InvokeTestCallbackForNoScreenshot(navigation_request);
  }

  if (copied_via_delegate || only_use_embedder_screenshot) {
    return false;
  }

''',
'''  // https://crbug.com/369356401: It's possible to issue two CopyOutputRequests
  // against the last committed entry. Bump the `copy_output_request_sequence()`
  // to prevent double-caching the screenshot.
  last_committed_entry->navigation_transition_data()
      .increment_copy_output_request_sequence();
  int request_sequence = last_committed_entry->navigation_transition_data()
                             .copy_output_request_sequence();
  bool copied_via_delegate;
  if (EnableNativePageScreenshotIntoHardwareBuffer()) {
    copied_via_delegate =
        navigation_request.GetDelegate()->MaybeCopyContentAreaAsHardwareBuffer(
            base::BindOnce(
                &CacheScreenshotHardwareBufferImpl,
                navigation_controller.GetWeakPtr(),
                navigation_request.GetWeakPtr(),
                last_committed_entry->navigation_transition_data().unique_id(),
                request_sequence,
                SupportsETC1NonPowerOfTwo(navigation_request)));
  } else {
    copied_via_delegate =
        navigation_request.GetDelegate()->MaybeCopyContentAreaAsBitmap(
            base::BindOnce(
                &CacheScreenshotImpl, navigation_controller.GetWeakPtr(),
                navigation_request.GetWeakPtr(),
                last_committed_entry->navigation_transition_data().unique_id(),
                /*is_copied_from_embedder=*/true, request_sequence,
                SupportsETC1NonPowerOfTwo(navigation_request)));
  }

  if (!copied_via_delegate && only_use_embedder_screenshot) {
    InvokeTestCallbackForNoScreenshot(navigation_request);
  }

  if (copied_via_delegate || only_use_embedder_screenshot) {
    return false;
  }

  // Sandium: a native page is drawn by Android, not the renderer surface.
  // Test renderer copy eligibility only after the embedder had its chance.
  if (!rwhv->IsSurfaceAvailableForCopy()) {
    // See https://crbug.com/368289857: If we hide the WebContents after a
    // same-RFH navigation starts, we invalidate the `viz::LocalSurfaceID`
    // and the browser UI will not be embedding a new ID when the navigation
    // finishes (`WebContentsImpl::DidNavigateMainFramePreCommit()` and
    // `RenderWidgetHostViewAndroid::DidNavigate()`). We won't be able to
    // screenshot the page if we navigate the WebContents again before the UI
    // embeds
    InvokeTestCallbackForNoScreenshot(navigation_request);
    last_committed_entry->navigation_transition_data()
        .set_cache_hit_or_miss_reason(
            CacheHitOrMissReason::kBrowserNotEmbeddingValidSurfaceId);
    return false;
  }

'''
    ),
    (
        'content/browser/navigation_transitions/back_forward_transition_animation_manager_android.cc',
'''  CHECK(animator_factory_);''',
'''  // Sandium: prefer the real destination snapshot. If it is unavailable,
  // animate a transient blurred copy of this tab's currently visible page.
  // Never substitute another history entry or retain the blur in the cache.
  auto* screenshot = static_cast<NavigationEntryScreenshot*>(
      destination_entry->GetUserData(NavigationEntryScreenshot::kUserDataKey));
  const bool sandium_has_preview =
      screenshot && screenshot->IsValid() &&
      screenshot->dimensions_without_compression() ==
          web_contents_view_android_->GetNativeView()->GetPhysicalBackingSize();
  auto sandium_embedder_content = MaybeCopyContentAreaAsBitmapSync();
  const auto sandium_size =
      web_contents_view_android_->GetNativeView()->GetPhysicalBackingSize();
  if (!sandium_has_preview &&
      (sandium_embedder_content.width() != sandium_size.width() ||
       sandium_embedder_content.height() != sandium_size.height())) {
    sandium_embedder_content.reset();
  }
  auto* sandium_view = static_cast<RenderWidgetHostViewAndroid*>(
      web_contents_view_android_->web_contents()->GetRenderWidgetHostView());
  const bool sandium_can_blur_current =
      !sandium_embedder_content.empty() ||
      (web_contents_view_android_->web_contents()->GetLastCommittedURL()
           .SchemeIsHTTPOrHTTPS() &&
       sandium_view && sandium_view->IsShowing() &&
       sandium_view->GetSurfaceLayer() &&
       sandium_view->GetSurfaceLayer()->surface_id().is_valid());
  TRACE_EVENT("navigation", "SandiumBackSnapshotAvailable",
              "available", sandium_has_preview,
              "blur_current", !sandium_has_preview && sandium_can_blur_current);
  if (!sandium_has_preview && !sandium_can_blur_current) {
    // No current pixels (for example a destroyed renderer): normal history
    // navigation is safer than a blank or wrong-document synthetic preview.
    return;
  }

  CHECK(animator_factory_);'''
    ),
    (
        'content/browser/navigation_transitions/back_forward_transition_animation_manager_android.cc',
'''#include "content/browser/navigation_transitions/back_forward_transition_animator.h"''',
'''#include "content/browser/navigation_transitions/back_forward_transition_animator.h"
#include "content/browser/renderer_host/render_widget_host_view_android.h"
#include "cc/slim/surface_layer.h"'''
    ),
    (
        'content/browser/navigation_transitions/back_forward_transition_animation_manager_android.cc',
'''      MaybeCopyContentAreaAsBitmapSync(), this);''',
'''      std::move(sandium_embedder_content), this);'''
    ),
    (
        'content/browser/navigation_transitions/back_forward_transition_animator.cc',
'''    auto screenshot_layer = cc::slim::SolidColorLayer::Create();
    screenshot_layer->SetBackgroundColor(
        fallback_ux_->color_config.background_color);
    screenshot_layer_ = std::move(screenshot_layer);''',
'''    // Sandium: this is explicitly the outgoing page, not a fabricated
    // destination screenshot. Its lifetime is this animation only.
    auto blur_container = cc::slim::Layer::Create();
    blur_container->SetMasksToBounds(true);
    scoped_refptr<cc::slim::Layer> blur_content;
    if (!embedder_content.empty()) {
      auto native_content = cc::slim::UIResourceLayer::Create();
      native_content->SetBitmap(embedder_content);
      native_content->SetPosition(gfx::PointF(
          0.f, -animation_manager_->web_contents_view_android()->GetTopControlsHeight()));
      native_content->SetBounds(animation_manager_->web_contents_view_android()
                                   ->GetNativeView()->GetPhysicalBackingSize());
      blur_content = std::move(native_content);
    } else {
      auto* view = static_cast<RenderWidgetHostViewAndroid*>(
          animation_manager_->web_contents_view_android()
              ->web_contents()->GetRenderWidgetHostView());
      CHECK(view);
      CHECK(view->IsShowing());
      const auto* current_surface = view->GetSurfaceLayer();
      CHECK(current_surface);
      CHECK(current_surface->surface_id().is_valid());
      auto surface = cc::slim::SurfaceLayer::Create();
      // A zero deadline reuses already displayed textures. Holding this
      // surface reference prevents reclamation during the transition.
      surface->SetSurfaceId(current_surface->surface_id(),
                           cc::DeadlinePolicy::UseSpecifiedDeadline(0));
      surface->SetPosition(current_surface->position());
      surface->SetBounds(current_surface->bounds());
      surface->SetTransform(current_surface->transform());
      blur_content = std::move(surface);
    }
    blur_content->SetIsDrawable(true);
    blur_content->SetFilters({cc::slim::Filter::CreateBlur(
        DipToPx(10), SkTileMode::kClamp)});
    blur_container->AddChild(std::move(blur_content));
    screenshot_layer_ = std::move(blur_container);'''
    ),
    (
        'content/browser/navigation_transitions/back_forward_transition_animator.cc',
'''  bool should_draw_rrect = fallback_ux_ && !favicon_bitmap.drawsNothing();''',
'''  // Sandium: outgoing blur has no destination favicon or browser logo.
  bool should_draw_rrect = false;'''
    ),
    (
        'chrome/android/java/src/org/chromium/chrome/browser/tab/TabWebContentsDelegateAndroidImpl.java',
'''Drawable drawable = ApiCompatibilityUtils.getDrawable(res, R.drawable.chromelogo16);''',
'''Drawable drawable = ApiCompatibilityUtils.getDrawable(res, R.drawable.sandium_toolbar_mark);'''
    ),
    (
        'cc/slim/layer_tree_impl.cc',
'''    // Apply new pass's occlusion to parent pass.
    if (transform_new_pass_to_parent_target.Preserves2dAxisAlignment()) {''',
'''    // Children draw at opacity 1 inside this pass, but their occlusion may
    // hide parent content only when the composed pass is fully opaque.
    // Preserve rear content during translucent screenshot crossfades.
    if (parent_opacity * layer.opacity() == 1.0f &&
        transform_new_pass_to_parent_target.Preserves2dAxisAlignment()) {'''
    ),
    (
        'content/browser/navigation_transitions/back_forward_transition_animator.cc',
'''  CHECK(new_render_widget_host_);
  CHECK_NE(primary_main_frame_navigation_entry_item_sequence_number_''',
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
'''#include "content/browser/renderer_host/navigation_request.h"''',
'''#include "content/browser/renderer_host/navigation_request.h"
#include "content/browser/renderer_host/page_impl.h"'''
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
