# Opaque page-matched status paint after native inset restoration

Pure paint-only plan for the owner's replacement requirement. Apply AFTER the
coherent scroll-status geometry reversal, without the old gradient paint.json.
It does not enable immersive mode or the full #1294 native-navigation experiment.
It does not change Sandium Back, transitions, homepage handoff, wallpaper, address
capsule or its transparent surround. Native insets remain the geometry owner.

API: `.circleci/scripts/opaque-status-paint.py::plan(src)` returns both changed
files; `transform(relative_path, source)` supports transactional composition with
the geometry owner; `PAINT_PATHS` lists source reset/verification paths. No writer,
standalone CLI, build switch, push or run. Unknown/partial paint and old underlap
residue fail closed before writes.

New reset inventory path:
`chrome/android/java/src/org/chromium/chrome/browser/ui/system/StatusBarColorController.java`
The shared EdgeToEdgeSystemBarColorHelper path is already in the18-file native
geometry inventory. Whole-profile rollback/preimage ownership belongs to the
geometry pipeline owner, not this helper.

## Visible behavior

* Plain phone browsing uses the active Tab's native background-color API and
  onBackgroundColorChanged callback. No screenshot sampling, JavaScript query,
  arbitrary theme-color or global previous-tab color cache.
* A transparent/unset initial background is flattened onto #121212; actual opaque
  light pages remain light. Partly transparent input blends onto that same dark
  fallback. Subsequent renderer/native-page background events update immediately.
* Native Hub, tablet header, focused address/suggestions UI and Settings keep their
  established surface/provider colors. The existing Settings black header/status
  customization is retained. Native status indicator/scrim overlays still apply.
* Shared E2E backing and icon-contrast calculations use the SAME opaque RGB. The
  old NTP force-light-icons override is not needed when its backing is opaque.
* Android's native E2E window can remain platform-transparent ONLY while its
  native delegate paints the opaque reserved status area. This is platform
  compositing, not scroll-under or a transparent visible bar. Without a delegate,
  the window itself retains an opaque backing rather than going transparent.

## Renderer background evidence and limitation

At pinned Chromium d331de35ca8ab1358c7a17e4bd41627d55eaef51,
WebViewImpl::BackgroundColor returns LocalFrameView::DocumentBackgroundColor.
That resolves the viewport/root backdrop and, when ColorSchemeForced is true,
applies DarkModeFilter::InvertColorIfNeeded for the background role before
blending with the base. WebFrameWidget's lifecycle background notification then
feeds the tab background observer. TabImpl updates the background before notifying
TabObserver; native/custom page background changes also use the established path.
This includes native forced-dark root-background correction, rather than the
page's author-specified meta theme-color.

It is NOT a pixel sampler for a fixed header, photograph or gradient at the top of
a page. Such content can differ from its root backdrop. Do not promise exact
per-pixel matching for those cases. The approach intentionally uses the browser's
established actual background pipeline and does not invent an overlay/sampler.

## Verification

Five tests cover exact pin hashes, replay and unknown-source rejection, full
64-fragment native geometry reversal before paint, source isolation from navigation,
backing/contrast RGB identity and no-delegate opacity. Extracted real Java methods
compile and run using JDK compiler modules with small dependency stand-ins, testing
all256 alpha values and native-vs-page surface selection. This is not a full
Android compile or phone visual regression. No build/run has been launched.
