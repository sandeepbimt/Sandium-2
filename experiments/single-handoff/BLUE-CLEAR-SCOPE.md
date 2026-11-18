# Controlled diagnostic clear-colour test

Baseline: frozen Sandium #1389; Chromium d331de35ca8ab1358c7a17e4bd41627d55eaef51 (156.0.8078.74).

## Exact change

Only SkiaRenderer::ClearFramebuffer's DCHECK-only, non-Linux opaque render-pass
clear changes from blue to opaque black. Transparent render passes, scissor and
damage bounds, clear timing, navigation, caches and DCHECKs remain unchanged.
No new feature flag, timer, overlay or global assertion disabling is introduced.
The existing application journal owns reversible source application and rollback.

Black is deliberately deterministic and opaque. Skipping the clear, using
uninitialized storage, or making an opaque pass transparent would confound the
experiment and could expose stale pixels. This test does none of those things.

## Evidence and limits

Pinned Chromium's dcheck_always_on default includes nonofficial Chromium builds,
even when is_debug=false. The checked-in Sandium and RawS configurations request
is_official_build=false. Actual generated C++ DCHECK defines have not yet been
independently recovered from the delivered APK build artifacts. Therefore this
code path is a source-backed candidate, not a confirmed cause of the recordings.

If the same transition now pulses black rather than blue, that supports diagnostic
clear colour exposure as the source, but the missing-frame/coverage/handoff defect
remains. If blue persists, this is not its sole source. Absence of blue alone does
not prove navigation fixed. Compare the same routes, first/cold and later/warm
visits, and inspect for dark/blank pulses, stale frames and shifted geometry.

## Validation

The fixture contains the full pinned upstream file and its SHA256. Tests verify
the only changed function block, idempotence, nonmutating planning, inverse source
round-trip, and fail-closed partial/drift/duplicate input handling. The actual
before/after C++ function is compiled and executed across DCHECK/non-DCHECK,
Linux/non-Linux and transparent/opaque branches. These are focused source and
function tests, not a full Android APK or GPU/device verification.

Upstream: https://github.com/chromium/chromium/blob/d331de35ca8ab1358c7a17e4bd41627d55eaef51/components/viz/service/display/skia_renderer.cc
