# Sandium full-uBO experiment — EXT0 source port

This is an isolated **full-uBO implementation experiment**, not a verified shipping
replacement. Current source includes packaged uBO1.76.4, fixed-identity Shields
bridge, authoritative request policy, exclusive startup routing, runtime-loss
guards, custom-rule synchronization, real-block telemetry and visible Shields
status. See `shields_bridge/README.md` for current parity gaps and `status/` for UI.
Build/runtime outcomes must be obtained from the actual run and device evidence.

The EXT0 decisions and run notes below are historical milestones. Statements such
as “not triggered”, “no component loaded” or “still required” describe that stage,
not the complete current implementation. Defaults remain opt-in; explicit current
pipeline flags determine whether runtime layers are enabled.

## Provenance and immutable inputs

* Sandium base: `d0d024f` (same tree shipped for #1292).
* Brave core: `44a84b1f89d9a35287289d6a3d493e362f5a5123` / 1.98.62.
* Chromium: `d331de35ca8ab1358c7a17e4bd41627d55eaef51` / 156.0.8078.74.
* Upstream lead: https://github.com/brave/brave-core/pull/40242 (Draft).
* Upstream five-commit patch SHA256:
  `5e6fb6d65abd7093e004df3e0faf59fc5e5bebb3f54b87a1ca2cac450091f787`.
* Adapted patch SHA256:
  `5add076c9c5daa6a9bfba4f76ffa0bc3ed690a46a1732f11c8220297fb263a93`.

## Port decisions

Nine upstream path conflicts were reconciled against pinned Chromium/Brave:
Android resources/build rules, extensions target dependencies, component resources,
favicon sources, and cr_elements. The newer pinned `BraveIsFavicon2AllowedOnOrigin`
security/access behavior remains alongside the extension favicon overrides.
Generated Chromium patches for conflicted files were rebuilt against exact sources.
The build opt-in is `sandium_ubo_runtime_experiment=true`; default is false.
The runtime `BraveAndroidExtensions` flag is still disabled by default.

A component extension bypasses the draft's ordinary extension policy gate.
Consequently **do not bundle/load uBO as a component yet**: it must acquire an
explicit tested runtime readiness gate. Default-enabling the runtime feature is
also not equivalent to its explicit command-line enabling: dependency overrides
must be verified (`WebContentsDiscard`, `LazyBrowserInterfaceBroker`,
`LoadAllTabsAtStartup`). No ad-block engine cutover is part of EXT0.

## Validation so far

* Adapted complete patch applies cleanly to exact clean Brave pin.
* All 11 changed/new generated Chromium patches pass `git apply --check` against
  corresponding exact Chromium input; results recorded in pinned-patch-results.json.
* Four read-only preflight safety tests pass (digest/pin/dirty-base/gate checks).
* Actual partial-tree product UI/removal/homepage/capture and native-nav rollback
  composition passes after accepting the exact added extension flag in the removal
  transform. Existing removed product entries remain removed; six feature-map tests pass.
* Full GN, Java/native compilation and ARM64 runtime are **not yet passed**.
  Local Chromium materialization is a 5.6MB selective source fixture, not a full
  build tree. A patch apply/composition pass is not a compile/runtime proof.
* No CI push/build or device/emulator action has been made for this experiment.

## Next gates

1. Validate all regenerated/new patches and combined Sandium removal overlays.
2. GN compile proof on ARM64 in an isolated existing Full-mode experiment branch;
   preserve canonical build checkpoints and avoid contaminating #1292 caches.
3. Full uBO background runtime proof (tabs/windowing, storage, blocking requests,
   document-start scriptlets/all frames, restart, private profile separation).
4. Native UI bridge with fixed identity/capability allowlist, versioned replies,
   durable settings transaction/readback, original custom-rules preservation.
5. Only after ARM64 runtime parity: coordinated network + cosmetic/scriptlet
   cutover on controlled navigation, keeping unrelated Shields and rollback.

Do not label partial list parsing, engine payload sizes, or synthetic model tests
as uBO runtime parity. Do not globally enable arbitrary extension installation.

## EXT0 compile-only CI isolation (prepared, not triggered)

The experimental branch's Full workflow accepts only `experiment/ubo-runtime`;
`run_build` still defaults false. It reads the immutable accepted reference but
cannot renew or publish reference metadata. Built handoffs and APK completion
markers have an `sandium-ubo-ext0-*` namespace; dependency-tool caches remain
shared. No emulator pipeline or new paid service is added.

Before ordinary source preparation, `source.py --mode off` restores exactly the
76 touched core files and 11 native targets to pinned upstream + existing Brave
patches. After each removal reset, it reapplies the complete port from exact
pinned blobs, before product overlays. It rejects changed pins, payload hashes,
symlinks and unowned new-path collisions; all source payloads preflight before
live writes. Four reset/CI isolation tests plus two source replay tests pass.

The GN opt-in compiles runtime infrastructure only. No uBO component is loaded,
no runtime feature is enabled, and the existing blocker remains the sole blocker.
This compile-only APK will not prove uBO filtering. It is the first gate before
adding explicit readiness and an exclusive engine-selection experiment.

Do not trigger while the priority phone run is active. Coordinate with the root;
this branch is not a production replacement. A successful build still requires
real ARM64 runtime validation before progressing to engine cutover.

## Future data-preservation gate

Historical Brave desktop issue https://github.com/brave/brave-browser/issues/42608
reports MV2 toggle behavior losing extension custom data. This is a lead, not
proof of Android behavior. Never implement engine selection by uninstalling uBO.
Before cutover, on a disposable profile containing custom rules, disabled/deleted
subscriptions and site choices, test enable/disable, upgrade, restart, rollback
and backup restoration with exact membership/order/text comparisons. No real
user profile may be cleared for these tests. Android infrastructure tracking:
https://github.com/brave/brave-browser/issues/59354 .

## Pinned Chromium enum dependency

Run #1301 reached the extension-enabled GN graph and exposed a pinned-version
guard mismatch: mobile extension UI needs `extension_action_enums`, but Chromium
156 defined that Java enum target and Android rules import only for desktop
Android. The isolated backport enables both on Android with extensions core,
matching the consumer. Native graph and APK proof are still pending.

## Later engine selector (user request, not implemented)
After full uBO runtime proof, expose a reversible Brave/uBlock engine selector.
Default remains Brave. A selection must atomically coordinate network filtering,
cosmetics and scriptlets so both engines are never active simultaneously. Preserve
both engines' settings and rules across switches, restart and upgrade. Provide
crash-safe rollback; require a restart if needed for a correct handoff. Do not
ship a nonfunctional selector before the runtime and persistence tests pass.
Selecting another engine must show a confirmation popup with a Restart button,
using the existing smooth UX. Apply the engine choice only after restart;
canceling leaves the current selection and active engine unchanged.
