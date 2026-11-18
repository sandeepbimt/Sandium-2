# Single-handoff experimental candidate

The isolated profile is enabled for the first authorized experimental compilation.
The CI entrypoint applies the complete source candidate and supports exact rollback.
See INTEGRATION-STATUS.md for source coverage and unverified runtime outcomes.
It is not an accepted replacement for the frozen Sandium release. Base: 4a00f05 (the source
used for the Chromium-navigation comparison), Chromium d331de35.

## Bounded implementation

* Ordinary web navigation: disable the optional blur transition's additional
  retained/solid/fade stages and let existing Chromium paint holding own eligible
  handoffs. Do not change origin, activation, timeout or error handling policies.
* Native-home handoff: one generation owns readiness and completion; cancel or
  replace transitions without accumulating callbacks. Observe attachment/layout
  readiness where supported, with the existing bounded native deadline.
* Preserve wallpaper, address-bar styling, shortcuts and Chromium controls
  geometry. Do not add a second viewport owner, arbitrary offsets or blanket
  snapshots.

These changes are not a universal no-flash guarantee. Activated renderer metadata
is not physical presentation; native pre-draw is not physical presentation either.
Slow destinations, security pages, renderer failure and website-authored layout
changes need legitimate visible handling. Do not hide errors or indefinitely
present an old origin under a new origin's address.

## Application and rollback

After native-navigation profile application, run `apply.py SOURCE --mode on`,
then `--mode on --verify-only`. All participating modules must be present. The
complete postimage is planned before writes and journaled before mutation.

Before any native-navigation restore or ordinary product replay, run this
profile `--mode off`. It checks exact pre/post hashes and refuses to overwrite
unknown changes. Only then restore native-navigation or the frozen product.
Do not enable the profile until full product composition and independent review
have passed. The entrypoint restores the outer journal before native replay and
verifies both layers without temporarily mutating source.

## Acceptance

Host tests validate startup feature selection and lifecycle/transaction rules,
not visual quality or full Android compilation. Device gate: repeated address
entry/link/external-intent/home/Back/forward with controls hidden and shown,
light/dark combinations, rapid supersession, cancelled gestures, slow/error
loads, renderer destruction and tab changes. Compare screenshots/video against
actual content readiness; separate browser-introduced jumps from website shifts.

## References

* https://developer.chrome.com/blog/paint-holding
* https://chromium.googlesource.com/chromium/src/+/refs/heads/main/content/browser/renderer_host/navigator.cc
* https://chromium.googlesource.com/chromium/src/+/main/docs/ui/android/browser_controls.md
* Pinned BackForwardTransitionAnimator::SubscribeToNewRenderWidgetHost and
  OnRenderFrameMetadataChangedAfterActivation: destination item-sequence guards
  are precedent for any future deeper surface work, not justification for an
  unvalidated replacement renderer manager in this candidate.

## Immediate interaction requirement

Taps must begin navigation immediately. Keep the existing subtle transparent green
address-bar progress fill; the candidate does not change it, URL display, Back,
Cancel or navigation dispatch timing. Back/Cancel must remain browser actions even
while a page itself is not interactive. Never wait for full network idle before
acknowledging a tap. Current implementation deliberately reuses Chromium's bounded
paint holding rather than adding an old-page/new-URL retention mode.

Not yet implemented or verified: a new guarantee of immediate visual tap feedback,
atomic presented-frame handoff across every native/ordinary route, and physical
on-device verification of the retained progress styling. These are acceptance
requirements, not claims supported by host tests.
