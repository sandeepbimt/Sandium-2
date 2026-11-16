# Native status candidate: disabled, not shipping

`patch.py` is an unwired candidate. Its shared static gate is false. Python tests
are source-contract checks, not Android compilation, rendering or runtime proof.

## Upstream ownership used

Pinned Chromium `d331de35` and Brave `44a84b1`:
- NativePage supportsEdgeToEdgeOnTop is the native top opt-in.
- NewTabPageCoordinator keeps foreground safe via TOP_INSET_PX only when the
  parent consumes the system inset. Its callback and foreground geometry remain.
- Brave ASM disables Chromium NTP customization, so the candidate registers its
  own TopInsetProvider observer and unregisters before destroy.
- Brave ASM makes NewTabPageLayout a FrameLayout. Wallpaper is a direct child.
- Existing wallpaper worker/focal-point crop is retained. During underlap it
  targets root dimensions; root draw keeps the exact image matrix, drawable
  bounds, filter/alpha and view alpha. It does not crop a second time, read pixels,
  copy bitmaps, create another worker or resize the foreground.

## Painting and tint

The native controller uses the same predicate for pending and realized NTP.
The existing system-bar helper owns transparent backing, readable light icons
and restoration. Original requested colours remain stored.

Unified root: separate paint-only height metadata notifies a lifecycle-bound
observer immediately, so exit/destruction cannot leave stale protection. The
existing root gradient renderer draws once. No CSS-safe-area update, spacer
mutation or inset redispatch is introduced.

Legacy root (API15 path): preserve the upstream legacy padding owner and its
native top-padding calculation. Top-only native underlap also sets the existing
content-fits-window signal, including a hidden gesture hint. A non-interactive
decor overlay paints status protection; pending/not-visible NTP gets its native
screen backing rather than an unrelated white window. It is removed on exit,
bypass or destruction. This path needs actual OS compositing verification.

## API15 narrowing

The earlier global EdgeToEdgeEverywhere override was rejected and REMOVED.
Its implementation remains byte-for-byte unchanged. Only the existing native
EdgelessTopInset feature path is selected; legacy root ownership is preserved.
Manufacturer and automotive opt-outs are retained. The separate web-underlap
experiment remains SDK36-only. Native eligibility remains regular NTP in the
tabbed window, portrait phone, gesture navigation, supported cutout, no keyboard,
fullscreen or non-browsing transition. Unsupported surfaces keep stock layout
and contrast, not an unverified gradient.

This still changes native top-provider routing while enabled. Test web,
incognito, CustomTab, Settings, tablet/landscape, three-button and keyboard
transitions before activation; narrow native eligibility alone is not proof of
unchanged geometry on every other surface.

## Checkpoint order

Reverse exact native additions with `undo_chromium` BEFORE replaying the shipping
status transform, then apply `chromium`. Tests prove round-trip/repeat composition
for all affected Chromium files. No production pipeline invokes this yet.

## Outstanding

- Actual Java/native compile, lint/nullness and APK rendering.
- Native ancestors/clipping, cold pending first frame, cached return, fade/cancel,
  reload and image replacement, rotation/keyboard/window lifecycle.
- Legacy decor overlay above real Android SurfaceView/Window surfaces and its
  exact system-icon bounds/contrast; no flash claim until captured.
- Full all-screen compatibility. Settings has a separate source candidate;
  tablet/automotive Settings retain stock contrast because they have a direct
  icon-tint writer. Other native screens are not declared complete.

Settings API15 candidate uses a status-only decor overlay. The rejected root
wrapping approach created competing bottom/IME owners and has been removed.
The existing Brave root/recycler/nav/IME inset handler remains the sole owner;
its existing callback only updates paint metadata. No additional root wrapper,
coordinator, inset listener or padding writes are introduced. Only colour-helper
capabilities opt in, allowing transparency without a delegate. Matching header
backing and the gradient are drawn before requesting light icons; cleanup removes
the overlay and restores ordinary colour contrast. Tablet/automotive keep stock
ownership. This still needs OS rendering, light/night, IME and lifecycle tests.

A one-shot pre-draw hook is registered before superclass creation to paint using
actual root insets before the first content frame, without waiting for the later
Brave content listener. It removes itself once insets exist and is also cleaned
up on destroy. This is not proof about the OS splash/starting-window frame or
dialog-window compositing; those still require capture on Android.

## Explicit test-only preparation

`prepare.py --src /path/to/chromium/src --core /path/to/brave/core` validates the
complete composed source set and prints final hashes without writing. It expects
normal theme/fade/news overlays already applied. Add `--test-only-enable --write`
only on a separate test branch/workspace after review to generate an enabled test
APK. No normal CI invokes this tool. It prepares every change before writing,
reverses native Chromium changes before shipping status replay, normalizes the
test gate, and supports repeated checkpoints. `test_prepare.py` covers enabled
replay, disabling and fail-before-write. This is source preparation, not evidence
of Java compilation or Android correctness; parent coordinates any actual build.

## Native screen coverage audit (not a completion claim)

- Regular NTP: candidate wallpaper/foreground split and legacy/unified gradient.
- Settings/sub-settings: shared activity candidate, status-only legacy overlay;
  newer owner uses the production painter. Tablet/automotive excluded.
- Welcome: `SandiumWelcomeSetupView.createView` directly sets a solid status bar
  and clears all system UI visibility flags. It is a distinct owner and is NOT
  fixed by the Settings/NTP candidate. A safe change needs the first-run activity
  inset and lifecycle owner, not a global native-screen assumption.
- Bookmarks: BraveBookmarkActivity extends Chromium BookmarkActivity, which owns
  its own coordinator/lifecycle. No candidate coverage established.
- History/downloads/tab switcher/incognito and other native browser screens:
  no universal extension justified yet. Need pinned owner/layout inventory and
  Android render tests. Full native-screen requirement is still open.

Additional pinned owner evidence (Chromium `d331de35ca8ab1358c7a17e4bd41627d55eaef51`):

- `chrome/android/java/src/org/chromium/chrome/browser/app/bookmarks/BookmarkActivity.java`
  observes ScrimManager status colour and composites it over semantic background
  before passing the result to StatusBarColorController. Any future protection
  must preserve that ownership, bottom-sheet scrim and tablet BookmarkPage split.
- `chrome/android/java/src/org/chromium/chrome/browser/history/HistoryActivity.java`
  creates a sibling bottom-sheet container and E2E pad-adjuster per view.
- Both extend SnackbarActivity → SynchronousInitializationActivity →
  ChromeBaseAppCompatActivity. The base's shouldDraw/wrap/canColor hooks default
  to global Everywhere. Therefore simply opting in colour without matching
  pre-existing layout ownership is insufficient on Android15, and wrapping all
  screens recreates the class of Settings double-inset regression rejected above.
- `chrome/android/java/src/org/chromium/chrome/browser/signin/FullscreenSigninAndHistorySyncActivityBase.java`
  confirms first-run AsyncInitializationActivity ancestry and an automotive
  status-colour override during layout inflation. Do not override globally.

The three concrete leaf/base sources are retained in fixtures for owner audits.
No patches are applied to them by test-only preparation yet.

## Overnight follow-up: separate unverified screen gate

The candidate can additionally recognize Bookmarks, History and Welcome **only
when an existing unified EdgeToEdgeBaseLayout already owns those screens**.
This does not provide their Android15 legacy owner, and is not all-screen support.
`--test-only-enable` deliberately leaves this separate gate off.
`--test-only-native-screens` requires `--test-only-enable` and explicitly opts
into that unverified paint-only branch. Both gates normalize/replay independently.
Bookmarks scrim and dialogs still need OS rendering validation before use.

The separate Welcome production change matches its window backing to the black
screen and changes only icon appearance bits, preserving existing layout flags.
It prevents relying solely on a status colour call that Android15 can ignore;
it does **not** implement wallpaper underlap or demonstrate gradual transparency.

Pinned build audit found a real candidate dependency gap: EdgeToEdgeControllerImpl
now calls ChromeSemanticColorUtils, but its internal android_library did not list
`//chrome/browser/ui/android/theme:java`. Test preparation now patches only that
implementation target, validates its pinned shape and replays idempotently. The
source pin is d331de35ca8ab1358c7a17e4bd41627d55eaef51; the upstream BUILD fixture is
retained with its original BSD notice. This is a build-graph fix, not proof that
GN/Javac or device rendering has passed.

## Explicit secondary-owner implementation (still test-only)

`secondary.py` now supplies actual per-activity owner hooks for Bookmarks, History
and Welcome, not only class-name paint recognition. It reuses upstream
ChromeBaseAppCompatActivity's one shared EdgeToEdgeLayoutCoordinator and wrapper:
create that coordinator at the existing helper-supplier initialization point,
then let the superclass publish it before EdgeToEdgeManager initialization.
The pinned base initializes InsetObserver first. Merely creating the wrapper in
setContentView would be too late to populate the helper supplier, so that unsafe
shortcut is not used. No global Everywhere feature is changed.

Bookmarks retains its original scrim callback and color composition byte-for-byte.
History observes its actual ScrimManager status-color supplier, composes the scrim
with its semantic backing, forwards through the existing color helper, and
removes that observation before destruction. Existing bottom-sheet controllers,
view hierarchy, pad adjusters and bottom insets are unchanged. Welcome's pinned
FirstRun -> FullscreenSignin -> AsyncInitialization -> ChromeBase chain has no
separate wrapper/manual inset hook; the same owner is opt-in there and its backing
is explicitly black. The safe Welcome view change preserves existing UI flags.

All three stay disabled unless BOTH test gates are explicitly enabled. Settings
continues using its separate paint-only solution, never this wrapper because it
owns bottom/IME padding itself. Tablets/automotive retain existing behavior.
Source composition/reversal/owner checks pass, but these hooks need actual APK
compilation and Android15 rendering/scrim/IME tests before production use. Earlier
coverage audit notes describe the pre-implementation gaps, not verified outcomes.

Pinned ancestor and leaf fixtures retain upstream copyright/license headers.
Chromium source URLs use the d331de35ca8ab1358c7a17e4bd41627d55eaef51 pin;
WelcomeOnboardingActivity is from Brave core44a84b1f89d9a35287289d6a3d493e362f5a5123.
