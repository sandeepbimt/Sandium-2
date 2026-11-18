# Dormant native-home holder integration

The complete candidate planner includes this module behind the explicit experimental profile.
It is limited to an ordinary
committed `showRenderedPage()` transition from the explicitly marked regular
Android NewTabPage to an HTTP(S) renderer document. Generic hide, native-to-native,
PDF-like pages, settings and Incognito do not create offers.

## Ownership and presentation

TabImpl clears its active native-page identity normally. A local single-use offer
separately transfers destruction responsibility to the holder before content-change
notification. Nested notifications and exceptions settle the local unclaimed
offer, not mutable global state. A per-Tab resource reservation forbids overlapping
offers for the same NativePage until the first offer closes. Nested generic disposal
is deferred to that reservation; active-page restoration is not destroyed. A successfully claimed resource must be closed
by its holder even if native observation rejects it.

The holder leaves the retired native root in its existing parent. It skips only
that root's removal while attaching the normal destination ContentView beneath
it. It does not wrap, reparent, translate, resize, capture, blur or animate the
retired root. Normal Chromium owns destination sizing and browser controls.
Destination attachment requests normal Android layout. The native observation
begins only at a subsequent normal draw traversal with unchanged geometry and
live safety checks, never from a timeout or a guessed frame.

The compositor adapter checks the actual selected scene, document/item identity,
activated surface metadata and successful presentation. The holder's completion
releases its exact token whether the observation succeeded or was revoked.

## Explicit bounded failure policy

The holder has a **new 500 ms maximum safety budget**, measured from acquisition
using uptime and never reset. Successful presentation releases immediately. The
budget is not a minimum delay, a readiness test or a reuse of a history-animation
deadline. On expiry normal Chromium content is exposed with no extra fade. Slow
or failed content may therefore still show its ordinary blank/loading state.
There is no promise of universally flash-free navigation.

## Safety and cleanup

- Unknown accessibility/obscuring/root UI state denies acquisition.
- A dedicated all-device accessibility observer uses the pinned immediate seed;
  it does not enable the existing tablet virtual accessibility provider on phones.
- The RootUiCoordinator predicate is queried live. Obscuring is seeded from real
  handler getters because its observer registration has no initial callback.
- Retained content cannot receive touch, drag, hover, generic motion or key input.
  Input revokes retention. Touch/drag and activating-key sequence tails are
  consumed. Back/Escape revoke and retain normal native dispatch.
- Focused descendants, keyboard, in-flight gestures/scroll, animated roots and
  unexpected visible holder children deny acquisition. Root-only focus is cleared.
- The retained subtree is hidden from accessibility and descendant focus, then
  restored on cleanup. Accessibility activation synchronously revokes.
- Bounds, controls, stop/detach, loss of window focus, authoritative overlay hide,
  shutdown and unsafe-before-draw states revoke. No snapshot is exported.
- Ownership fields clear before cleanup. Old view disposal precedes native cancel
  so a reentrant cancel cannot reuse the same cached root before old cleanup.
  Exact active-native-page restoration is not removed or destroyed. Acquisition is
  forbidden during the entire restore/dispose/cancel section, so reentrant navigation
  uses normal Chromium instead of capturing partially restored view attributes.

## Verification limits

Tests compile actual new Java components and extracted production method bodies
with explicit Android/Chromium collaborator doubles, and replay transformations
against complete pinned source fixtures. They exercise nested notifications,
exceptions, same-root reentry, initial layout waiting, identity-scoped cancellation,
deadline, geometry changes and input sequences. Complete staged source composition
is tested separately. These are **not** a full Android/generated-JNI build, Android
ViewRoot/SurfaceView presentation test or phone validation. Conservative revocation
may shorten or prevent retention on real control/layout sequences. The existing
native-history callback repair and ordinary web handoff are separate stages.
