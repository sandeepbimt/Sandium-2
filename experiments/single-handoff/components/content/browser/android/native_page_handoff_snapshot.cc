// Held Sandium candidate. Android-only; deliberately absent from GN.
#include "content/public/browser/android/native_page_handoff_snapshot.h"
#include "cc/slim/layer.h"
#include "cc/slim/surface_layer.h"
#include "content/browser/renderer_host/navigation_entry_impl.h"
#include "content/browser/renderer_host/render_frame_host_impl.h"
#include "content/browser/renderer_host/render_frame_metadata_provider_impl.h"
#include "content/browser/renderer_host/render_widget_host_impl.h"
#include "content/browser/renderer_host/render_widget_host_view_android.h"
#include "content/public/browser/browser_thread.h"
#include "content/public/browser/navigation_controller.h"
#include "content/public/browser/render_frame_metadata_provider.h"
#include "content/public/browser/visibility.h"
#include "content/public/browser/web_contents.h"
namespace content {
namespace {
bool SameTarget(const NativePageHandoffTarget& a,
                const NativePageHandoffTarget& b) {
  return a.owner_generation == b.owner_generation && a.frame == b.frame &&
      a.document == b.document && a.widget_routing_id == b.widget_routing_id &&
      a.frame_sink == b.frame_sink && a.item_sequence == b.item_sequence;
}
// Tests ancestry plus alpha/hidden state only. Does NOT prove no sibling cover,
// transform, clipping or Android overlay. Final scene owner must check those.
bool HasOpaqueVisiblePath(const cc::slim::Layer& root,
                          const cc::slim::SurfaceLayer& surface) {
  if (root.hide_layer_and_subtree() || root.opacity() != 1.f) return false;
  if (&root == &surface) return surface.draws_content();
  for (const auto& child : root.children()) {
    if (HasOpaqueVisiblePath(*child, surface)) return true;
  }
  return false;
}
}  // namespace
std::optional<NativePageHandoffTarget> CaptureNativePageHandoffTarget(
    WebContents& contents, uint64_t owner_generation) {
  if (!BrowserThread::CurrentlyOn(BrowserThread::UI) || !owner_generation ||
      contents.IsCrashed() || contents.GetVisibility() != Visibility::VISIBLE)
    return std::nullopt;
  auto* frame = static_cast<RenderFrameHostImpl*>(contents.GetPrimaryMainFrame());
  if (!frame || !frame->IsActive() || !frame->IsRenderFrameLive() ||
      frame->IsErrorDocument() || !frame->GetLastCommittedURL().SchemeIsHTTPOrHTTPS())
    return std::nullopt;
  auto* widget = frame->GetRenderWidgetHost();
  if (!widget) return std::nullopt;
  auto* view = RenderWidgetHostViewAndroid::FromRenderWidgetHostView(widget->GetView());
  if (!view || !view->IsShowing() || !view->GetFrameSinkId().is_valid())
    return std::nullopt;
  auto* entry = static_cast<NavigationEntryImpl*>(
      contents.GetController().GetLastCommittedEntry());
  auto* frame_entry = entry ? entry->GetFrameEntry(frame->frame_tree_node()) : nullptr;
  if (!frame_entry || frame_entry->item_sequence_number() < 0) return std::nullopt;
  return NativePageHandoffTarget{owner_generation, frame->GetGlobalId(),
      frame->GetDocumentToken(), widget->GetRoutingID(), view->GetFrameSinkId(),
      frame_entry->item_sequence_number()};
}
std::optional<NativePageHandoffSurfaceObservation> InspectNativePageHandoffSurface(
    WebContents& contents, const NativePageHandoffTarget& expected,
    uint64_t current_owner_generation, const cc::slim::Layer& selected_scene_root) {
  auto current = CaptureNativePageHandoffTarget(contents, current_owner_generation);
  if (!current || !SameTarget(*current, expected)) return std::nullopt;
  auto* frame = static_cast<RenderFrameHostImpl*>(contents.GetPrimaryMainFrame());
  auto* widget = frame->GetRenderWidgetHost();
  if (!widget) return std::nullopt;
  auto* view = RenderWidgetHostViewAndroid::FromRenderWidgetHostView(widget->GetView());
  const auto* surface = view->GetSurfaceLayer();
  const auto& metadata = widget->render_frame_metadata_provider()->LastRenderFrameMetadata();
  if (!surface || !metadata.local_surface_id || !metadata.local_surface_id->is_valid() ||
      metadata.primary_main_frame_item_sequence_number != expected.item_sequence ||
      surface->surface_id() != viz::SurfaceId(expected.frame_sink, *metadata.local_surface_id) ||
      metadata.viewport_size_in_pixels.IsEmpty() ||
      metadata.viewport_size_in_pixels != surface->bounds() ||
      metadata.viewport_size_in_pixels != view->GetCompositorViewportPixelSize() ||
      !HasOpaqueVisiblePath(selected_scene_root, *surface)) return std::nullopt;
  return NativePageHandoffSurfaceObservation{*current, surface->surface_id(), metadata};
}
}  // namespace content
