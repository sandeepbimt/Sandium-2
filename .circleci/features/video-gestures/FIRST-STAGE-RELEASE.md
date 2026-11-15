# Achievable first stage: native controls inside existing site fullscreen

This is a **build/test candidate**, not a verified working player.

## User-visible flow

1. Open a video page and use the site's existing fullscreen button.
2. When Sandium can safely identify a single current video/session, show a small
   opt-in `Video gestures` control. Ineligible or ambiguous pages keep site UI.
3. Once enabled: horizontal gesture previews a relative seek, commits on release;
   left/right vertical gestures change window brightness/music volume; center
   tap toggles playback. Accessible buttons provide play/pause and +/-10 seconds,
   brightness and volume, and `Site controls` restores original controls.
4. Exit fullscreen, navigate/change tabs, pause activity or enter PiP: remove
   overlay, cancel gesture and restore window-only brightness. Do not restart
   playback or alter global brightness.

Playback/seek calls go to Chromium MediaSession (`resume`, `suspend`, `seekTo`),
not a mock player or substituted decoder. Seek is available only when the live
session exposes valid finite position and supported actions. This preserves
Chromium/site authority, but actual site-specific behavior is UNTESTED.

## Deliberately not included

No inline contextual pill, new fullscreen authorization, download, new PiP
entry, playlist, detached Media3 player, speed/lock/rotation/fit controls or
promise of arbitrary DRM/cross-origin/multi-video support. Native/DOM toolbar
candidates are not part of the first-stage installer at all. The installer
rejects previously injected experimental helper/GN registrations and requires
a clean pinned source checkpoint rather than pretend they are absent.

## Release gate

When the user finishes UI requirements and root coordinates one build, compile
this limited installer against pinned source (including the current removals).
Then verify on Android: actual playback pause/resume, actual seek position change
on two finite videos, live/nonseekable fallback, custom player/DRM unaffected,
source/tab/navigation/rotation interruptions, restoring brightness and accessible
controls. Test from a fresh page navigation: mid-document/BFCache ambiguous media
inventory is intentionally rejected. A successful APK compile alone is not proof.

If any of these tests cannot be performed, label it an experimental fullscreen
controls build and list the gaps. Do not call it the full Quetta-style player.
No build has been requested or triggered by this package.

## Latest theme and double-tap scope

Player controls resolve the shared native theme's colorAccent/colorBackground/
textColorPrimary. Fallbacks are light blue #6E8EB5 and near-AMOLED #080808, not
sand gold. They must be inflated under the application's actual themed activity.

No global double-tap interception is added. Web videos/custom-player overlays
already use double tap for seek, play or zoom, and native interception would
steal those gestures. Double-tap entry into the new inline/fullscreen player
would also require the unfinished native authorization/identity path; it cannot
be honestly advertised as part of this stage. Existing site fullscreen remains
the entry. Do not add a document-wide double-click listener or overlay as a
shortcut, and do not replace accessibility or browser zoom behavior.
