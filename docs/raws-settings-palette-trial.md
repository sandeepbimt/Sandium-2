# RawS native Android UI trial

This restore-only trial uses the presentation and actions from the owner-supplied
RawS native UI handoff (design commit
`8243108b03825729498383557fb6bf8f62c16c55`) with Chromium
`52bdd21723d5db0c9ab11716d38feac74828cf84`.

- Welcome: Sandium title and surface palette in the native first-run host.
  Chromium still owns consent, sign-in, each required step and the incoming URL.
- Menu: existing Chromium menu and action dispatch with a shared editor, saved
  order/visibility, and an All Menu route. Uses native lists, not a new grid.
- Address bar: optional Sandium day/night capsule color at the native color
  endpoint. Default is stock; type, focus, animation, site colors, NTP and
  Incognito remain native. The switch applies when the browser is reopened.
- Shield: one native bottom sheet reachable from the tabbed menu, linked to the
  native Protection/Privacy settings. Reports status unavailable where no
  authoritative live state is exposed. No new blocker toggles or fake counts.
- Settings: native list palette, live menu editor entry, address-bar color
  preference and Protection entry. Existing preference behavior is unchanged.

The UI does not own navigation, page loading, tab history, renderer state or
page transitions. The original engine and rules are unchanged; Chromium Rust
compatibility grants specific wrappers visibility and enables features directly
requested by the reviewed adblock crate. This run does not change checkpoint
selection, save policy, CI schedule or restore-only time budget.

The reference illustration is not packaged. The restore gate verifies exact
source and staged-tree identities. The generated APK graph must reach the actual
Java and resource owners for all five surfaces. Source/host checks are not
Android compilation or phone acceptance.

On device: fresh install/rotation, normal reopen, toolbar focus/site colors/back,
menu reorder/Cancel/Done/All/relaunch, repeated Shield open/dismiss, and Settings
routes plus light/dark and accessibility. Compare to the unmodified Chromium
interaction for page and toolbar behavior.
