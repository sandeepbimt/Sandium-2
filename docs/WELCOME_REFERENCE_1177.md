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

## 16 November welcome refinement
Default content has reduced padding and concise summaries, with the primary action
still outside the content scroller. Expanded More options can scroll without a
visible scrollbar; collapse resets to the top. Large accessibility fonts or small
landscape windows retain overflow access instead of clipping controls. Fit on the
owner's actual phone remains a device-validation item.

Readiness/download progress and successful checkmarks use green #46C878; native
readiness gates are unchanged. The logo reuses an exact copy of the toolbar's
balanced silhouette tracer, with a regression equality check, reduced-motion and
visibility lifecycle handling. The existing logo asset is unchanged.

Dark pages is a live profile policy, not intrinsically restart-dependent. Its hint
truthfully says “Applied with setup restart”; startup-only transition preferences
still use setup's restart. Start browsing exposes a separate green one-second
pre-restart bar, explicitly labelled as restart feedback, not additional download
progress. A lifecycle-owned handler dispatches restart independently of animation
settings and is cancelled when the welcome view is destroyed.

## 16 November available-space correction after device feedback
The owner's installed build showed a large empty region below More options.
The default main-settings card now uses fill-viewport surplus, distributing it
between complete vertically centered setting groups. Each group keeps its title,
summary and restart hint together. Natural WRAP_CONTENT minimum measurement is
preserved; no text scaling or fixed screen-height assumption is introduced.
Expanding More options removes these weights and uses natural scrollable height;
collapsing restores viewport fill and scroll-to-top. Logo/progress/button behavior,
font sizes and the large-font overflow fallback are unchanged. Actual device
layout remains a required follow-up check.

## Dark Pages hint removal after #1225
Per owner request, Dark Pages now uses the ordinary switch-row presentation
without a restart hint. Startup-only transition rows retain their restart notices.
The existing available-space distribution absorbs the removed line; no blank
placeholder is retained. Dark-page policy, startup restart and all other controls
are unchanged. Both fresh composition and an already-composed Dark Pages row
upgrade to the no-hint presentation.
