# Native status inset restoration

The owner removed transparent status bar and scroll-under behavior throughout
browser/web. The normal product now calls `apply-sandium-native-insets.py` instead
of installing the experimental scroll-status overlay. The full native-navigation
comparison remains OFF: Sandium Back/cache/ordinary transitions are retained.

The migration reverses all 64 reviewed transformations across 18 pinned files:
custom status spacer/top stack, root inset consumption, underlap eligibility,
synthetic CSS safe area, inset observer changes, and associated test mutations.
It also removes old underlap diagnostics and the optional comparison gradient.
Stage30 also migrates before later overlays and verifies again at the end, so
a legacy UI checkpoint cannot bypass the restoration by resuming late.
It preserves unrelated source edits and plans all changes before writing. Clean
native input and repeat/resume are supported. Unknown partial edits fail closed.

The status area uses normal native inset geometry. The driver composes the
reviewed opaque paint transform after geometry in memory and validates all 19
files before writing. Native explicit status providers retain precedence; plain
web browsing follows the actual renderer root background callback, including
forced-dark correction. This is root/backdrop color, not sampling an arbitrary
fixed header or image pixel. Both paint files are reset-owned on full and UI replay.

For target SDK 37 on Android 15/16, transparent OS-window status color remains
only where native edge-to-edge plumbing supplies the opaque reserved-area paint
delegate. The visible region is opaque and icons use that same composited RGB.
No unsupported edge-to-edge opt-out is introduced. This is source/host verified,
not a claim of real-phone opacity, icon contrast or Back/Forward correctness.
No immersive/fullscreen behavior is added.

Validation: native fixture equality, old overlay/trace/gradient migration,
repeat/readback, unknown-anchor no-partial-write, wrapper wiring, and existing
address/toolbar source-contract tests. Full Android build/device validation is
still required, especially Back with hidden bar, menu, rotation, native homepage,
settings, fullscreen exit and IME. Verify opaque status backing on Android15/16
with gesture and three-button navigation; actual dark/light/forced-dark pages,
provider/native screens, initial load/error, and Back/Forward with bar hidden
must not reveal wallpaper/web content through the reserved status region.
