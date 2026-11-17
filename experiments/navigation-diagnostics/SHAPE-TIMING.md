# Typography/dark shape timing: evidence boundaries

`apply-typography-policy.py` observes final browser policy at the existing
Page-owned commit snapshot assignment, after main-frame resolution or inherited
child policy. Apply after page-text native + OOPIF overlays. It owns no new source
path: NavigationRequest is already restored. It does not modify the policy.

Event 26 TYPOGRAPHY_POLICY_DISPATCH: [packed_policy, outermost_main_frame, phase].
phase=0 means browser commit dispatch preparation, never renderer application.
Low byte is scale percentage; bits 8/9 are enabled/justify. Normal-profile opt-in
checks are delegated to the shared ContentBrowserClient bridge. Producer does no
async work and records source TimeTicks. Navigation identity is GetNavigationId.
No URLs, page text, selector, geometry, or content payloads.

Source tests: 3 focused tests (strict anchor/drift/idempotence, emitted numeric C++
body compile/run with collaborator stubs, no content payload). Actual #1315
composed NavigationRequest dry-run passes. These are NOT Android compilation or
renderer coverage evidence.

## What remains unimplemented

Exact pinned MetricsWebContentsObserver::OnTimingUpdated receives renderer
PageLoadTiming and FrameRenderDataUpdate, associates a valid PageLoadTracker, then
passes those structures to UpdateMetrics. This is a promising existing IPC path
for aggregate layout shift metrics without adding DOM inspection. However exact
Mojo fields and document association APIs were not locally available; primary
source retrieval failed (429/timeouts). No guessed structure fields were emitted.

A browser receipt timestamp is not the renderer event time. Using current active
document identity for a delayed timing update would risk attributing old-page
metrics to a replacement. Session epoch must be associated before async transport.
Do not silently send old buffered renderer samples into a new recording session.

Current dark dispatch event 7 plus typography dispatch event 26 and browser paint
receipt event 25 can establish browser policy-before-paint-receipt ordering only.
They cannot measure the exact dark-application delay, compositor presentation, or
whether typography caused a layout shift. Font download, website scripts, images,
ad insertion and browser controls can also affect layout.

To answer causality, record numeric renderer policy application/style lifecycle
and page-load shift timing with document identity and recording epoch, then use
same-page controlled typography OFF/ON comparisons under matched cache/network
conditions. Separate actual first-paint timing from browser receipt and compositor
presentation. A lack of recorded shifts is not proof that page geometry did not
change before first paint, nor that address-bar/native-home layout remained stable.
