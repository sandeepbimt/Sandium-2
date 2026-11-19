# Native blur on frozen #1402

Chromium d331de35ca8ab1358c7a17e4bd41627d55eaef51 / Brave
44a84b1f89d9a35287289d6a3d493e362f5a5123 only. No Chromium158 changes.
All four Chromium fixture Git blobs checked against this exact upstream pin.
Appearance fixture is pinned Brave blob3081a2777a6dd226417cd0284035f2117b8de973.

New boolean sandium_page_transition_blur_enabled defaults On; saved boolean
wins; absent boolean migrates legacy default/off to Off, other/absent to On.
Settings uses switch; welcome owner uses the same preference contract.
Startup removes previous blur parameter strings and conflicting feature entries,
then selects Chromium native feature by name, with restart required.

Native sigma3.0, hold350ms, fade150ms, fallback color, eligibility, visual-paint
release and teardown are unchanged. Native excludes reload, same-document,
same-host, BFCache and overlapping predictive-back animations; not every route
will blur. Separate optional Sandium20%dim remains its own feature and control.
It does not alter native sigma, hold, fade, capture, or fallback policy.

Outer planner runs last after existing inner native reversal. Exact native
manager/header postimages and upstream blur feature parameter blocks are checked.
Unexpected source fails closed instead of being replaced. Actual prepare script
unwinds outer then inner journal before legacy overlays replay. Direct base/full
replay over modified outer postimages intentionally rejects different markers.

Nine focused tests verify upstream integrity, native156 frozen→reversal→dim,
Settings source composition and proper rollback→base/full→native replay,
parameter preservation, source-drift rejection, startup toggle shape, and exact
journal restoration. Python checks do not establish Android compilation or
runtime quality; these remain integration/build/device validation gates.
