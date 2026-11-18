# Dormant unwrapped NTP capture normalization

## Supported case

This correction is intentionally limited to the observed settled bottom-toolbar
route: regular current NTP, no wallpaper wrapper, top-controls height/content
offset/top offset all zero, bottom offset zero, bottom height at least the positive
toolbar height, no tab strip, attached untransformed unscrolled laid-out root and
parent, zero parent padding, and the exact expected applied root margin/position.
Unknown or changing geometry keeps the existing Chromium capture contract.

Pinned NewTabPage.updateMargins puts an **unwrapped root** at:

    contentOffset - toolbarHeight - tabStripHeight

The existing static content scene uses contentOffset in physical pixels (the
StaticTabSceneLayer Java binder adds RENDER_Y*density then native SetPosition).
At the supported settled zero-top case the root-to-content origin is therefore
`-toolbarHeight`, not `-topControlsHeight` (which is zero). The capture-only
capability returns that overlap; no live margin, layout, status bar, wallpaper or
toolbar height changes. Synchronous capture retains its extra topControlsHeight
compensation and the native consumer's inverse adjustment.

This is the existing native compositor controls-coordinate contract, not a new
runtime proof of arbitrary scene ancestry or a general Viz offset-tag evaluator.
It does not apply to moving top controls, top toolbar, tab strip, padded/scaled
parents or wrapped Sandium wallpaper roots. In a wrapper, the foreground margin
already exists inside captured local pixels; applying the unwrapped invariant
would double-subtract it. Wrapper capture remains an explicit unsupported gap.

## Recording ownership

A snapshot fixes page, view, WebContents/container identity, viewport dimensions,
background, overlap, attachment, window position and geometry before recording.
HardwareDraw records synchronously on the UI thread, then paints the immutable
RenderNode asynchronously. Identity/geometry is checked at recording start/end;
mutation during recording rejects the result, releasing HardwareBuffer and its
reader callback, or recycling the exclusive result bitmap. Ordinary navigation
AFTER recording is valid and does not invalidate the outgoing history snapshot.
The asynchronous completion never substitutes the newly current page.

## Verification limits

Host tests compile actual owner, snapshot and delivery methods with explicit
collaborator doubles, replay full source transforms with existing capture
diagnostics, and test bottom/top toolbar behavior, insets, sync compensation,
wrapper exclusion, geometry/identity mutation and result ownership. This does not
replace generated-JNI/Android compilation or phone verification. No fixed 48/112/
168-pixel constant or detached renderer-container origin is used.
