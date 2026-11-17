# Restore pinned Chromium Back controls flow

Chromium pin: `d331de35ca8ab1358c7a17e4bd41627d55eaef51`.

This change removes Sandium's suppression of Chromium's two animated `SHOWN` requests before navigation gesture startup. It restores exact upstream statements and import placement in ToolbarManager (predictive Back) and NavigationHandler (three-button history gestures). Fresh upstream files remain byte-identical; cached trees with Sandium's prior suppression are repaired.

## Source evidence and scope

Upstream requests controls visibility before `onBackStarted`. Sandium previously omitted this step, but retained `TabStateBrowserControlsVisibilityDelegate` navigation loading locks, including non-same-document history. Thus visibility could instead be requested later during destination handoff. Restoring the established sequence avoids that Sandium-specific divergence without a new viewport owner, animation, or timing heuristic.

This does not disable predictive Back, loading/security/focus constraints, offset-tag reseeding, native view transitions or upstream rendering. The disabled-feed NTP restoration correction remains intact. It introduces no new feature flags. Native `BrowserControlsRenderDrivenShowConstraint` is enabled by default at this pin, so initialized interactable web ordinarily animates through the renderer; it is incorrect to characterize every SHOWN request as a synchronous reset.

## Limits

This is an upstream-flow restoration, **not a verified elimination of every page shake**. Upstream reveal can itself change visual viewport geometry. It may relocate a discontinuity earlier in the preview rather than remove it. The original recordings establish the symptom, but contain no sufficient controls-offset/activation evidence for a definitive frame-level attribution. No fully independent address-bar geometry or transparent-surround experiment is enabled here.

Tests verify fresh/reused source, exact upstream preservation, handler ordering, transition gates, cancellation/invocation preservation, fail-before-write and repeat application. These are source transformation tests, not a phone runtime pass. Device acceptance still needs hidden/shown bar, Back commit/cancel, web/native homepage, BFCache/cold restore, BCIV offset tags and focus/security locks. Do not label the phone issue fixed until these are observed.
