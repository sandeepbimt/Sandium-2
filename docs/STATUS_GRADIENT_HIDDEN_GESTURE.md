# Status gradient: hidden gesture-hint controller creation

## Evidence and scope

The #1173 screenshot shows an opaque status strip rather than content fading
under the status icons. The supplied Android bugreport reports a zero-height
navigation bar, no tappable navigation inset, and positive left/right system
gesture insets. These are consistent with gesture navigation with the gesture
hint hidden. Captured status paint diagnostics report status/top padding of 120
and protection of zero; the captures have no controller eligibility event.

At pinned Chromium d331de35ca8ab1358c7a17e4bd41627d55eaef51,
EdgeToEdgeControllerCreator requires BOTH positive gesture evidence and a
nonzero navigation-bar inset before creating the controller. Thus this device's
inset combination cannot instantiate the controller through this path. Changing
only the gradient colors cannot correct that prerequisite.

## Targeted correction

Allow the existing creator to initialize the controller on hidden-hint phones
when gesture evidence is positive, the Android-16 experiment and everywhere
feature are enabled, the activity is ChromeTabbedActivity, portrait phone,
outside multiwindow/PiP, with visible top status bars, supported top cutout and
no caption bar. Do not synthesize navigation insets or remove gesture evidence.
The original nonzero-navigation-bar path is unchanged.

Controller creation is NOT unconditional page underlap. All existing per-page
eligibility, incognito/native-page, keyboard, fullscreen, layout and security
fallbacks remain byte-for-byte unchanged. The existing fading protection keeps
status icons legible; unsupported cases retain their normal opaque safe area.

The new pinned source is included in the reset recipe so checkpoint replay
restores the original before applying the patch. Its original Chromium BSD
header is retained. No new library or external code is introduced.

## Verification and limitations

Source-contract tests cover both branches, guard retention, no fabricated
insets, idempotence and unchanged downstream transforms. Composition checks
must also exercise pinned reset/replay. These are not Android execution tests.

A fresh device run must verify actual gradient, readable icons, no content jump
on initial load/scroll, keyboard show/hide, rotation, tab switching, Settings,
incognito and fullscreen. Check the numeric SandiumHiddenGestureController
trace followed by SandiumStatusEligibility and nonzero protection geometry on
an eligible page. The targeted prerequisite fix does not prove the final
rendering or rule out a second device-specific issue.
