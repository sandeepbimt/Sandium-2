# #1171 direct URL navigation crash: targeted correction

## Evidence

User-tested #1171 / commit a4cd546. Latest device bugreport created 2026-11-15
14:09:35 India time contains repeated main-thread crashes at 13:49:43,
13:52:41 and 14:09:22 local:

```
java.lang.AssertionError
  at jx8.C(...:3)
  at org.chromium.chrome.browser.omnibox.UrlBarApi26.layout(...:40)
  at androidx.constraintlayout.widget.ConstraintLayout.onLayout(...:61)
  at org.chromium.chrome.browser.omnibox.LocationBarPhone.onLayout(...:8)
```

Actual #1171 APK DEX inspection confirms `jx8.C` constructs/throws AssertionError.
The call in UrlBarApi26.layout follows the native scrollDisplayText/layout checks.
This is not the previous onboarding manifest or Settings null-preference crash.
The native UrlBar.layout invariant disallows scrollDisplayText from requesting
another layout (apart from the explicitly allowed bounds-ellipsis path).

## Correction

The unified address overlay enabled experimental LocationBarPhone centering.
That implementation also changed editable UrlBar text alignment/gravity,
horizontal scrolling and scrollX from parent measurement. Those changes compete
with UrlBar's own text direction, multiline focus behavior and TLD visibility.

Center the measured view with the existing packed constraint chain, but remove
all those parent text-behavior mutations. Native UrlBar remains responsible for
input wrapping, selection, BiDi alignment and scroll restoration. The layout
assertion remains intact: no suppression/catch, no loss of security formatting,
and no custom URL navigation path. Long URLs retain constrained width and native
origin visibility. Upgrading an already V1-applied source is idempotent.

The exact setter that caused the observed additional layout has not been
instrumented on Android. The call site is proven, and this is a bounded ownership
correction, not a claim of runtime-confirmed root-cause resolution.

## Verification

- 8 unified-address source contract tests pass, including V1 upgrade/idempotence.
- Full pinned source composition, reset/replay, interruption recovery and bad-patch
  preflight pass with UI, home shortcuts, fullscreen controls and removal overlays.
- Independent source review found no new static blocker.
- No CI run, Android compilation or device reproduction performed for this patch.

Required device cases: direct URL submit from home and loaded page; repeat focus,
submit, cancel and Back; long domain/path; IDN/BiDi; empty text; landscape and
large font. Confirm no crash and correct selection/URL identity after focus loss.
