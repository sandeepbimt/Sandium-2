# Chromium 158 native blur control

Pinned source: Chromium `52bdd21723d5db0c9ab11716d38feac74828cf84`.
Fixtures retain original Git blob identities, checked before planning.

- Startup `sandium_page_transition_blur_enabled`: absent → On; legacy
  `default`/`off` → Off, all other legacy strings → On. Existing boolean wins.
- Removes stale command-line strength/timing parameters and conflicting feature
  entries, then selects the native feature by name only. Restart is required.
- Native parameters stay sigma 3.0, hold 350 ms, fade 150 ms. These are upstream
  values, not newly selected Sandium timing values.
- Native eligibility stays unchanged: no reload, same-document, BFCache,
  same-host navigation, or simultaneous native predictive-back animation.
  This does not promise blur on every navigation or homepage transition.
- Separate existing Darken preference retains an optional 20% black layer,
  disabled while blur is Off. Its saved preference is preserved, not confused
  with blur intensity. Dim has its own feature name and is not an upstream
  Chromium feature. No fallback/night-color/capture override is restored.
- Upstream ViewAndroid detach/destruction cleanup added in158 remains intact.

The planner runs last in the outer rollback journal, after native-navigation
reverses old overlays. It refuses non-native manager/header postimages rather
than overwriting unexpected source. The upstream content_features blur block
must be verbatim and the old custom dim FeatureParam absent. Existing unrelated
content_features declarations are preserved.

Validation: six focused Python tests cover fixture integrity, eligibility,
parameter preservation, source-drift rejection, no-write planning, exact journal
rollback, startup toggle shape, and actual nested Settings marker blocks.
No Android compilation or device test is claimed. Full158 source composition
must also pass: existing earlier base Appearance overlay currently fails its
old ordering anchor on pinned158 before this final planner is reached.
