# Approved UI additions on the completed #1402 base

User direction supersedes Full Mode-U: use normal Full and the existing pinned
Brave1.98.62 / Chromium156, not the latest upstream upgrade. This branch starts
from remote bba47961ec5ea37799160fa8e6ac485276170c67, with the completed #1402
reference and #1410 independent readback. The old branch/archive is not modified.

## Scope

- Preserve all #1402 features, thirteen removal groups and #1389-derived
  navigation/handoff architecture, except the explicitly approved blur choice.
- Native156 Chromium transition blur Off/On, default On; upstream timing and
  eligibility, separate optional dim. No Sandium strength/hold/fade variants.
- Welcome disabled grey animated dots, off-white Start browsing or Quick Restart,
  action-matched five-step feedback over1.5seconds and pale-green button fill.
- Off-white thin top-edge address loading line, no whole-address green fill.
- Default-On notification choice. Android permission remains the user's decision;
  request only after setup/restart and an eligible normal homepage frame. Preserve
  previous OS denial, grants, request history and no-repeat behavior.

## Pipeline and reference

Normal Full jobs are structurally identical to the exact frozen baseline; only
five workflow branch filters select work/1402-approved-ui. Default run_build stays
false. The source/official GN/APK identity and all eight shard hashes are checked
against the exact completed1402 reference before restore adoption. The old APK
and local completion state are retired before the new product build. Output
handoffs remain current-workflow scoped; full post-APK archive behavior is intact.

No Full-U schema, latest-engine pin, source-only phase workflow or target158
compatibility shim is carried into this branch. Newly added notification reset
owners are exact156 upstream inputs with the exact pinned Brave coordinator patch.
Existing removal steps, feature groups and GN removal flags stay unchanged.

## Proof and limitations

Individual local tests: welcome14, nativeblur9, notifications7 and progress10
pass. These prove specific source transformations/fixtures and helper behavior,
not Android compilation or phone smoothness. Full canonical composition and
normal Full wiring are checked before launch. Native blur remains limited to
upstream eligible navigations; it does not guarantee no page flashes. Deferred
permission uses at-most-once intent consumption and cannot guarantee display if
the process dies between persistence and the OS request.

A later CI success must include the actual APK and full archive checks. No CI
run has been launched from this branch at the time this record was written.

## Integration evidence

- Normal Full54 tests pass with historical provenance preserved and explicit
  frozen1402 task mapping. Active job objects remain identical to that baseline.
- Full single-handoff88 tests pass, including native156 Settings/native fixtures
  and executed Java startup preference migration tests.
- Scoped lint proof refresh changes only reset ownership hashes and supplemental
  inventory file identity: all964 exact exception rows and eight owned removals
  are unchanged; rendered lint XML is byte-identical. Ten original resource
  tests and three new provenance tests pass.
- The real branding/welcome CLI admission checks and full actual156 composition
  are additional release gates. A diagnostic-probe postimage composition mismatch
  was found and corrected by authenticating and preserving only the exact known
  probes. Independent full replay, real branding/welcome CLI twice and exact
  rollback now pass. Unknown probe modifications remain rejected.

## Device checks for the eventual APK

1. Upgrade over #1402 without uninstalling; confirm saved data/menu/filter choices.
2. Welcome preparation shows dots and ignores taps until ready. Confirm the ready
   action and countdown distinguish Start browsing from Quick Restart and finish
   in1.5seconds, including reduced-motion mode and leaving/re-entering the activity.
3. Blur defaults On only when no saved choice overrides it. Check Off/On and
   independent dim after the requested restart; native eligibility is unchanged.
4. Address progress stays on the top edge without changing page/toolbar geometry.
5. Notification prompt never overlays welcome. Check toggleOff, existing grant,
   prior denial, fresh permission, interrupted restart, tab change and modal states.
6. Regression-check homepage/back/forward/menu/keyboard behavior, existing dark
   pages and filters, and removed-feature Settings surfaces.

The final Off/On source pass also removes exactly the four Sandium-owned legacy
Default/Low/Medium/High label declarations whose consumers were replaced. It
reuses the existing summary resource for native-transition guidance. Exact marker
and old-content guards, a Git-blob-verified pinned156 GRD fixture and rollback
checks cover this change. No resource exclusion was added to hide unused labels.
Native blur focused coverage is now12 tests; the full handoff suite remains88.
