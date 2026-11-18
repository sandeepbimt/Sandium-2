# Native reveal probe

Reference: Chromium d331de35ca8ab1358c7a17e4bd41627d55eaef51
`NewTabPage.enableSmoothTransition()` and alpha-only NtpSmoothTransitionDelegate.
No capture offset, wallpaper, margin, alpha, animation duration, or navigation
policy is changed. Outside recording, the original delegate is returned.

An inverse observer on existing NewTabPage is installed by the existing
SandiumDiagnosticsCapture UI bootstrap. NewTabPage does not import the recorder
or Brave code. It and the existing UI source are part of the Chrome Android
Java compilation; no new Java source set or dependency edge is introduced.
NewTabPage is already owned by removal-recipe.json Chromium reset inventory and
its Chromium patch map. Diagnostic composition includes it atomically via the
producer PATH, after homepage backing and existing back-controls transforms.

At native delegate.start, sample at most 16 already-scheduled pre-draw callbacks
within 500ms. Fifteen draws may be sampled before completion; the final slot is
reserved for the first existing post-completion draw. A monotonic 500ms deadline
stops normal samples even if the main queue delays timeout delivery; timeout
cleanup runs when that queue can execute it. No draw/layout is requested.
Cleanup follows next post-reveal pre-draw,
cancel, detach, timeout, invalid/replaced recording epoch or failed
sink. Native completion callback is always invoked once as before. Samples
immediately before and after that callback distinguish screenshot teardown from
subsequent native layout. If no subsequent pre-draw occurs, timeout ends capture;
absence is not a successful visual match.

Events 28 NATIVE_REVEAL_VIEW (16 fields) and 29 NATIVE_REVEAL_CONTROLS (10 fields)
are Java-only. nav=0 deliberately: sample IDs pair rows inside the process but
are not a fabricated navigation link. Java receive clock is recorded with native
source clock=-1. Sink accepts only original active epoch and real regular profile.
No URL, title, content, persistent ID or pixel data.

Stages: 0 armed before native fade,1 start,2 pre-draw,3 before native end callback,
4 cancelled/replaced,5 timeout,6 detached,7 reserved,8 after end callback,
9 first available post-end pre-draw completed. View kind 0 is outer native root,
kind 1 foreground (same view when no wallpaper wrapper). Detached coordinates
are zero with attached=0 and must not be treated as screen coordinates.
Controls values are actual provider values, not inferred top/bottom offsets.

Limits: no compositor-present timestamp, matrix/pivot/scale or full window/layer
ancestry. Window positions+translation+margins narrow the native layout issue but
do not alone prove composed screenshot/live pixel equality. Recording incurs
existing bounded journal overhead, so this is not a zero-overhead performance test.
Host collaborator compilation/tests do not replace an Android compile/device test.
