"""Reversible test of Chromium's DCHECK-only diagnostic blue clear.

Retains deterministic initialization; changes no DCHECK or navigation behaviour.
Application/rollback is owned by the existing navigation overlay journal.
"""
from pathlib import Path

PATH = 'components/viz/service/display/skia_renderer.cc'
PIN = 'd331de35ca8ab1358c7a17e4bd41627d55eaef51'
MARKER = 'SANDIUM_DIAGNOSTIC_CLEAR_TEST_V1'
BEFORE = '''void SkiaRenderer::ClearFramebuffer() {
  if (current_frame()->current_render_pass->has_transparent_background) {
    ClearCanvas(SkColors::kTransparent);
  } else {
#if DCHECK_IS_ON() && !BUILDFLAG(IS_LINUX)
    // On DEBUG builds, opaque render passes are cleared to blue
    // to easily see regions that were not drawn on the screen.
    // ClearCavas() call causes slight pixel difference, so linux-ref and
    // linux-blink-ref bots cannot share the same baseline for webtest.
    // So remove this ClearCanvas() call for dcheck on build for now.
    // TODO(crbug.com/40227119): add it back.
    ClearCanvas(SkColors::kBlue);
#endif
  }
}'''
AFTER = BEFORE.replace('    ClearCanvas(SkColors::kBlue);', '''    // SANDIUM_DIAGNOSTIC_CLEAR_TEST_V1: isolate the debug clear colour only.
    // Keep opaque initialization and all DCHECKs. A dark pulse still means
    // uncovered content; this is not a navigation/presentation-readiness fix.
    ClearCanvas(SkColors::kBlack);''')


def transform(source):
    if source.count(AFTER) == 1 and source.count(MARKER) == 1:
        if BEFORE in source:
            raise ValueError('Duplicate diagnostic clear function')
        return source
    if MARKER in source or source.count(BEFORE) != 1:
        raise ValueError('Pinned diagnostic clear function drift or partial patch')
    return source.replace(BEFORE, AFTER, 1)


def plan(root):
    path = Path(root) / PATH
    return {path: transform(path.read_text())}
