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
