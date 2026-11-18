// Held Sandium component. Not wired into Chromium or GN.
#ifndef CONTENT_PUBLIC_BROWSER_ANDROID_NATIVE_PAGE_HANDOFF_OBSERVATION_OWNER_H_
#define CONTENT_PUBLIC_BROWSER_ANDROID_NATIVE_PAGE_HANDOFF_OBSERVATION_OWNER_H_
#include <optional>
#include "base/functional/callback.h"
#include "base/memory/scoped_refptr.h"
#include "base/memory/weak_ptr.h"
#include "content/public/browser/android/native_page_handoff_snapshot.h"
#include "content/public/browser/web_contents_observer.h"
namespace content {
class Compositor;
// One-shot observer for ONE committed target. This does not acquire/release a
// native view, prove occlusion, or change navigation/security identity.
class CONTENT_EXPORT NativePageHandoffObservationOwner final : public WebContentsObserver {
 public:
  enum class EndReason {
    kPresentationObserved, kNavigationStarted, kPrimaryPageChanged,
    kHidden, kDestroyed, kTargetChanged, kSceneChanged, kCancelled,
    kFrameSinkLost, kSecurityDestination, kDeadline
  };
  // Must return the current selected scene, or null when layout/occlusion policy
  // disallows handoff. No captured detached root or arbitrary ancestor accepted.
  using SceneProvider = base::RepeatingCallback<scoped_refptr<cc::slim::Layer>()>;
  using Completion = base::OnceCallback<void(
      EndReason, std::optional<NativePageHandoffSurfaceObservation>)>;
  NativePageHandoffObservationOwner(WebContents& contents,
      NativePageHandoffTarget target, SceneProvider scene, Completion completion);
  // Silent teardown. Caller owns lease cleanup independently on its own teardown;
  // use explicit Revoke while alive if a completion notification is required.
  ~NativePageHandoffObservationOwner() override;
  NativePageHandoffObservationOwner(const NativePageHandoffObservationOwner&) = delete;
  NativePageHandoffObservationOwner& operator=(const NativePageHandoffObservationOwner&) = delete;
  // Call only after final scene selection in compositor BeginFrame, before its
  // GenerateCompositorFrame. No callback registration from arbitrary load events.
  void ObserveAtFinalization(Compositor& compositor);
  // Caller must also revoke on frame-sink/window/tab/layout/security changes and
  // its bounded native lease deadline. This class does NOT create another timer.
  void Revoke(EndReason reason);
  void DidStartNavigation(NavigationHandle* navigation) override;
  void PrimaryPageChanged(Page& page) override;
  void PrimaryPageWillBeDeactivated(Page& page) override;
  void RenderFrameDeleted(RenderFrameHost* frame) override;
  void PrimaryMainFrameRenderProcessGone(base::TerminationStatus status) override;
  void OnVisibilityChanged(Visibility visibility) override;
  void WebContentsDestroyed() override;
 private:
  void OnPresented();
  void ClearPending();
  void Complete(EndReason reason,
      std::optional<NativePageHandoffSurfaceObservation> observation = std::nullopt);
  NativePageHandoffTarget target_;
  SceneProvider scene_;
  Completion completion_;
  bool ended_ = false;
  std::optional<NativePageHandoffSurfaceObservation> pending_;
  scoped_refptr<cc::slim::Layer> pending_scene_;
  base::WeakPtrFactory<NativePageHandoffObservationOwner> weak_factory_{this};
};
}  // namespace content
#endif
