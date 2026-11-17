# Sandium full-uBO implementation experiment

Source review: 35ccd8c. The experiment now includes a complete pinned uBlock
Origin payload, Android extension infrastructure, localized component loader,
private native Shields bridge, authoritative per-request policy, exclusive
startup ownership, bounded fallback, runtime-loss guards, source-list/custom-rule
synchronization, real-block counters and visible engine status.

This is **not a verified shipping replacement**. An activated candidate was
submitted as run #1329; consult actual CI artifacts and device evidence for its
outcome. Source tests and synthetic ownership models do not prove Android build
success, uBO execution, filtering parity or performance.

## Activation and build isolation

The pipeline opt-in `sandium_ubo_runtime_experiment=true` compiles the runtime
infrastructure. `sandium_ubo_activate_candidate=true` additionally enables the
paired SandiumUboRuntime/SandiumUboExclusiveRouting features only on the isolated
`experiment/ubo-runtime` branch. Normal phone builds and foundation runs retain
default-off activation. Explicit disable of either feature wins. Arbitrary
extension installation remains denied; only the pinned component is registered.

The integrated build script applies loader, bridge, routing, startup, request
policy, optional activation, then status. Continuations reverse exact ownership
receipts before source/product replay. Never bypass a receipt conflict. Isolated
experiment caches/markers must not replace canonical phone checkpoints.

## Actual behavior and limits

- Regular profiles can select uBO only after native exact-generation, user-rule,
  list-revision and listener readiness checks plus a live background host.
- External navigation has a bounded 12-second startup barrier. A failed startup
  unloads uBO and verifies teardown before native fallback. Failed teardown
  cancels navigation. Shields reports actual fallback, not successful replacement.
- Once selected, engine ownership is immutable for that session. Runtime loss
  blocks subsequent request/navigation boundaries and exposes restart-required;
  it does not silently enable the other engine. Previously completed/in-flight
  work cannot be retroactively blocked.
- Private/incognito profiles remain Brave-native and cannot load this component.
  This is an explicit gap against an all-profiles uBO replacement.
- Existing public Shields controls retain native state authority. The Sandium
  product exposes URL subscriptions, not upstream Brave component catalog lists.
  Bootstrap completion, effective subscription selection and original URLs feed
  uBO before ACK. Deleted/disabled entries must not be recreated. Download or
  compiled-source failure rejects readiness rather than silently omitting lists.
- Master/ad/cosmetic settings gate actual request, cosmetic, scriptlet and popup
  paths; this is source implementation, not verified UI parity. The two-state
  cosmetic On maps to BLOCK, not hidden Standard/Aggressive equivalence.
- Picker/clear/export use existing native custom-filter text. Cookies, shred,
  dark mode, typography and unrelated Shields functionality remain native.
- Counters use real blocked outcomes, bounded local batching and native document
  validation. They omit stale/frameless/root/overflow events and do not count CSS
  hides. They are not claimed identical to every uBO dashboard statistic.
- Settings refresh preserves ownership. Existing pages may use old rules during
  acquisition; removing already-applied cosmetic/scriptlet effects can require
  reload. No claim of instant visual restoration or measured zero overhead.

## Evidence still required

Native/Java/GN build success, installed ARM64 launch, real active owner, controlled
network block and exception, per-site controls, scriptlets, cosmetics, popup
behavior, subscription changes, custom rules, counters, persistence, fallback,
crash handling and navigation latency all require independent evidence. A runtime
readiness ACK is not a controlled filtering smoke test. Keep compile-only,
activated-build and observed-device results distinct.

No emulator work is part of this experiment after the user's stop instruction.
Do not clear a real profile to test persistence. Use a disposable profile for
upgrade/restart/rollback tests and compare rules, disabled/deleted subscriptions
and site choices exactly. Engine switching must not uninstall uBO or erase data.

## Provenance and immutable inputs

* Historical EXT0 Sandium base: `d0d024f` (tree shipped for #1292).
  The current composed phone baseline is selected by the build script, not this
  historical identifier.
* Brave core: `44a84b1f89d9a35287289d6a3d493e362f5a5123` / 1.98.62.
* Chromium: `d331de35ca8ab1358c7a17e4bd41627d55eaef51` / 156.0.8078.74.
* Upstream lead: https://github.com/brave/brave-core/pull/40242 (Draft).
* Upstream five-commit patch SHA256:
  `5e6fb6d65abd7093e004df3e0faf59fc5e5bebb3f54b87a1ca2cac450091f787`.
* Adapted patch SHA256:
  `5add076c9c5daa6a9bfba4f76ffa0bc3ed690a46a1732f11c8220297fb263a93`.

## Historical EXT0 stage

EXT0 initially provided only the extension infrastructure port. Earlier compile-
only runs did not package/activate a replacement; those historical results must
not be applied to later full candidate source. The current component/coordinator
and activation layers supersede the old “not bundled/not wired” implementation
notes. Detailed provenance remains in git history and pinned-patch-results.json.

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
