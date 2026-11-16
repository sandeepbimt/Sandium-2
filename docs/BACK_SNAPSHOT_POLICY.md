# Real back-navigation snapshots

Pinned Chromium: `d331de35ca8ab1358c7a17e4bd41627d55eaef51`.
Pinned Brave: `44a84b1f89d9a35287289d6a3d493e362f5a5123`.

## Behavior

- Capture native pages (including the homepage) through the existing Android
  delegate before checking whether the renderer has a surface available to copy.
  A native view does not depend on that renderer surface. Existing window,
  compositor, URL identity, navigation and lifecycle guards remain in force.
- Start a predictive back/forward page animation only with the destination entry's
  valid, matching-size screenshot when available. A hit immediately displays the actual recorded
  page, then uses the existing transition handoff to live content.
- On a miss, use genuine compositor Gaussian blur of this tab's currently visible
  outgoing page, then the existing readiness-driven crossfade to the destination.
  Native sources require a matching-size synchronous bitmap; web sources require
  an HTTP(S) committed URL, showing view and valid surface ID. Never reuse another
  history entry or persist this transient blur as the destination's screenshot.
  If no safe outgoing pixels exist, use normal navigation without a synthetic
  blank/logo preview. Cancellation preserves the current page.
- Defensively replace the internal fallback icon resource with Sandium artwork.
  The blur fallback suppresses its logo/rounded-rectangle entirely.

## Bounds

This is not a promise of instant interactive restoration for every history entry.
Screenshots are visual previews, not live pages. BFCache eligibility remains under
Chromium/site control. Cache eviction, memory pressure, process death, changed
viewport geometry, a failed capture or a page requiring reload may still require
normal navigation. No unlimited memory retention, disk screenshot history,
forced BFCache eligibility, wrong-entry reuse or stretched snapshots are added.

The observed video confirms the old internal-page fallback. It cannot identify
its exact screenshot-cache miss reason. Moving the native delegate fixes a
concrete capture hole found in source, not a measured device-specific cause.
`SandiumBackSnapshotAvailable` records the destination cache hit and outgoing-blur
eligibility. Existing cache-miss diagnostics continue to apply to capture.

## Verification

Pinned-source transforms, idempotence and regression tests run locally. They are
not Android execution or a full Chromium compile. Device acceptance should cover:

1. Homepage -> website -> Back; repeated Back/Forward; native homepage artwork.
2. Website -> website -> Back with original scroll position; canceled gestures.
3. Rapid/chained gestures, orientation change, background/resume, memory eviction.
4. Hidden and visible browser controls without unexpected geometry jumps.
5. Incognito isolation and between-native-page guards (do not capture wrong page).

A cache miss must use a blurred current page when safe pixels exist, never a
synthetic logo page. Reduced-motion eligibility remains unchanged. A valid snapshot must remain
correct for its destination and hand off to live content without stale pixels.
