# Navigation loading trace follow-up

Pinned source matches the #1225 tree (`b5235d3`, local `efb9a4d`).
The video and trace are different repetitions of the same reported issue, not
frame-synchronized captures.

## Observed

The trace's homepage history navigation commits in about 168 ms. The animator
then remains in `kWaitingForContentForNavigationEntryShown` for about 1.636 s.
An Android Handler task appears about 1501.7 ms after entering that state,
followed by the animation completion. Pinned NTP code has a 1500 ms feed-restore
fallback and a 100 ms alpha fade, consistent with this interval.

Brave's NTP explicitly disables Chromium feed, while the inherited smooth
transition uses that feed's restoring-state supplier. The no-feed policy now
supplies `NO_STATE_TO_RESTORE` instead; enabled-feed pages retain the original
supplier. Fade and cancellation remain native. `SandiumNtpFeedWaitSkipped`
identifies the selected path.

The screenshot cache reason is 12 (`kCacheMissScreenshotOrientation`). This is
an exact size mismatch check, not proof of physical rotation. No unsafe
stretching/cropping of destination snapshots is added here.

## Ordinary navigation source

The original cross-site blur clones the WebContents surface only. A native NTP
covers that surface, so it is not a reliable representation of the visible home.
The source selector now requests the existing native-page synchronous capture
for non-web outgoing pages when the destination is HTTP(S) and not PDF. Native destinations
are not captured because they can replace their view before navigation commit.
Pinned Android `NavigationRequest::NeedsUrlLoader` explicitly identifies
`IsPdf()` as Java NativePage rendering, including HTTP-backed native PDFs. Captures must have matching dimensions; the native
capture's documented top-controls offset is applied without stretching.
HTTP(S) web pages keep the native surface path.

If no safe native pixels are available, this optional cover animation is not
created. Normal navigation still runs. This avoids presenting stale hidden
renderer pixels but cannot guarantee a blank-free native transition in that
failure case. Device testing must establish capture availability/timing.

The existing fallback colour policy is unchanged. No arbitrary bitmap pixel is
used as background. No user's blur level, hold or fade duration is changed.
`SandiumOrdinaryBlurSource` and `SandiumOrdinaryBlurBackground` expose the source
choice and backing colour for correlation. `SandiumOrdinaryBlurState` and
`SandiumOrdinaryBlurExit` identify hold/fade/teardown timing. `SandiumNativeBlurCapture` measures
the synchronous capture cost; excessive main-thread cost is a release blocker.

## Verification bounds

Pinned full C++/header transforms and idempotence are tested. Java policy harness
executes the exact production helper and verifies enabled-feed supplier identity
and disabled-feed no-state behavior. These are not Android rendering tests.
Device acceptance must cover native/web URLs, both toolbar positions, IME
open/closing, small viewport, canceled/chained Back gestures, native capture
failure, private mode and background/resume. Existing timers and cleanup paths
remain in force. No CI run is started by these changes.

## Synchronized second recording

Both native-home departures show flat RGB202 gray, while the web-to-web hop
shows actual blurred Google content. First contentful paint occurs before the
gray disappears. High 675/300 and Darken are enabled in the trace. A hidden white
renderer surface under the 20% black overlay predicts RGB204, close to the
recorded RGB202. This strengthens the source hypothesis but is not direct proof
of a particular compositor layer. Existing baseline lacks ordinary-blur state
trace markers. The candidate adds them for verification without changing timing.
