"""Native-home source for ordinary blur; called after pinned full transition transform."""
def replace(source, old, new):
    if source.count(new)==1 and old not in source.replace(new,'',1): return source
    if source.count(old)!=1: raise ValueError('native blur source anchor mismatch: '+old[:80])
    return source.replace(old,new,1)

def header(source):
    # Migrate checkpoints produced by the prior inline-default version as well
    # as fresh pinned headers. Chromium forbids non-empty inline virtual bodies
    # in this header; defaults belong in the implementation translation unit.
    for old, new in [
        ('    virtual SkBitmap MaybeCopyNativeContent() { return SkBitmap(); }',
         '    virtual SkBitmap MaybeCopyNativeContent();'),
        ('    virtual int GetTopControlsHeight() { return 0; }',
         '    virtual int GetTopControlsHeight();'),
    ]:
        if old in source:
            source = replace(source, old, new)
    source=replace(source,'#include "cc/slim/surface_layer.h"','#include "cc/slim/surface_layer.h"\n#include "cc/slim/layer.h"\n#include "third_party/skia/include/core/SkBitmap.h"')
    source=replace(source,'    virtual std::optional<SkColor> GetThemeColor() = 0;', '''    virtual std::optional<SkColor> GetThemeColor() = 0;
    // Defaults keep non-native test/delegate implementations source compatible.
    virtual SkBitmap MaybeCopyNativeContent();
    virtual int GetTopControlsHeight();''')
    source=replace(source,'  scoped_refptr<cc::slim::SurfaceLayer> blur_layer_;','  scoped_refptr<cc::slim::Layer> blur_layer_;')
    return source

def implementation(source):
    source=replace(source, '}  // namespace\n\n// static', '''}  // namespace

SkBitmap BlurTransitionAnimationManager::WebContentsViewAndroidDelegate::
    MaybeCopyNativeContent() {
  return SkBitmap();
}

int BlurTransitionAnimationManager::WebContentsViewAndroidDelegate::
    GetTopControlsHeight() {
  return 0;
}

// static''')
    source=replace(source,'#include "cc/slim/surface_layer.h"','#include "cc/slim/surface_layer.h"\n#include "cc/slim/ui_resource_layer.h"\n#include "content/public/browser/web_contents_delegate.h"\n#include "base/trace_event/trace_event.h"')
    source=replace(source,'''    return web_contents_->GetThemeColor();
  }

 private:''','''    return web_contents_->GetThemeColor();
  }

  SkBitmap MaybeCopyNativeContent() override {
    if (!web_contents_ || !web_contents_->GetDelegate()) return SkBitmap();
    return web_contents_->GetDelegate()->MaybeCopyContentAreaAsBitmapSync();
  }

  int GetTopControlsHeight() override {
    auto* view = GetView();
    return view ? view->GetTopControlsHeight() : 0;
  }

 private:''')
    source=replace(source,'''  const viz::SurfaceId& surface_id = delegate->GetCurrentSurfaceId();
  if (!surface_id.is_valid()) {
    return;
  }

  auto* native_view = delegate->GetNativeView();
  if (!native_view) {
    return;
  }
''','''  auto* native_view = delegate->GetNativeView();
  if (!native_view) return;
  const auto size = native_view->GetPhysicalBackingSize();
  // Native pages cover the renderer surface. Never animate that hidden surface
  // as if it were the visible homepage. Capture the actual current native view.
  SkBitmap native_bitmap;
  const bool outgoing_web = prev_url.SchemeIsHTTPOrHTTPS();
  if (!outgoing_web &&
      (!navigation_handle->GetURL().SchemeIsHTTPOrHTTPS() || navigation_handle->IsPdf())) {
    // Native destinations, including HTTP PDFs, can replace their view before
    // commit. Do not mistake destination pixels for the outgoing native page.
    return;
  }
  if (!outgoing_web) {
    TRACE_EVENT("navigation", "SandiumNativeBlurCapture");
    native_bitmap = delegate->MaybeCopyNativeContent();
  }
  const bool native_pixels = !native_bitmap.empty() &&
      native_bitmap.width() == size.width() && native_bitmap.height() == size.height();
  const viz::SurfaceId& surface_id = delegate->GetCurrentSurfaceId();
  TRACE_EVENT("navigation", "SandiumOrdinaryBlurSource",
              "native_pixels", native_pixels, "outgoing_web", outgoing_web);
  if ((!outgoing_web && !native_pixels) || (outgoing_web && !surface_id.is_valid())) {
    // No safe visible pixels. Leave native navigation unchanged rather than
    // covering it with a stale renderer surface or wrong-page snapshot.
    return;
  }
''')
    source=replace(source,'''  blur_layer_ = cc::slim::SurfaceLayer::Create();
  blur_layer_->SetIsDrawable(true);
  blur_layer_->SetSurfaceId(surface_id,
                            cc::DeadlinePolicy::UseSpecifiedDeadline(0));
  blur_layer_->SetStretchContentToFillBounds(true);
  blur_layer_->SetBounds(native_view->GetPhysicalBackingSize());''','''  if (native_pixels) {
    auto container = cc::slim::Layer::Create();
    container->SetBounds(size);
    container->SetMasksToBounds(true);
    auto pixels = cc::slim::UIResourceLayer::Create();
    pixels->SetBitmap(native_bitmap);
    pixels->SetIsDrawable(true);
    pixels->SetBounds(size);
    // Sync native capture includes top-controls padding; match its documented
    // compositor coordinate contract without stretching the captured content.
    pixels->SetPosition(gfx::PointF(0.f, -delegate->GetTopControlsHeight()));
    container->AddChild(std::move(pixels));
    blur_layer_ = std::move(container);
  } else {
    auto surface = cc::slim::SurfaceLayer::Create();
    surface->SetSurfaceId(surface_id, cc::DeadlinePolicy::UseSpecifiedDeadline(0));
    surface->SetStretchContentToFillBounds(true);
    surface->SetBounds(size);
    blur_layer_ = std::move(surface);
  }
  blur_layer_->SetIsDrawable(true);''')
    source=replace(source,'''  fallback_color_layer_->SetBackgroundColor(background_color);''','''  TRACE_EVENT("navigation", "SandiumOrdinaryBlurBackground",
              "argb", background_color.toSkColor());
  fallback_color_layer_->SetBackgroundColor(background_color);''')
    source=replace(source, '  animation_state_ = state;', '''  TRACE_EVENT("navigation", "SandiumOrdinaryBlurState",
              "state", static_cast<int>(state), "navigation_id", navigation_id_);
  animation_state_ = state;''')
    source=replace(source, '  ResetNavigationState(exit_reason);', '''  TRACE_EVENT("navigation", "SandiumOrdinaryBlurExit",
              "reason", static_cast<int>(exit_reason), "animate", should_animate_out);
  ResetNavigationState(exit_reason);''')
    # Keep ownership until visual teardown, including the upstream fallback phase.
    source=replace(source, '  ResetNavigationState(TransitionExitReason::kAnimationTimerExpired);\n  SetAnimationState(AnimationState::kFadeToFallbackColor);', '  // SANDIUM_BLUR_LIFETIME_V1: timeout changes presentation, not navigation ownership.\n  // A later abort must still match DidFinishNavigation and remove the overlay.\n  SetAnimationState(AnimationState::kFadeToFallbackColor);')
    source=replace(source, 'void BlurTransitionAnimationManager::DidFirstVisuallyNonEmptyPaint() {\n  // If the page is ready before the blur hold timer expires, start the reveal.\n  // Since other paths reset `navigation_id_`, this specifically handles the\n  // direct transition from the blur layer to fade out.\n  if (navigation_id_ != 0) {\n    SignalExit(TransitionExitReason::kFinished,\n               /*should_animate_out=*/true);\n    return;\n  }\n\n  if (animation_state_ != AnimationState::kFadeOut &&\n      (blur_layer_ || fallback_color_layer_)) {\n    // If the timer already expired, we still need to trigger the final\n    // fade out of the fallback layer now that the new page is ready.\n    StartFadeOut();\n  }\n}', 'void BlurTransitionAnimationManager::DidFirstVisuallyNonEmptyPaint() {\n  // SANDIUM_BLUR_PAINT_OWNER_V1: do not reveal for an unrelated primary frame.\n  // This is an RFH guard, not a claim of matching document/frame presentation.\n  if (navigation_id_ == 0 || (!blur_layer_ && !fallback_color_layer_) ||\n      web_contents()->GetPrimaryMainFrame()->GetGlobalId() != target_rfh_id_) {\n    return;\n  }\n  // Timer expiry retains the same owner through fallback, so both visual paths\n  // now retire their navigation together with the final reveal.\n  SignalExit(TransitionExitReason::kFinished, /*should_animate_out=*/true);\n}')
    return source
