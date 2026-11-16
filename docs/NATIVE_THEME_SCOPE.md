# Sandium native theme scope

The current baseline is the owner's Oppo-reference request of 15 November 2026.
See [OPPO_THEME_2026-11-15.md](OPPO_THEME_2026-11-15.md) for sampled palette,
covered surfaces, protected semantic colors, verification and runtime limits.
Earlier pale-green, sand-gold and muted-blue palettes are superseded.

`apply-sandium-native-theme.py BRAVE_ROOT` rewrites Brave Android color overlays
and scoped Settings appearance. Apply after source/color overlays, before
GN/resource packaging. The existing native-readiness and filter logic, Sandium
logo/animation, website rendering and private/security identity are untouched.
The separately applied `apply-sandium-oppo-toggles.py SRC BRAVE_ROOT` implements
shared native-switch styling; fixed Oppo switch colors intentionally do not
inherit wallpaper/dynamic primaries, avoiding low-contrast white thumbs.

The persisted dynamic-color preference is not rewritten. Other controls retain
explicit dynamic opt-in and light-mode contrast. No source-only test proves
uniformity of every custom view or Android-owned dialog; device visual checks
remain necessary.

## Settings heading background (16 November 2026)

The shared Settings activity now paints `app_bar_layout` with the same
`sandiumSettingsBackground()` value as the preference screen root after the
base activity finishes setup. This makes the title/search surroundings on main
Settings and shared sub-settings (including Homepage) match the section backing.
The search field and preference cards retain their separate surfaces. Existing
light and explicit dynamic-color behavior stays in the helper; no status-bar
opacity, inset, sizing, navigation or scrolling code changes.

Pinned source/idempotence tests cover the shared activity and theme helper.
Android device verification of main/sub-setting navigation remains pending.
