// Held Sandium component. No Java/native-view side effects.
#include "content/public/browser/android/native_page_handoff_observation_owner.h"
#include <utility>
#include "base/check.h"
#include "base/functional/bind.h"
#include "cc/slim/layer.h"
#include "content/public/browser/android/compositor.h"
#include "content/public/browser/browser_thread.h"
#include "content/public/browser/navigation_handle.h"
#include "content/public/browser/navigation_controller.h"
#include "content/public/browser/render_frame_host.h"
#include "content/public/browser/web_contents.h"
namespace content {
namespace {
bool SameObservation(const NativePageHandoffSurfaceObservation& a,
                     const NativePageHandoffSurfaceObservation& b) {
  // Inspect independently revalidates the immutable document/widget/item owner.
  // Do not wait for unrelated selection/ink/tracked-element hints to stop changing.
  // BrowserControlsMetadata::operator== in this pin omits has_offset_tag, so
  // spell out the presentation geometry, including offset-tag authority.
  const auto& x = a.activated_metadata;
  const auto& y = b.activated_metadata;
  const auto& xc = x.browser_controls_metadata;
  const auto& yc = y.browser_controls_metadata;
  return a.embedded_surface == b.embedded_surface &&
      x.local_surface_id == y.local_surface_id &&
      x.primary_main_frame_item_sequence_number == y.primary_main_frame_item_sequence_number &&
      x.viewport_size_in_pixels == y.viewport_size_in_pixels &&
      x.device_scale_factor == y.device_scale_factor &&
      x.page_scale_factor == y.page_scale_factor &&
      x.external_page_scale_factor == y.external_page_scale_factor &&
      xc.top_controls_height == yc.top_controls_height &&
      xc.top_controls_shown_ratio == yc.top_controls_shown_ratio &&
      xc.bottom_controls_height == yc.bottom_controls_height &&
      xc.bottom_controls_shown_ratio == yc.bottom_controls_shown_ratio &&
      xc.top_controls_min_height_offset == yc.top_controls_min_height_offset &&
      xc.bottom_controls_min_height_offset == yc.bottom_controls_min_height_offset &&
      xc.has_offset_tag == yc.has_offset_tag &&
      x.root_scroll_offset == y.root_scroll_offset &&
      x.is_scroll_offset_at_top == y.is_scroll_offset_at_top &&
      x.min_page_scale_factor == y.min_page_scale_factor &&
      x.max_page_scale_factor == y.max_page_scale_factor &&
      x.root_overflow_y_hidden == y.root_overflow_y_hidden &&
      x.scrollable_viewport_size == y.scrollable_viewport_size &&
      x.root_layer_size == y.root_layer_size &&
      x.root_background_color == y.root_background_color &&
      x.has_transparent_background == y.has_transparent_background;
}
}  // namespace
NativePageHandoffObservationOwner::NativePageHandoffObservationOwner(
    WebContents& contents, NativePageHandoffTarget target,
    SceneProvider scene, Completion completion)
    : WebContentsObserver(&contents), target_(std::move(target)),
      scene_(std::move(scene)), completion_(std::move(completion)) {
  CHECK(BrowserThread::CurrentlyOn(BrowserThread::UI));
  CHECK(scene_);
  CHECK(completion_);
}
NativePageHandoffObservationOwner::~NativePageHandoffObservationOwner() {
  CHECK(BrowserThread::CurrentlyOn(BrowserThread::UI));
  // Destruction may be initiated by an owning container whose pointer has not
  // yet been cleared. Never call external completion from a destructor: it
  // could reset that container and recursively delete this object.
  ended_ = true;
  ClearPending();
  scene_.Reset();
  completion_.Reset();
}
void NativePageHandoffObservationOwner::ClearPending() {
  weak_factory_.InvalidateWeakPtrs();
  pending_.reset();
  pending_scene_.reset();
}
void NativePageHandoffObservationOwner::Complete(EndReason reason,
    std::optional<NativePageHandoffSurfaceObservation> observation) {
  CHECK(BrowserThread::CurrentlyOn(BrowserThread::UI));
  if (ended_) return;
  ended_ = true;
  ClearPending();
  scene_.Reset();
  auto completion = std::move(completion_);
  if (completion) std::move(completion).Run(reason, std::move(observation));
  // Completion may destroy this owner. Do not access members after it.
}
void NativePageHandoffObservationOwner::Revoke(EndReason reason) {
  CHECK(reason != EndReason::kPresentationObserved);
  Complete(reason);
}
void NativePageHandoffObservationOwner::ObserveAtFinalization(Compositor& compositor) {
  CHECK(BrowserThread::CurrentlyOn(BrowserThread::UI));
  if (ended_) return;
  if (!web_contents()) { Complete(EndReason::kDestroyed); return; }
  if (web_contents()->GetController().GetPendingEntry()) {
    Complete(EndReason::kNavigationStarted); return;
  }
  auto weak = weak_factory_.GetWeakPtr();
  auto scene_provider = scene_;  // Keep callback state alive across reentrant revocation.
  auto scene = scene_provider.Run();
  if (!weak || ended_) return;
  if (!scene) { ClearPending(); return; }
  if (pending_scene_ && pending_scene_.get() != scene.get()) {
    Complete(EndReason::kSceneChanged); return;
  }
  auto current = InspectNativePageHandoffSurface(*web_contents(), target_,
      target_.owner_generation, *scene);
  if (!current) { ClearPending(); return; }
  if (pending_ && SameObservation(*pending_, *current)) return;
  ClearPending();
  pending_ = std::move(current);
  pending_scene_ = std::move(scene);
  compositor.RequestSuccessfulPresentationTimeForNextFrame(base::BindOnce(
      [](base::WeakPtr<NativePageHandoffObservationOwner> owner,
         const viz::FrameTimingDetails&) {
        if (owner) owner->OnPresented();
      }, weak_factory_.GetWeakPtr()));
}
void NativePageHandoffObservationOwner::OnPresented() {
  CHECK(BrowserThread::CurrentlyOn(BrowserThread::UI));
  if (ended_ || !pending_ || !web_contents()) return;
  if (web_contents()->GetController().GetPendingEntry()) {
    Complete(EndReason::kNavigationStarted); return;
  }
  auto weak = weak_factory_.GetWeakPtr();
  auto scene_provider = scene_;  // Keep callback state alive across reentrant revocation.
  auto scene = scene_provider.Run();
  if (!weak || ended_) return;
  if (!scene || scene.get() != pending_scene_.get()) {
    Complete(EndReason::kSceneChanged); return;
  }
  auto current = InspectNativePageHandoffSurface(*web_contents(), target_,
      target_.owner_generation, *scene);
  if (!current || !SameObservation(*pending_, *current)) {
    ClearPending(); return; // Rearm only at a subsequent finalized browser frame.
  }
  Complete(EndReason::kPresentationObserved, std::move(current));
}
void NativePageHandoffObservationOwner::DidStartNavigation(NavigationHandle* navigation) {
  if (navigation->IsInPrimaryMainFrame()) Complete(EndReason::kNavigationStarted);
}
void NativePageHandoffObservationOwner::PrimaryPageChanged(Page&) {
  Complete(EndReason::kPrimaryPageChanged);
}
void NativePageHandoffObservationOwner::PrimaryPageWillBeDeactivated(Page&) {
  Complete(EndReason::kPrimaryPageChanged);
}
void NativePageHandoffObservationOwner::RenderFrameDeleted(RenderFrameHost* frame) {
  if (frame->GetGlobalId() == target_.frame) Complete(EndReason::kTargetChanged);
}
void NativePageHandoffObservationOwner::PrimaryMainFrameRenderProcessGone(base::TerminationStatus) {
  Complete(EndReason::kTargetChanged);
}
void NativePageHandoffObservationOwner::OnVisibilityChanged(Visibility visibility) {
  if (visibility != Visibility::VISIBLE) Complete(EndReason::kHidden);
}
void NativePageHandoffObservationOwner::WebContentsDestroyed() {
  // Destruction is already in progress; detach before notifying the lease owner.
  // Completion must dispose its native resource without querying WebContents.
  Observe(nullptr);
  Complete(EndReason::kDestroyed);
}
}  // namespace content
