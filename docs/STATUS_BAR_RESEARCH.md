# Sandium Android 16 status-underlap trial

## Status
Experimental source patch, not release-validated. User explicitly requested a reversible visual trial. No CircleCI triggered by this work. No claim that a new APK has this feature yet.

Pinned Chromium `d331de35ca8ab1358c7a17e4bd41627d55eaef51`, Brave `44a84b1f89d9a35287289d6a3d493e362f5a5123`; source baseline #1082.

The first legacy-only scroll-triggered draft was rejected. This revision implements a stable web underlap without a scroll threshold, limited to Android 16's unified inset architecture and the user's evidenced top URL toolbar.

## Design

- Consistently selects Chromium's existing EdgelessTopInset provider architecture on Android 16 through one isolated gate. This is necessary so RootUiCoordinator, controller and toolbar agree on who owns the top inset.
- Normal HTTP(S) browsing gets top consumption. Existing TopInsetProvider tells the top toolbar to include the system inset; normal browser-control scrolling then moves that toolbar away. No manual second toolbar offset and no scroll-position mode toggle.
- The unified root keeps independent top protection geometry after consumed top insets reach it. A noninteractive dark gradient is painted AFTER children. The actual window bar is transparent with light icons.
- InsetObserver forwards top CSS safe-area with `max`, avoiding additive cutout double counting.
- Native pages, internal schemes/onboarding, incognito, non-tabbed activities, landscape/tablets, multiwindow/PiP, fullscreen, keyboard, forced controls, side/bottom cutouts, top cutouts taller than the status inset, caption bars, status indicators, crash state and non-browsing layout transitions keep ordinary web-inset behavior.
- All normal requested status colors remain stored; leaving the eligible surface restores the latest color. Destruction clears the custom inset/protection state.
- Bottom URL toolbar is deliberately outside this trial. The user's Hindu screenshots show TOP URL toolbar plus separate bottom navigation, not a bottom URL toolbar.
- No blur, frosted onboarding, theme color or filter-count changes are included here.

## Changed production classes

1. `EdgeToEdgeUtils`: Android16 trial gate and consistent architecture routing.
2. `EdgeToEdgeControllerImpl`: bounded web eligibility, lifecycle invalidation, top state/protection propagation and restoration.
3. `InsetObserver`: independently retained top safe area/protection geometry.
4. `EdgeToEdgeSystemBarColorHelper`: transparent status window + readable icons while retaining normal requested colors.
5. `EdgeToEdgeLayoutCoordinator`: passes retained top geometry without adding padding.
6. `EdgeToEdgeBaseLayout`: independent post-child gradient.

## Validation completed

`python -m unittest discover -s .circleci/tests -p test_status_underlap_patch.py -v`

Source-contract tests cover all nine pinned source transformations/idempotence, prepare-before-write failure on drift, scope guards, no scroll threshold, separate protection/padding, safe-area handling, Android16 gate and color restoration. Python compilation passed.

Six Android Robolectric tests are added to EXISTING test sources (no new GN target): independent protection despite zero top padding and restoration; negative protection-height clamp; restoration of latest requested status color after underlap; controller geometry policy rejects side/bottom/oversized cutouts and captions; web/control eligibility policy; actual controller activation followed by keyboard, cutout and URL restoration on an Android36 lightweight activity. These tests are AUTHORED, NOT EXECUTED: this workspace has neither javac/Android SDK nor the Chromium build environment. They must run in the native build environment. Passing Python tests is NOT evidence of Android compilation or functional rendering.

## Concrete remaining risks

- Activating the existing top architecture on Android16 also switches native-screen provider routing; even where web underlap is excluded, native screens need regression testing.
- Chromium explicitly leaves top-aligned overlay adjusters unfinished. Menus/dialogs, find-in-page and permission UI must be tested for camera/status overlap.
- SurfaceView/compositor layering must be tested to ensure the post-child gradient is visible above the rendered page.
- Toolbar layout, content viewport/safe-area and CSS fixed/sticky elements must be device-tested. OEM Android16 behavior is unverified.
- White-page icon contrast is protected by the gradient in this design but not yet visually verified on hardware.

## Trial acceptance

On actual Android16 Oppo device: initial URL controls below camera/time; scroll moves actual page pixels beneath status icons naturally; reverse scroll has no threshold jump; black/white/image pages readable; keyboard and omnibox restore correctly; top menus/permissions/find-in-page; tab switcher/NTP/onboarding/incognito; fullscreen video; rotation, side cutout and split screen; background/resume; crash recovery.

## Apply and rollback

Apply after upstream source patches, before Java compilation:
`python3 .circleci/scripts/apply-sandium-scroll-status-bar.py "$CHROMIUM_SRC"`

Trial-only rollback, also idempotent on restored checkpoint sources:
`python3 .circleci/scripts/apply-sandium-scroll-status-bar.py "$CHROMIUM_SRC" --disable`

`--disable` returns the architecture gate to stock behavior while keeping inert methods. Do NOT simply skip the script on an existing modified checkpoint: it could retain the enabled source. For full source removal use the generated patch reversed against matching source or reconstruct clean pinned sources. Ordinary upstream EdgelessTopInset behavior remains whatever upstream flag selects when the Sandium gate is disabled.

Review corrections: raw cutout and caption geometry retained independently of system-bar insets; 3-button-nav early bypass clears custom top state and notifies toolbar observers; inactive paths do not call mocked/unneeded color helper; exact URL/load callbacks re-evaluate internal-page/error transitions. Native tests remain unexecuted locally.

## November 15 follow-up: solid status strip on #1169 family

Evidence inspected: user's 155441.jpg shows a hard black strip above an HTTP(S)
article, not a visible fade. The earlier back-navigation trace metadata reports
Android SDK 37, so it is incorrect to assume that device is excluded by `>=36`.
The screenshot itself does not establish its OS, flags, forced-controls state,
root inset ownership, or whether the screenshot was captured on #1169.

Source findings:
* The existing gradient is already post-child, transparent at 1.5× the status
  inset. The opaque status rectangle should have zero height when top insets are
  consumed. Merely changing its color does not repair an inactive underlap path.
* Eligibility requires unified root inset ownership plus supported activity,
  page, controls, layout, cutouts, keyboard, and window configuration.
* The existing listener responds to offsets/heights/position but did not respond
  to Android controls visibility or offset-tag constraint changes. The pinned
  BrowserControlsStateProvider documents these as distinct notifications, not
  synonymous with offsets. The new callbacks recheck the **same** guards when
  constraints change without movement. They do not force acceptance.
* Added trace-only `SandiumStatusEligibility` (booleans and numeric geometry) and
  `SandiumStatusPaintGeometry` (protection/status/padding heights) distinguish an
  eligibility refusal, unconsumed inset, missing protection, and compositor
  rendering failure. No URLs, titles, page pixels or history are recorded.

No eligibility restriction, alpha, gradient curve, inset dimensions, animation
or safe-area behavior is changed. Android 14/15, landscape, keyboard, fullscreen,
native screens and unsupported cutouts keep their prior behavior. Do not call
this a proven visual fix. The missing screenshot-linked runtime state prevents
identifying the exact refusal or layer from existing evidence.

Validation: Python transformation/migration/source-contract tests, including
#1169 checkpoint migration and repeated back-geometry instrumentation composition.
Native compilation, Robolectric execution, OEM SurfaceView compositing and device
visual checks remain outstanding. Capture a trace while reproducing the strip:
`active=false` plus eligibility fields identifies the guard; `active=true` with
`protection>0,status=0,padding=0` but a solid strip points to another compositor/
window layer rather than permission to remove safety gates. Verify white/image
pages retain readable icons, then keyboard, back navigation, rotation, fullscreen,
tabs and Settings. Reject a change that introduces page position jumps.

## November 16: stable bottom-toolbar inset ownership

The APK recordings show a whole-page down/up jump on menu opening and an inverse
jump on dismissal, while the bottom toolbar remains anchored. They also show a
white-backed gradient over dark article content after scrolling. These are
observations, not proof that every website content shift shares one cause.

The prior underlap predicate rejected all forced controls and every nonzero top
minimum. With a bottom toolbar, the only top layer can be Sandium's own spacer.
Menu/navigation controls locks are transient, and disabling top-control scrolling
can pin that spacer. Rejecting its own state exchanges native spacer ownership
for root padding, potentially while controls/insets callbacks are in progress.

The new predicate keeps bottom-toolbar underlap eligible across those locks only
when the aggregate top height is precisely the explicitly owned spacer height
and minimum height/offset do not exceed that ownership. Real extra top controls
still reject underlap. Top-toolbar, native/error/incognito pages, IME, fullscreen,
layout transitions, cutout and window-configuration exclusions are unchanged.
The spacer and initial header clearance stay present; no DOM mutation, scroll
compensation, per-frame Android translation, or opaque masking is introduced.

The gradient and physical/CSS safe-area metadata are deliberately unchanged.
An initially considered removal of the synthetic CSS safe-area top was rejected
in review: it could regress author fixed/sticky headers, and metadata does not
prove automatic page padding. Trace-only eligibility output now includes owned
spacer, actual top minimum, top offset and content offset so residual white-strip
coverage can be separated from root inset changes on-device.

Validation: 21 pinned source/migration/idempotence tests pass, including migration
from the exact header-safe #1209 script and repeated back-trace composition.
The generated Android test now cycles forced-controls true/false while the owned
spacer is pinned/unpinned, checks root top-inset consumption stays unchanged,
rejects extra top geometry, and then exercises keyboard restoration. It is
AUTHORED, NOT EXECUTED locally; no Android SDK/compiler is present.

This fixes a specific eligibility defect and is a candidate for the observed
menu/navigation instability and status coverage failure. It is not yet proof of
visual resolution on the Oppo device. Test menu open/close repeatedly at origin
and mid-scroll, forward/back, slow loading, top/hidden/revealed controls, white and
image pages, keyboard, tabs, rotation and fullscreen. Website-controlled late
image/ad/font layout changes are not disabled or force-corrected; the recording's
independent Hindu hero shift remains a separate investigation.
