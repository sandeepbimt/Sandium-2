# Dormant Android target/surface observation helper

The complete candidate source planner registers this collector and its observation
owner in GN and connects the JNI/holder modules, behind the explicit experimental profile.
No actual GN generation, Android compile or device rendering test has run.
The collector alone has no lease or reveal authority and MUST NOT be used alone
to release retained content. The experiment requires explicit profile activation.

## Source boundary and verified calls

`CaptureNativePageHandoffTarget` reads only the active/live primary HTTP(S),
non-error document of a visible, non-crashed WebContents on the UI thread. It
captures browser RFH ID and actual DocumentToken, widget routing ID/frame-sink ID,
committed primary frame's session-history item sequence, and the caller's nonzero
lease generation. Unknown/native/error targets are ineligible, not delayed.

`InspectNativePageHandoffSurface` recollects that identity, compares the actual
RWHVA SurfaceLayer primary ID with activated metadata (not DFH's allocator ID),
checks metadata item sequence, and conservatively requires metadata physical
viewport, SurfaceLayer bounds and current compositor viewport to agree. It checks
opaque/nonhidden ancestry under the root supplied by the scene owner. It returns
copied values, not content-internal pointers. The metadata's controls/scale fields
are retained for a future owner to compare across registration and delivery.

Pinned Chromium native Back uses the same frame-entry item sequence versus
activated-metadata comparison. The browser DocumentToken protects same-RFH reuse;
it is NOT a renderer-echoed document identity. Same-document navigation must still
invalidate the caller's generation. Invalid sequence -1 is rejected, including
native-page cases noted in the pinned history animator.

The exact public RFH/widget APIs do not expose the actual SurfaceLayer or metadata
provider accessor. Internal casts and collection therefore remain inside content.
Chrome may include only the new public header, with no content/browser dependency.
The compressed API evidence fixture records pin, full source hashes and precise
excerpts, not a replacement Chromium header set.

## What is NOT proved

A nonempty observation is not presentation, paint completeness, non-eviction, or
absence of a fallback/cover. Ancestor visibility does not prove transforms, clips,
filters, siblings or Android overlays leave the target fully visible. The caller
must supply the ACTUAL selected scene root, not any detached subtree. Browser
controls heights/offsets may still change after collection. This collector neither
locks surfaces nor prevents subsequent eviction. Physical viewport equality is a
conservative eligibility gate; unsupported geometry returns empty, never changes
layout or extends a timeout.

Future integration must validate final scene selection and target coverage, then
register successful presentation in that frame's finalization; invalidate on all
navigation (including same-document), primary-page/widget/surface/scene/viewport,
visibility, destruction, cancellation, error and security changes. A later success
can belong to a retried frame; generation and observations must still match. The
native outgoing resource must be browser-owned NTP only, isolated from active
TabImpl.mNativePage, and noninteractive/inaccessible while leased. Error/security
paths must release through native policy, not wait on this HTTP-only collector.

## Build wiring (deliberately not applied)

Pinned `content/browser/BUILD.gn` Android source block at line3120 owns browser
implementation files (e.g. android/android_surface_control_compositor.cc).
Pinned `content/public/browser/BUILD.gn` Android source block at line679 owns
public Android headers (e.g. android/compositor.h). A future reviewed integration
adds this .cc/header to those lists and checks Android dependency/public-header
visibility. No chrome target should import the private implementation header.

## Verification limits

The host test compiles the EXACT helper .cc with explicit API doubles and checks
owner changes, stale activation/item/surface, viewport mismatch, ancestry, hidden/
transparent paths, error/native/inactive/crashed documents and thread confinement.
This is collector logic coverage, NOT full pinned-header, GN, Android or device
compilation. API excerpts were independently checked against the exact pin.

## Dormant compositor-finalization observation owner

`NativePageHandoffObservationOwner` is a one-shot content-owned observer component.
It registers the actual Chromium successful-presentation callback only when called
from final scene finalization. An unchanged pending observation is not registered
again. Changed geometry/metadata invalidates old callback authority before rearming;
a late success from an older registration cannot approve the new observation.
Delivery recollects the current selected scene, target and metadata, and requires
identity/equality with the registered observation. Callback state is retained
locally across reentrant scene-provider teardown, and completion clears authority
before invoking external code. The observer itself never removes a view.

Native lifecycle callbacks revoke on primary navigation start, primary page change
or deactivation, target frame deletion, renderer process exit, hidden contents and
WebContents destruction. During destruction it detaches first and does not recapture
content. Completion for that case must release the caller's owned native resource
without querying WebContents, whose destruction is already in progress.

Integration obligations remain explicit:
- Construct for the committed target AFTER relevant commit/page-change observer
  dispatch; do not make the target's own completion event revoke a new operation.
- Supply an actual current selected scene provider with layout/occlusion policy,
  returning null for ineligible scenes. A detached root is not a valid provider.
- Call ObserveAtFinalization only after final scene selection inside BeginFrame.
- Revoke on compositor frame-sink/window loss, tab/layout/security change and a
  bounded native lease deadline. This class does not add a new arbitrary timer.
- The browser-native page lease, input/accessibility and Java/JNI adapter are NOT
  integrated. No content is currently retained or revealed by this component.
- A successful callback plus matching observation is not pixel-perfect/occlusion
  proof, dark-policy readiness or an Android native-view atomic-swap guarantee.

The host owner test compiles both actual .cc files against explicit API doubles.
It covers valid/deduplicated success, stale callbacks after rearming or revocation,
metadata changes before delivery, pending navigations, scene changes, lifecycle
callbacks and provider/completion teardown. It is not a Chromium/Android build.

Destructor policy: observation-owner destruction is silent, invalidates pending
callbacks and clears closures without external notification. The holder/Tab owner
must release its native-page lease independently during its own teardown. Explicit
Revoke while the observation owner is alive provides completion notification.
Calling arbitrary completion from a destructor could reset an owning unique_ptr
and recursively delete the same owner; the source regression forbids that.

The owner host harness also runs AddressSanitizer and UndefinedBehaviorSanitizer.
LeakSanitizer is disabled in this traced executor because it cannot inspect
threads under ptrace; leak detection is not claimed. Two negative source mutations
prove the regressions fail: removing pending-callback invalidation, and restoring
external completion from the destructor. The latter must reproduce an ASan
heap-use-after-free or double-free, not merely any failed subprocess.

Observation-owner declaration lives in content/public/browser/android and is
CONTENT_EXPORT/final. Its .cc stays in content/browser/android. Chrome adapters
must include only the public declaration; no content/browser include is needed.
GN registration remains unapplied: add the public header to the Android public
source list and implementation to the Android browser list alongside the collector.

## Dormant source registration plan

`content_registration.py` now prepares both exact pinned Android GN list changes
and copies the two public headers plus two private implementation files. It is
NOT imported by the active installer. Existing different files, partial/duplicate
entries and anchor drift fail closed. Exact-source tests verify replay and that
removing additions restores the pinned lists byte-for-byte. The public Android
source target already depends on `//cc/slim`; no dependency on content internals
is introduced into Chrome or public headers.

This is registration preparation, not a successful `gn gen`, dependency-check,
JNICALL generation, native compilation, or Android build. Complete holder/Tab
integration and full source composition are still prerequisites for activation.

Presentation matching now uses an explicit geometry signature rather than the
entire metadata equality operator. The pinned controls equality omits
`has_offset_tag`; the handoff signature explicitly compares it alongside controls
heights, ratios and min-height offsets. Surface/item, viewport/scales,
scroll/viewport/root geometry, transparency and fallback background remain guarded.
Selection, tracked-element, delegated-ink, mobile-optimization and direction hints
cannot endlessly postpone release when this presentation geometry is unchanged.
Negative regressions reject both omission of offset-tag authority and restoration
of the full-metadata quiet-page requirement. This does not certify dark-policy
readiness or pixels; it narrows the presentation observation contract only.
