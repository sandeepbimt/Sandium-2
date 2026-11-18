# Remaining all-route boundary: source feasibility, not an implemented fix

The reviewed candidate through `98ad5a1` remains disabled. No experimental build
was published or triggered. The owner requires complete preparation before a run.

## Exact pinned ordinary route

Chromium `d331de35ca8ab1358c7a17e4bd41627d55eaef51` (156.0.8078.74):
`TabImpl.handleDidFinishNavigation` selects `showRenderedPage` at commit.
`hideNativePage` notifies the holder and destroys the old native page.
`CompositorViewHolder` installs the replacement overlay; ordinary native layout
and renderer surface holding have different owners. These are intentional native
contracts, not proof that a particular observed flash is caused by this boundary.
No further narrow ordinary-route defect was established in the source audit.

Waiting for FCP in Java would not prove presentation and would mishandle blank,
error and security destinations. Repeated viewport sizing is not cumulative
inset subtraction: it recomputes dimensions from the current native inputs.

## Option A: synchronize the existing native and compositor surfaces

Correction from the framework source and public SDK: the framework has a
SurfaceView/frame-callback SurfaceSyncGroup overload, but that overload and its
callback are `@hide`. The public API 34 interface does not expose it to an ordinary
application. Do not introduce hidden-API reflection as a shipping dependency.
Public root-surface transaction support alone does not identify Chromium's next
SurfaceView buffer. A sync completion callback does not itself prove application
or display. Chromium's requestRender and already-drawn swap callback are not
substitutes.

A real implementation requires a destination-associated compositor buffer bridge,
viewport identity, deferred native-page destruction, and one input/accessibility
owner. Do not hold the whole root frame while waiting for a slow page: that would
also hold the toolbar/progress UI. No such bridge is implemented in this candidate.

Reference: https://android.googlesource.com/platform/frameworks/base/+/master/core/java/android/window/SurfaceSyncGroup.md

## Option B: render the homepage through Chromium WebUI

Upstream has real Android WebUI NTP work, not merely a hypothetical desktop port:
https://chromium.googlesource.com/chromium/src/+/42937e4ba2e5d383daf6f0e057f5fe530ac1a451
The initial May 2026 change was explicitly a prototype. The pinned revision
contains ENABLE_WEBUI_NTP registration and Android NewTabPageUI paths. However,
the current pinned `search::IsWebUiNtpEnabledForDesktopAndroid()` requires BOTH
`base::android::device_info::is_desktop()` and `kUseWebUiNtpAndroid`.

Pinned `chrome/browser/android/ntp/new_tab_page_url_handler.cc` rewrites
chrome://newtab using the default-search provider's 1P/3P NTP only under that
predicate, falling back to chrome-native://newtab if its target is invalid.
It is not a phone-ready feature toggle, and direct chrome-native URLs need separate
migration treatment.

A dedicated packaged Sandium mobile WebUI is the cleaner evaluation than enabling
the desktop page wholesale. Required parity/security work:

- Narrow origin-bound Mojo/browser handlers, CSP and packaged assets; no broad
  JavaScript interface or file:// wallpaper access.
- Preserve the existing mobile CustomLinksManager scope and up-to-200 shortcuts,
  rename/order/defaults; do not silently switch to desktop preference storage.
- Wallpaper selection, crop, persistence and raised icon/name appearance.
- Explicit treatment of old native NTP history/restored tabs and home/newtab entry.
- Normal/incognito profile isolation and native private-page fallback.
- Audit Java toolbar `isNativePage`/NTP assumptions, focus, keyboard and controls.
- Android compilation and actual navigation/interaction/restore tests.

This removes one architectural boundary: native-home View versus web SurfaceView.
It does not remove renderer process swaps, website layout shifts, or dark-policy
paint timing in ordinary web-to-web navigation. It must not be advertised as the
complete navigation fix before those independent routes are verified.

## Current conclusion

Neither option is implemented or validated end to end. Preserve Chromium's
security and bounded-retention policies; do not fill the gap with blanket outgoing
page screenshots or delayed URL/security identity. Keep the reviewed lifecycle
repairs reversible and disabled while the broader design is evaluated.


## Deeper native bridge audit (still design only)

Exact pinned APIs provide useful building blocks, not an all-route fence:

- `content::Compositor::RequestSuccessfulPresentationTimeForNextFrame` accepts a
  `viz::FrameTimingDetails` callback. CompositorView already uses it for metrics.
  CompositorImpl delegates to its layer-tree host and returns without a callback
  if no host exists. A new owner therefore needs explicit teardown/cancellation,
  not an unbounded wait. A generic successful next frame is not proof that a
  particular destination surface was displayed.
- CompositorViewHolder.onCompositorLayout calls layout update and finalizeLayers
  before commit. This is the candidate point to validate final scene ownership;
  its existing callback queues acknowledge swaps, not presentation.
- Render-frame metadata activation identifies a history item, local surface and
  viewport, but does not expose the renderer frame token to observers. Activation
  is not physical display or proof dark styling has finished.
- DelegatedFrameHostAndroid updates its local_surface_id before a visibility
  early return. Its SurfaceId getter therefore does not prove embedding. Inspect
  the actual SurfaceLayer, its primary surface, bounds and scene ancestry.
- StaticTabSceneLayer/ContentLayer can choose a live wrapper containing any
  drawable leaf, and can still supply a thumbnail. Neither `can_use_live` nor a
  drawable leaf establishes target-document identity.
- CompositorView's existing fluid-resize path coordinates native draw pause with
  AttachedSurfaceControl.applyTransactionOnDraw and a sequence-owned committed
  listener. This is a real narrow transaction precedent, not permission to pause
  the compositor while a network page loads. Pausing would also stall compositor
  toolbar/progress feedback.

Before production implementation, the missing contract must associate the
validated destination live surface and viewport with the browser frame that
actually gets submitted and presented. Registering a generic next-frame callback
from an arbitrary commit callback would not establish that association. Scene,
primary page, surface, viewport or owner changes must invalidate the pending
transaction before any callback can release an old native view.

Route policy remains asymmetric: native homepage retention is browser-owned UI;
retaining an arbitrary outgoing site beneath a newly committed internal or
cross-origin identity is not acceptable. Web-to-native must coordinate identity,
input and surface replacement rather than copy native-to-web retention logic.
Security/error/crash/blank destinations retain Chromium's native escape policy.

Public API references:
- https://developer.android.com/reference/android/window/SurfaceSyncGroup
- https://android.googlesource.com/platform/frameworks/base/+/refs/heads/main/core/java/android/window/SurfaceSyncGroup.java

No new bridge code, active profile, push or build is represented by this audit.

### Submission association resolved at the pinned cc::slim implementation

`cc/slim/layer_tree_impl.cc` provides the missing ordering evidence:
`BeginFrame` calls client BeginFrame (which performs Java scene finalization),
then synchronously calls GenerateCompositorFrame. A callback registered during
final scene validation is moved into PresentationCallbackInfo alongside that
newly generated `out_frame.metadata.frame_token`. It is not attached to an older
already in-flight frame.

`DidPresentCompositorFrame` processes entries with token <= the feedback token.
Successful callbacks survive failed presentation and run on a subsequent
successful frame. Therefore this is an at-or-after-submission fence, not a
strict exactly-one-frame callback. Every intervening page, scene, viewport,
surface, frame-sink and security-owner change must revoke the pending lease.
The callback must revalidate ownership before releasing native content. Lack of
a root or nonempty viewport can defer generation; registration is not completion.

The pinned RenderWidgetHostViewAndroid::GetSurfaceLayer already returns the
actual DFH content layer, avoiding reliance on its prematurely advanced SurfaceId
getter. This is a useful inspection primitive, not yet a working cross-layer
handoff. Target-document identity, selected live-scene ancestry, fallback/eviction,
native-page lifetime, input and accessibility ownership still need integration
and real Android tests before any experimental profile activation.
