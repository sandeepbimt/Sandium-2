# Explicit regular-profile activation candidate

Foundation runs stay default-off. Set CircleCI boolean pipeline parameter
`sandium_ubo_activate_candidate=true` only for the isolated
`experiment/ubo-runtime` branch to build a candidate with BOTH
SandiumUboRuntime and SandiumUboExclusiveRouting default-enabled. The script and
activation overlay independently reject other branches. This does not enable
features on the normal phone branch or claim functional success.

Requires loader prerequisite fix4206027. The last overlay evaluates command-line
overrides and declared feature defaults on the not-yet-installed FeatureList
instance. Explicit disable of either feature wins. Both scheduling and late
materializer callback also require exclusive routing, preventing a runtime-only
configuration from activating uBO alongside native filtering. All four Android
prerequisites remain enabled together through the existing pre-init path.

Apply order: loader, Shields, routing, startup, request policy, activation, status
(then GN). Reset status FIRST, then activation, request policy, startup, routing,
Shields, loader, before baseline
source reset/audits. Ownership receipts reject unowned changes. Baseline
runtime-off checks remain before all overlay application; they are not falsely
applied to activated postimages.

Private/incognito profiles explicitly remain native-only: candidate manifest sets
incognito=not_allowed, disk payload hashes are recomputed, and loader scheduling
and completion reject OTR profiles. This is a disclosed capability gap versus
full uBO parity, not a private mode implementation. Chromium's pinned incognito
manifest handler recognizes kNotAllowed and prevents incognito enablement.

Build artifacts record requested candidate activation, private=NATIVE and runtime
owner=UNVERIFIED. Actual owner may be uBO only after native readiness/ACK gates;
startup timeout must expose native fallback, and lost selected runtime is
failclosed. User-facing status is supplied by the Shields/status integration,
not inferred from this build switch. No native fallback may be described as a
successful uBO replacement.

Tests compile the emitted pre-init boolean expression across all64 combinations
of paired defaults/enable/disable overrides, verify branch refusal, exact paired
feature state, private manifest policy, replay/reset and source composition with
4206027 loader plus current Shields/routing/startup. Native build/device testing
still remains necessary.
