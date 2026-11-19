# Exact 1.100.58 preparation audit

Read from retained a672821 (#1402 reference), retarget work based 63d38a3.
No prior unpublished 157 implementation/test result is assumed present or valid.
The new exact upstream package requires Node >=24.16.0 and pnpm >=11.11.0;
existing selected versions still satisfy those constraints.

## Preserve ordered preparation

- `prepare-brave-source.sh`: unwind outer single-handoff/native journals and
  reset diagnostics before source reset; host tooling, source init, native Brave
  RBE/Siso setup; removal reset, retire-reader, full overlays, Morphe, then GN.
- Ordered product scripts 24–30: branding; filter reset/subscriptions/bootstrap;
  page/back transitions and controls; homepage warmup/downloads/welcome;
  Shields two-state/engine-race/resources; complete UI composition; final removal
  and downstream product composition.
- Script29 order: prune/promo/branding/theme/insets, Shields popup, bottom toolbar,
  paged menu/chrome theme, unified address, toolbar refinement/search choices,
  focus-follow/settings fade/progress diagnostics/suggestion anchor/UI links,
  high-contrast toggles.
- Script30 order: disposable removal composition; insets; 13-removal apply;
  home shortcuts; video gestures; dark/manual correction; page text; homepage
  backing/paint; capture coherence; address progress; final insets/text checks;
  diagnostics; configured native-navigation plus single-handoff LAST; graph
  audits/evidence; same-pin lint resource repair.
- Native-navigation and single-handoff profiles are both enabled in #1402.
  Unwind outer journal before inner journal. Preserve native capture coordinates,
  asynchronous diagnostic journal and absence of the older recolor workaround.
  Native-blur changes are assigned separately, not included in this patch.

## Removal contract

13 groups: Email aliases; Leo/AI; News; Playlist; Rewards/Ads; Speedreader;
Talk; Tor; VPN; Wallet/Web3; Wayback; Web Discovery; Reporting (daily ping,
crash uploads, P3A). Removal manifest has 350 core reset inputs, 123 Chromium
inputs, 18 exact Brave patch replays, 37 generated outputs and 16 GN arguments.
Its 16 ordered operations include billing-origin-only, native feature map,
sponsored NTP consumers, Java dependency closure, packaged extras/resources and
final overlay synchronization. Preserve entitlement checks; remove product
entry points, not purchase gates.

## Small independently verified retarget

`apply-sandium-full-overlays.py` now requires exact bd6d26d1 / 52bdd217 pins.
Ten complete upstream source fixtures were fetched at the exact Brave commit,
with original headers and SHA256 provenance. Every live main operation replays
successfully and the second replay is byte-identical: reporting defaults/runtime,
Web Discovery plus Rewards pref guard, Playlist old-profile normalization,
Android News exception removal, Android email default and Origin purchase-row
removal. Existing feature-policy test also passes.

The historical AI_ANDROID_DEPS_OLD helper anchor is absent in current upstream
browser/android/BUILD.gn. This helper is NOT called by main (AI is deliberately
left upstream there). Do not infer this is a live full-overlay failure or that
later Leo compile-exclusion adapters are compatible; they still need audit.

`upgrade_source_profile.py` separately validates the frozen candidate tuple,
official ARM64 APK target, actual checkout HEADs and exact upstream package hash.
It never claims dependency sync, GN/build readiness, APK success or compiled
compatibility with #1402. Bootstrap can consume it without modifying seed guards.

## Remaining blockers, not silently retargeted

`pin-inventory.json` separates active guards/evidence from frozen references and
historical tests/docs. This is not a bulk replacement list. Preparation shell,
vanilla verifier, removal manifests/adapters, feature-specific pin gates and both
navigation journal owners still need exact target evidence. The old checkpoint
COMPAT and #1402 reference/resume validation must stay unchanged and must not
admit new-engine compiled outputs.

The old lint inventory is explicitly same-pin evidence: 328 resources (320
approved, 8 removed) with old pinned blobs/dependency chains. It cannot be
relabelled as a 158 audit. Reset path existence and all 18 Brave patch replays
must be checked against new Chromium, and composed GN/lint/Java/native builds
remain unexecuted. Source replay here does not certify all 13-removal groups,
UI/navigation, GN graph, Android compile, APK, or device behavior.
