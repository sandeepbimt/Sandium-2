# Welcome reference refinement after #1177

The owner's new Oppo Settings screenshot keeps black and #1A1A1A grouped
surfaces, already present in #1177, but uses colored category icons. Its flat
icon regions supply green #02BE12, amber #FDB200 and orange #FF7701; JPEG edges
are not treated as exact design tokens. Existing blue remains #198CFF.

Welcome now uses green for blocking, amber for Night Mode, orange for darken
transition/third-party cookies and blue for blur/fingerprinting. This mapping
is a Sandium design choice inspired by the reference, not an asserted Oppo
mapping. Icons are decorative: native readiness success, disabled and checked
states keep their existing independent semantics. Toggles remain white-thumb/
blue-track. Existing glyphs, dimensions, actions, loading gate and preferences
are untouched, as are the logo and any Shields animation.

Settings-row dividers start at the text column, leaving the colored icon
column continuous as in the reference. RTL uses start/end margins. The blur
picker's separate full-width dividers remain unchanged. Heading, spacing,
scrolling and minimum targets are deliberately not redesigned in this task.

Validation: welcome regression, native theme contrast and toggle tests pass;
source-only checks do not prove device appearance or native build success.

## Profile-card header follow-up
The subsequent Oppo profile-card reference is adapted as an informational header:
exact existing `sandium_toolbar_mark` artwork, untinted/uncropped and aspect-fit,
in a 56dp circular charcoal holder; title **Sandium**; supporting line **Choose
your browsing preferences.** No account/action chevron is added because the card
does not perform an account action. Text wraps at large font scales; the logo
is decorative for accessibility and the title is marked as a heading. Native
setup controls and readiness gating remain unchanged. The existing branded
resource and its packaging are reused, with no new image generation or assets.
