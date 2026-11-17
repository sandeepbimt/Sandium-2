# Canonical menu storage repair (held separately from #1294 navigation rollback)

## Established defect

Sandium Edit writes membership and order in application-private SharedPreferences
`sandium.menu.layout.v1` / `layout`. Native Settings > Customize Menu continued to
read/write Brave's boolean visibility preferences. The Sandium parser intentionally
uses those old booleans only for newly encountered entries, so native edits to a
known entry were ignored by the phone menu. Native Settings also trusted its cached
Bundle and allowed AndroidX default preference persistence, introducing another
potentially inconsistent view of the same setting.

This is a reproducible source-level store disagreement. We have **not established**
that the owner used native Settings or that it caused their exact #1290 loss after
closing the app. The same-editor save/load path already uses synchronous commit;
no Android process-restart reproduction has proved disk loss.

## Repair

- Both native Settings and Sandium Edit now use the existing canonical layout.
- `CustomizeBraveMenu.isVisible` reads canonical membership for known IDs and only
  falls back to existing legacy preferences for unknown IDs. Product restrictions
  still run first.
- Native switches use that live read rather than cached Bundle values; AndroidX
  auto-persistence is disabled. A toggle returns the actual synchronous disk result.
- Changing one item preserves all other membership/order, including unavailable
  actions. Missing items append once. Invalid keys, capacity exhaustion, and corrupt
  existing data fail without replacing it.
- No clear, reset, new storage namespace or bulk migration. Existing v1 bytes remain
  readable, including data from older APKs. Legacy preferences remain untouched.
- State/store Java classes move from internal to public appmenu target so the native
  settings module can use them without an internal dependency. Old checkpoint GN
  entries are normalized, not duplicated; the new settings patch input is included
  in the reset manifest.

## Tests and limitations

Host tests compile the actual State/Preferences implementation with a file-backed
Android SharedPreferences stand-in and execute separate JVM processes. Cases:
editor add/move/remove; native live reads over stale fallback; native add/remove/
re-add; membership/order reload; unavailable item reappearance; changed catalog
upgrade simulation; old namespace migration; write failure; invalid keys; corrupt
layout preservation; capacity limit. These are not real Android lifecycle tests.

Pinned source overlay tests cover clean apply, repeated apply, prior-checkpoint
GN upgrade, verification and source-drift rejection. Independent review caught and
resolved duplicate class registration, stale fallback and capacity no-op issues.

Before calling the owner's exact problem solved, validate on device with existing
data and an in-place upgrade: add, move, remove and re-add separately; normal close/
reopen and Exit; verify order and membership from both editor surfaces. Do not
uninstall or clear data. Clean install is a separate, later test. No APK was built
or deployed for this repair at this stage.
