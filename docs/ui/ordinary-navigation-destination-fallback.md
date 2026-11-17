# Ordinary navigation fallback follows destination policy

## Evidence and narrow defect

In the supplied phone recording, the Google → UN News transition has a blurred
outgoing page followed by a white content region (including the inspected 2.0s
frame). The recorded interval is approximately 1.77–10.70s. This is consistent
with the ordinary Chromium transition's fallback phase, but a recording alone
does not distinguish the fallback layer from an unpainted renderer surface.

Pinned Chromium d331de35ca8ab1358c7a17e4bd41627d55eaef51 creates the fallback
at `BlurTransitionAnimationManager::ReadyToCommitNavigation`. The existing
Sandium extension selected black only from the process-global force-dark flag,
otherwise borrowing the outgoing WebContents theme color. Sandium's actual page
darkness is document-bound/per-site, so that selector can incorrectly choose
white for a destination whose dark mode is explicitly ON.

## Change

The fallback now uses the existing browser-authorized
`GetSandiumDarkPageFlagsForNavigation(web_contents, final_url)` at ReadyToCommit:

- Managed ON: black, using the previous force-dark fallback color.
- Managed OFF: white. Do not copy a dark outgoing site's theme or global flag.
- Unmanaged: preserve existing global-feature/theme behavior.
- Error, PDF, view-source, non-HTTP(S), missing or opaque commit origin: do not
  request a managed policy; keep existing behavior.

This is a neutral dark/light transition backing, not a claim to predict the
unpainted destination's precise CSS background color. The final URL is used
after redirect resolution. No outgoing WebPreferences are changed. The existing
first-visually-nonempty-paint, cancellation, interruption and cleanup behavior,
user blur strength/durations, and native/back-forward eligibility remain intact.
No arbitrary additional delay is introduced.

## Validation and limits

Tests compile and execute the exact transformed selector against interface stubs
for ON/OFF/unmanaged × global flag × outgoing theme plus excluded destinations.
They verify source checkpoint migration, reapplication, and unchanged lifecycle
methods. Existing composed native-blur and page-transition tests pass.

This is not a full Chromium compilation or device trace proving which surface
owned the white interval. Device verification must repeat opposite per-site dark
rules, redirects, cancelled/error loads, slow network, native/PDF destinations,
and confirm no white transition backing for a managed-dark destination. A site's
own late white paint or premature first-paint signal is a separate readiness
issue, not hidden by this patch.
