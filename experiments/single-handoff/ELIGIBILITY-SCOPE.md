# Dormant static-layout selection hook

The complete candidate planner includes `eligibility.py` behind the explicit experimental profile.
Its plan function
transforms only exact pinned Layout.java and StaticLayout.java. Full source
fixtures retain the source hash and pin. Unknown/partial anchors fail closed.

The default Layout hook returns false. StaticLayout queries its LIVE selector,
model and scene: exact Tab object and expected WebContents, model tab ID/live
texture, actual selected scene identity, active/showing non-transition BROWSING,
unit scale/zero model X/Y/render translation, and a live non-native/non-SadTab
HTTP(S) tab without predictive Back animation. This intentionally rejects tablet
wrappers and unrecognized layouts. No copied previous eligibility flag is valid.

Proposed caller signature is:
`isSandiumNativeHandoffSceneEligible(expectedTab, expectedWebContents, selectedScene)`.
Call after getUpdatedActiveSceneLayer at finalization and repeat at presentation
callback delivery against actual CURRENT layout/scene. Never retain the Layout
from LayoutProvider as authoritative: its contract says it can change unnoticed.
A Tab object, not only tab ID, is required to reject identity reuse.

This query does NOT check Android window occlusion, modal/security overlays,
compositor attachment, geometry tags, renderer activation, or actual presentation.
Native CONTENT_OFFSET_X/Y and offset tags are not rewritten or assumed stable.
The holder/native adapter must independently invalidate on those mutations and
must supply the actual selected scene, not any chosen detached root. Root equality
alone does not prove no later cover was added. It must not be used alone to release
an outgoing page or bypass any native security surface.

Tests compile the exact injected methods extracted from fully transformed pinned
sources with explicit Java collaborators. They cover current versus stale tab/WC,
model ID, native/error-like SadTab, hidden/destroyed state, layout transitions,
unknown/wrapped scene, changed scene at delivery, nonunit/NaN geometry and replay/
fail-closed transforms. This is NOT full Android Java/nullability compilation or
device validation. No browser build is started by these tests.
