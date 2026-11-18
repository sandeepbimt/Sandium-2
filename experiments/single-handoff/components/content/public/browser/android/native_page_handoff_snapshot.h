// Held Sandium candidate. Not wired into Chromium or its build.
#ifndef CONTENT_PUBLIC_BROWSER_ANDROID_NATIVE_PAGE_HANDOFF_SNAPSHOT_H_
#define CONTENT_PUBLIC_BROWSER_ANDROID_NATIVE_PAGE_HANDOFF_SNAPSHOT_H_
#include <cstdint>
#include <optional>
#include "cc/trees/render_frame_metadata.h"
#include "components/viz/common/surfaces/surface_id.h"
#include "content/common/content_export.h"
#include "content/public/browser/global_routing_id.h"
#include "third_party/blink/public/common/tokens/tokens.h"
namespace cc::slim { class Layer; }
namespace content {
class WebContents;
// Browser-owned identity, NOT a document token echoed by the renderer.
struct NativePageHandoffTarget {
  uint64_t owner_generation;
  GlobalRenderFrameHostId frame;
  blink::DocumentToken document;
  int widget_routing_id;
  viz::FrameSinkId frame_sink;
  int64_t item_sequence;
};
// An activation/scene observation, NOT presentation or occlusion proof.
// No internal object pointer escapes. Recollect after each mutation and before
// consuming a successful browser-compositor presentation callback.
struct NativePageHandoffSurfaceObservation {
  NativePageHandoffTarget target;
  viz::SurfaceId embedded_surface;
  cc::RenderFrameMetadata activated_metadata;
};
CONTENT_EXPORT std::optional<NativePageHandoffTarget>
CaptureNativePageHandoffTarget(WebContents& contents, uint64_t owner_generation);
CONTENT_EXPORT std::optional<NativePageHandoffSurfaceObservation>
InspectNativePageHandoffSurface(WebContents& contents,
    const NativePageHandoffTarget& expected,
    uint64_t current_owner_generation,
    const cc::slim::Layer& selected_scene_root);
}  // namespace content
#endif
