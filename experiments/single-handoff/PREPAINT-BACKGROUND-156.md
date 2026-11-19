# Temporary renderer background candidate (#1418)

Reference: BareBrowser v1.0.0 patch 0186, “Let a light page keep its own canvas on a dark theme”:
https://github.com/BareBrowser/bare-browser/blob/v1.0.0/patches/0186-Let-a-light-page-keep-its-own-canvas-on-a-dark-theme.patch

Pinned Chromium: d331de35ca8ab1358c7a17e4bd41627d55eaef51.
Exact tab_android.cc Git blob: dc12c8e4e232f717b9a6087ee8fcc04e1b832ae5.

Bare identified why a permanent black page-base color breaks transparent light websites. This candidate adapts its temporary WebContents-owned canvas lifecycle; it does NOT import Bare wholesale or change Chromium's blur, Off/Low choice, page darkening, handoff timing, screenshot holder, toolbar geometry, or page-load scheduling.

Apply black only on committed successful visible HTTP(S) fresh-document navigation when the app theme is dark. Release to Chromium's default canvas on first visually nonempty paint, load stop (including empty pages), superseding navigation, hiding, or renderer loss. Destruction only drops ownership without calling the renderer. Exclude same-document, BFCache and prerender activation, errors and native URLs. Unlike Bare, do not apply at WebContents attachment: that could recolor an already-painted restored document. A legitimate light page keeps its native canvas after first paint; no permanent black background or CSS injection.

The observed roughly RGB204 flash has NOT been attributed conclusively to the renderer base canvas. This is a bounded test candidate, not a proven fix, and cannot address Android/compositor placeholder colors or precommit flashes. Restoring the outer journal removes it exactly. Unknown source changes fail closed.

Validation: exact pinned fixture hash, idempotence/drift rejection, real emitted C++ helper compiled and executed against interface stubs, all lifecycle exclusions/releases exercised, outer transaction rollback/replay. These checks are not an Android compilation or pixel/rendering verification. Device acceptance must compare initial dark navigation, a transparent-background light article with site darkening disabled, cancellation, back/cache restore, tab switch and renderer failure. Do not claim white flashes eliminated until verified.
