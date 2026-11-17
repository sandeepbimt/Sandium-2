# Toolbar capture coherence

Pinned Chromium: `d331de35ca8ab1358c7a17e4bd41627d55eaef51`.

## Proven source omissions

Sandium repurposes the Home slot as Forward. Its native Android view updates
`enabled` and `imageAlpha`, but Chromium's original PhoneCaptureStateToken compares
Home tint and visibility only. When other properties are unchanged, an
invalidated toolbar can be classified SNAPSHOT_SAME and its dirty rectangle
cleared. The new immutable fields represent actual painted state; differences use
the existing HOME_BUTTON classification. The original constructor remains valid
with the original enabled/opaque defaults. URL comparison remains unchanged.

The upstream hidden-capture pre-draw path checks top-control hidden ratio.
Sandium's bottom toolbar has a nonzero separate top spacer, so top visibility
need not represent toolbar visibility. The existing position-aware
BrowserControlsStateProvider.getBrowserControlHiddenRatio selects top/bottom.
Use that API without enabling the feature or bypassing focus, constraints,
fullscreen, animation, in-motion or snapshot-difference suppression.

## Primary references

- [PhoneCaptureStateToken](https://github.com/chromium/chromium/blob/d331de35ca8ab1358c7a17e4bd41627d55eaef51/chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/top/PhoneCaptureStateToken.java)
- [ToolbarPhone capture readiness and token generation](https://github.com/chromium/chromium/blob/d331de35ca8ab1358c7a17e4bd41627d55eaef51/chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/top/ToolbarPhone.java)
- [ToolbarControlContainer capture suppression and hidden capture](https://github.com/chromium/chromium/blob/d331de35ca8ab1358c7a17e4bd41627d55eaef51/chrome/browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/top/ToolbarControlContainer.java)
- [BrowserControlsManager position-aware hidden ratio](https://github.com/chromium/chromium/blob/d331de35ca8ab1358c7a17e4bd41627d55eaef51/chrome/android/java/src/org/chromium/chrome/browser/fullscreen/BrowserControlsManager.java)

## Evidence limits and integration

Observed device screenshots show restored Wikipedia content with old URL/Forward
state that later updates. That is consistent with stale toolbar capture, but the
installed APK commit and live-versus-texture provenance were not established.
These changes fix demonstrated source omissions; they do not establish the root
cause of the device episode, eliminate all URL delays, or fix page white flashes.
No additional capture request or arbitrary delay is introduced.

Five tests cover atomic plan failure, idempotence, untouched native suppression,
actual shipping bottom/unified/refinement/homepage composition, and compilation/execution of the actual transformed full token class and hidden
predicate with lightweight Java collaborators. These are not Android UI tests.

Integrator must add PhoneCaptureStateToken.java to pinned Chromium restore inputs,
apply this script after normal toolbar overlays, verify readback, include it in
reset/partial-failure composition, and run canonical regressions. No build or
workflow is started by this script. Full Android build/device validation remains
required.
