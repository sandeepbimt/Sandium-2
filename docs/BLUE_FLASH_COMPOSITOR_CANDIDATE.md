# Back-navigation blue flash: isolated compositor candidate

Status: source hypothesis with a confirmed occlusion invariant violation, not a device-verified fix. Base Sandium #1173, `57dca6b3343d89579556dad4ea4c185e1bc7a0b6`; Chromium `d331de35ca8ab1358c7a17e4bd41627d55eaef51`.

## Evidence

The user confirms the short `chrome-trace-2026-11-15-100849.pftrace.gz` and `155504.mp4` recording capture the same navigation. The return from NDTV Profit to Google search uses a valid cached screenshot, not fallback (`fallback=false`, cache_reason 0). It restores via BFCache. Preview and activated viewport are 1080x2234, destination identity matches, scale1 and scroll0/0. Activated destination frame precedes the 126 ms crossfade. These observations do not support fallback color or a gross viewport-size mismatch as the cause for this event.

The recording shows Google content sliding into place, followed by a blue wash that intensifies while browser chrome stays normal, then disappears. A fixed page pixel through nine successive frames progresses from RGB(39,40,74) through (14,14,185) to (0,0,252). This is compatible with fading a screenshot over an exposed blue surface, rather than choosing a blue fallback screenshot.

## Pinned source causal chain

`cc/slim/layer_tree_impl.cc` creates an intermediate render pass for a fractional-opacity layer with multiple drawing layers. Children draw at opacity1 inside that pass. Its opaque-region occlusion is then unioned into the parent without considering the composed pass's effective opacity. Yet the parent quad has opacity `parent_opacity * layer.opacity()`. A translucent group therefore incorrectly claims to fully occlude content beneath it.

Navigation screenshots are marked `SetContentsOpaque(true)` in `navigation_entry_screenshot.cc`; the screenshot layer has a drawable scrim child. Crossfade lowers screenshot-layer opacity. This is a matching trigger for the intermediate-pass problem. The animator scrim is black, not blue.

`components/viz/service/display/skia_renderer.cc::ClearFramebuffer` clears opaque passes blue under `DCHECK_IS_ON() && !BUILDFLAG(IS_LINUX)`. Exposed undrawn compositor output matches the recording exceptionally well. The APK's effective DCHECK configuration and exact renderer invocation were not independently proven, so this last causal attribution remains a hypothesis pending instrumented/native/device validation.

## Minimal change

Extend the existing pinned, fail-closed back-transition overlay with one guard: propagate a new pass's occlusion to the parent only when `parent_opacity * layer.opacity() == 1.0f`, retaining the existing axis-aligned transform requirement. Keep internal-pass occlusion, screenshot opaque metadata, blend mode, background clearing, cached screenshot selection, activation/identity safeguards, animation duration, BFCache and scroll/insets untouched.

This is a compositor correctness change with broader effect than navigation: translucent groups may correctly draw more rear content rather than culling it. It does not disable assertions or conceal the blue by changing debug clear colors.

## Tests and limits

241 local tests pass, including 21 back-transition/checkpoint source/model tests, including 5 new tests for the exact pinned transformation, idempotence, fail-closed anchor, parent-opacity guard, unchanged inner occlusion and opaque/translucent/axis-alignment truth table. These are NOT native compositor or Android runtime tests.

Before release, run native compositor regression cases with an opaque rear layer and overlapping opaque children in a fractional-opacity foreground group. Assert rear quads remain at fractional opacity and can be culled at opacity1. Include an ancestor-opacity plus filter-created-pass case. Build the real APK only after user confirmation, inspect it, then reproduce the same swipe return on device and record it. Test normal back, cancelled gestures, dark/light pages, rapid repeats and blur/darken settings. Confirm no blue wash and no new page instability. No build or publication was performed for this candidate.
