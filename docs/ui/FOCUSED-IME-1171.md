# #1171 focused field investigation

## Verified evidence

- Inspected the user's Sandium screenshot `155480.jpg`: focused field appears near the top while a separate quick-engine strip sits over the keyboard. Loaded-page screenshot `155478.jpg` shows the unified native toolbar at the bottom.
- Independently inspected actual #1171 APK DEX. Optimized controller `Lqzh.d` calls `Lr92.a(I Z Z Z Z Z Z)I`. The latter does **not** select TOP on omnibox focus: the target predicate is Find, eligible PiP, or top preference. Focus only remains in animation selection. The prior position patch is therefore present in the artifact, not merely its source.
- DEX also contains the native bottom-focus IME offset/max-height implementation. `EnableToolbarPositioningInResizeMode` has a true default in the APK feature initializer.
- User bugreport records main Sandium package `com.brave.browser_default` with `ADJUST_RESIZE` during URL editing. It does not establish the controller's live inset-observer mode, actual position preference, root/toolbar bounds, or final offset at the screenshot.
- Pinned Brave adapter intentionally passes false for NTP and Hub flags but forwards focus to Chromium. No additional forced-top focus branch was found there.
- The engine strip is a separate `TYPE_APPLICATION_PANEL` from `BraveActivity.quickSearchEnginesReady`, positioned at keyboard height. It does not reserve native toolbar layout space. A separate requested patch removes that strip; do not solve it by adding another floating URL input.

## Concrete lifecycle gap and bounded correction

Retaining bottom placement on focus exposes an upstream early-return assumption: `updateCurrentPosition` returns immediately when target position equals current position. Focus changes the native offset/max-height semantics, but the controller otherwise depends on a later keyboard-height/visibility event. Those events need not recur when an already-open keyboard transfers between page input and omnibox, or focus changes without a height change.

`apply-sandium-focus-follow.py` refreshes the existing native toolbar and progress-bar offsets when the position remains BOTTOM. It guards constructor-time supplier callbacks before the layer fields are initialized. It does not change preference, placement eligibility, IME arithmetic, window mode, viewport, focus, or native editing ownership.

This is a real lifecycle correction but is **not a proven explanation or fix for the photographed top placement**. Do not claim otherwise. The controller now emits two numeric-only trace events while tracing and focused: target/current position, preference/special-mode flags, and native offset/root/container/toolbar/visible-frame geometry. No URL, text, title, page pixels, or history is logged. These distinguish wrong logical placement from stale/double inset or enlarged-host geometry on the next actual device trace.

## Integration and validation

Apply after the reviewed unified address transform (and preserve the independent UrlBar ownership crash correction). Only ToolbarPositionController.java changes; it is already a production pinned-reset input. This branch contains no pipeline registration, build, push, or checkpoint changes.

Four source-contract tests pass: repeat application, initialization guard/dual-layer refresh, unchanged native offset arithmetic/preferences, and trace privacy/order checks. They do not compile Android or prove touch, layout, IME animation, hardware/floating keyboard, landscape, split-screen, or reduced-motion behavior.

Device acceptance: focus from a web page with keyboard closed, from an already-focused page form, from homepage; type long and short text; close/reopen keyboard; Back; top-preference fallback; landscape/multiwindow. Check actual field position, no keyboard overlap or screen jump, and acquire the two trace events if top placement persists. Keep native security/full URL editing intact.
