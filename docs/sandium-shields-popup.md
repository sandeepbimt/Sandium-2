# Sandium grouped Shields popup

Selected design B: an anchored popup, never a full-page settings screen. This change is
presentation-only, separate from the paused Brave Origin removal work.

## Visible controls

- Site Shields switch with current site/status
- Block trackers & ads and Block cookies, grouped together
- Block element and Clear all blocked elements, grouped together
- Shred site's data, its own group
- Bottom text: localized count followed by “trackers and ads blocked”

Clear is visible but disabled when no site cosmetic rules exist. Existing native availability
guards for Shred and the element picker remain: unavailable functions are not falsely enabled.
No Advanced expansion step. HTTPS, scripts, fingerprinting, global settings, the reset-defaults
row, old warning/report footer and old large count presentation are hidden. Their native
protection settings are unchanged. Legacy resource IDs stay in an inaccessible zero-size GONE
container for safe shared-code compatibility; this is UI hiding, not engine removal.

The existing bounded PopupWindow, orientation/toolbar anchoring, scrolling, lifecycle dismissal,
site-setting setters, Shred confirmation, and element-picker dispatch remain native and unchanged.
Grouped cards use Sandium's shared theme, with dark charcoal base and near-white green controls.
Existing light/dynamic themes remain readable rather than forced dark.

## Counter correctness

The new line sums the actual per-tab ads and trackers events only (not scripts/fingerprinting),
formats the number for the current locale, and uses a GRD Android `%1$s` placeholder.
Zero is yellow, positive is green, with distinct readable light/dark resource colors.
The count is not hardcoded to the concept preview's 23. A queued update rechecks tab identity
and reads the latest count on execution rather than displaying a stale captured value.
Opening the popup and clearing navigation statistics also refresh the line. It is accessible
as a normal text node, not a live region that announces every blocked request.

## Pipeline and replay

Apply `apply-sandium-shields-popup.py` at the end of product-overlay-29, after existing palette,
branding and status-bar overlays. Input is exact Brave Core commit
`44a84b1f89d9a35287289d6a3d493e362f5a5123`. Transform all candidate contents before writing.
Retain original licenses. Tests use the actual pinned files via git, not Java fragments.

Checks performed: 8 focused popup source tests, clean and repeated application, compatibility
with Sandium's two-state Shields overlay, 6 palette tests. Branding unit checks pass; full
branding verification on the isolated Brave clone is blocked by the missing prior Sandium
logo asset (not supplied by this popup overlay). No native Android compilation, emulator,
or device validation has yet been performed. Source checks are not runtime validation.

Before marking the APK verified: test zero/positive count, navigation while open, reopen,
Shields off/on without changing hidden settings, each submenu and Back, Shred cancellation,
clear blocked elements empty/nonempty, element picker, landscape, large fonts, RTL and TalkBack.
