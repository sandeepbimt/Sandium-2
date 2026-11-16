# Android element color chooser (not enabled)

Browser-owned Shield entry and chooser source. This folder is not invoked by the
production pipeline. It requires the independently reviewed native/renderer
corrector session/transport/store implementation; it cannot work by itself.

JNI class: `org.chromium.chrome.browser.sandium.dark.SandiumElementColorsUtils`,
namespace `sandium`. Native interface: start(Tab,long requestId)->boolean,
preview(Tab,long,int property,int rgb)->boolean, save(Tab,long,int,int),
cancel(Tab,long), resetSite(Tab,long). Property0 is foreground,1 background;
RGB is bounded opaque0..0xffffff. No selectors, URLs or page strings cross Java.
Callbacks onSelection(Tab,long), onSaveResult(Tab,long,int), onSessionEnded(Tab,long).
Save results:0 saved,1 applied this visit only,2 rejected. Native sends the Save
result before the session-ended callback. Cancel removes preview/picker state,
never an already committed override.

A browser-generated positive request ID rejects callbacks from older sessions in
the same Tab. Native also authenticates its independent document/session token.
Java retains the initiating Activity+Tab+WebContents, cancels on navigation,
Activity stop/destroy and WebContents destruction, and cleans observers/dialogs
before notifying native to survive synchronous reentrant callbacks. Waiting
selection times out after60s; Save has a7s fallback beyond native's5s deadline.

The chooser offers text/background, bounded#RRGGBB input, four presets, explicit
Preview/Save/Cancel and a confirmation for Reset site corrections. Save disables
repeat submissions while awaiting native acknowledgment. No implicit Save or
CAPTCHA interaction occurs. Shield popup is hidden before selection starts.

`tests/run.sh` compiles actual chooser Java with Android/JNI stubs and checks17
lifecycle/typed-command assertions. This does not test real Android rendering,
Mojo/JNI compilation, keyed node overrides, persistent matching or device UI.
The existing Java+renderer composition test also replays this source transform;
all remain disabled pending complete-source/native review and build validation.

### #1193 pinned Java API and listener scope correction
Chromium d331de35ca8ab1358c7a17e4bd41627d55eaef51 WebContentsObserver
exposes final `observe(WebContents)` and documents null as detach; it has no
`destroy()` method. Close now clears the observer field before `observe(null)`.
The test double no longer invents destroy and verifies observer registration
and removal during navigation, replacement and teardown.

The Shield listener now uses `correctionContext`, avoiding setupViews' existing
`Context context` local. The transform migrates only its exact prior listener
block. The Java test runner compiles the actual injected listener with a matching
outer context local, alongside the chooser lifecycle assertions. These are local
Java/stub checks, not a full Chromium Android build.
