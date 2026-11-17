# Native homepage wallpaper backing candidate

Pinned Chromium d331de35ca8ab1358c7a17e4bd41627d55eaef51 and Brave
44a84b1f89d9a35287289d6a3d493e362f5a5123. This script is not wired into CI.
Apply after normal News removal, branding, sponsored-NTP consumer cleanup and
home-shortcuts overlays. It changes only native homepage owners, not web sizing,
renderer controls, status-bar insets, navigation gestures or toolbar paint.

## Contract

BraveNewTabPage opts in regular-profile phones before publishing its provider.
FeedSurfaceCoordinator wraps its original root, preserving all foreground
children, focus/touch behavior and control-derived top/bottom margins. Its outer
root receives the existing wallpaper ImageView, not an enlarged copy of an
already-cropped bitmap. The existing worker now measures that outer-sized image;
it continues using upstream focal cropping, cancellation and bitmap callbacks.
Provider `getView()` and thumbnail capture share the outer root. Native transition
capture therefore sees the same hierarchy. Side UI margins still belong to the
outer view. Last-touch coordinates gain the foreground's offset.

The wrapper has the original default-color fallback. Foreground backgrounds are
saved and cleared only while a permitted, correctly sized bitmap exists;
disabling wallpaper restores them. Brave's policy container observes this same
paint state, including creation after readiness. Late theme updates retain new
fallback colors without covering an active backdrop. No profile preference is
written. A native preference observer is destroyed when BraveNewTabPage is
destroyed. Async callbacks after release cannot re-enable backing.

Toolbar readiness is separate from retained wallpaper paint: it additionally
requires an attachment latch. Android may still report isAttachedToWindow=true
inside detach callbacks, so the latch is explicitly cleared first. A detached
thumbnail can retain its wallpaper while toolbar readiness is false. Bitmap
replacement invalidates thumbnail state and notifies paint observers even if
readiness remains true. A size change rejects a stale-size bitmap until the
existing worker returns matching dimensions.

NativePage defaults false/no-op for all other pages. Its explicit Runnable
observer API carries readiness and bitmap changes; a separate nullable paint
color is owned by the live toolbar and published to the native overlay. Equal
color writes are no-ops to bound observer reentry. Publishing a color never
changes readiness. Toolbar subscription/capture/paint handling is a separate
change and is not part of this candidate.

## Validation and limits

Five local tests pass: exact source application/replay, plan-before-write failure,
shipping News→branding guard→sponsored cleanup→shortcuts composition, worker
cancellation/dimension call-site contract, and compiled extracted Java provider
methods covering attachment, enable/disable, stale size, bitmap replacement,
foreground fallback, paint-color deduplication and common wrapper ownership.
Fixtures are pinned source snapshots; BraveNewTabPageLayout includes the shipping
News/sponsored removal transforms. This is NOT a full Android/NullAway build or a
phone rendering test. Full combined toolbar composition, resource dependency
checks, detached snapshots, preference toggles, tablet/incognito exclusions,
orientation, IME and predictive Back still require integration/device validation.
Drawable intrinsic-dimension readiness intentionally fails closed if target
bitmap density does not match measured pixels; that case needs runtime evidence,
not unconditional readiness.
