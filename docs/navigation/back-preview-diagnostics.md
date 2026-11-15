# Destination-aware back preview: experimental, not a verified flash fix

## Basis
Trace `Blue Flash Trace Sandium-2026-11-15-015439.pftrace.gz`, SHA256
`e1336b6f0098c5edd2e37347010520ed800b990dd122f8f95a3ce2ad6dded273`.
Two back transitions restored the Google destination via BFCache in 37.507 ms
and 33.529 ms. Their visual transition spans were 429.10 ms and 378.77 ms.
This is not evidence that a reload caused the flash. No pixels, fallback color,
or cache miss reason were captured, so the source of blue remains unproved.
Slight horizontal movement is part of upstream's gesture animation. A vertical
screenshot/live mismatch could relate to underlap/insets, but the trace did not
capture the inset/root scroll values needed to establish that cause.

## Pinned applicability
Chromium `d331de35ca8ab1358c7a17e4bd41627d55eaef51`
Brave Core `44a84b1f89d9a35287289d6a3d493e362f5a5123`.
The overlay validates both Git HEADs and every exact source anchor before any
writes. It is idempotent and refuses duplicate old anchors beside applied text.
Fixtures are unmodified files from the Chromium commit above, retrieved from
`https://raw.githubusercontent.com/chromium/chromium/<commit>/<path>`; upstream
copyright/license notices are retained.

## Narrow behavior change
Before leaving a primary normal HTTP(S) page, capture its reported document
background from `current_rfh->GetPage().background_color()`. Require the frame
to be live and its committed URL to match the history entry. Store only opaque
colors, session-locally in NavigationTransitionData; no new disk/profile data,
URLs or screenshots are persisted. Unknown/transparent values are cleared.
Both cross-document and same-document capture entry points use the helper,
including when screenshot capture subsequently gets skipped.

Only when upstream chooses a missing/invalid screenshot fallback, use the
*destination entry's* remembered color, never the outgoing site's color. Valid
bitmap/texture previews remain exactly upstream. If the color is unavailable,
use neutral #121212 in night/incognito context, #FAFAFA otherwise, rather than
a potentially tinted dynamic-color surface. A genuinely blue document may
legitimately produce a blue fallback. HTML theme-color is deliberately not used:
it describes browser chrome, not necessarily the page background.

The background is a solid approximation, not a screenshot; gradients, images,
scroll-dependent colors and later page-theme changes cannot be reconstructed.
Restored sessions start without the session-only remembered color. Incognito
colors stay within the same navigation entry lifetime and are not serialized.

## Diagnostics
Under `navigation` tracing:
- `SandiumBackPreviewSelection`: fallback bool and upstream cache reason enum.
- `SandiumBackFallbackColor`: destination-color availability and resolved ARGB.
- `SandiumBackPreviewBounds`: physical preview width/height.
- `SandiumBackHandoffState`: state enum and physical size at state processing.

No navigation URL, page text or image pixels are added to trace. Pair a fresh
trace with screen recording to determine whether the visible flash is fallback,
a valid screenshot or live-renderer handoff. These events alone cannot prove
root scroll/inset mismatch; add narrowly targeted geometry instrumentation if
that persists. Do not alter inset guards merely on suspicion.

## Integration and safeguards
Active Full product-overlay-26 invokes this after the existing page transition
overlay; flow wiring validation includes it. No change to screenshot eligibility,
BFCache capacity/admission, ready-frame checks, transition duration, darken/blur
preferences, top insets or existing native/error/fullscreen safety guards. No CI
was started by this work. Settings crash fixes remain in the branch ancestry.

## Validation and limits
Six local pinned-source transformation tests pass, including repeat application,
unknown-source rejection before writes, duplicate-anchor rejection, both capture
paths, and preservation of complete valid-screenshot/gesture functions.
`test-brave-build-flow.py` passes. Independent source review corrected use of
Android view default background to actual PageImpl document background.
These are NOT a Chromium compile or Android device test. Compile the exact
candidate once approved, then test back via gesture and button, BFCache hits
and misses, same-document history, light/dark, dynamic palette, incognito,
rotation, native/error destinations, keyboard and reduced motion. Confirm
scroll position/vertical stability on device. Do not claim the flash or settling
is fixed until the affected path is reproduced and tested in the new APK.
