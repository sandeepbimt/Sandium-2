# Lean implementation ledger

## Candidate 1: recipe isolation and daily usage updater (2026-11-13)

Baseline: user-tested #1075, upstream repository commit `952b614ef375ec524954c27997d0e491936d21cb`.
This local development copy was initialized from the saved snapshot, not cloned upstream history. The local Git baseline is not an upstream commit.

### Implemented locally, not yet CI/device verified

- One Flow workflow retained; separate default experimental namespace `sandium-exp-single-v1-bridge-lean01`.
- Product manifest explicitly records all 13 required removal groups. Release readiness remains false.
- Compatibility digest binds pins, target/toolchain, active exclusions and effective additional GN flags.
- Exact recipe digest includes scripts, overlays, branding and pipeline configuration. Receipt completion requires matching recipe; same-profile implementation edits can still restore prior work.
- Cache discovery includes product compatibility. Old product completion receipts cannot satisfy the lean recipe. Initial seed import must be explicitly enabled for this new namespace; the canonical compressed base remains read-only.
- APK proof includes exact recipe, source revision and SHA-256. It is issued only after successful compilation, or validated against an existing proven restored APK. A stale or mismatched restored APK is discarded, while its other build outputs remain available for dependency-based reuse.
- Native dependency audit checks the generated `//brave:brave` dependency closure for selected Batch A implementation targets; buildflag metadata is not mistaken for implementation. The report explicitly does not claim APK/runtime verification.
- First new exclusion candidate: `enable_brave_stats_updater=false`, removing the daily usage updater and its exclusive parameter `.cc/.h` files from the source set. Android Java restart invocation/declaration and native JNI function are also removed, preserving the Safe Browsing JNI method. GN audit requires those implementation sources to be absent. This does **not** remove P3A, remote crash reporting or all shared statistics helpers. Reporting group remains incomplete.

### Pinned-source evidence

Pin `44a84b1f89d9a35287289d6a3d493e362f5a5123`:
- `browser/brave_stats/buildflags.gni`: declared updater build argument.
- `browser/brave_stats/BUILD.gn`: updater implementation files conditional on it; shared features remain; updater parameters are now moved behind the updater flag after exhaustive reference search showed only the updater and its tests use them.
- `components/email_aliases/buildflags/buildflags.gni`: Android excluded, not a configurable GN argument.
- `components/brave_wayback_machine/buildflags/buildflags.gni`, `components/speedreader/common/buildflags/buildflags.gni`, `components/tor/buildflags/buildflags.gni`: Android excluded by upstream defaults.
- `components/brave_talk/buildflags/buildflags.gni`: enabled upstream; Sandium already excludes it.
- `components/web_discovery/buildflags/buildflags.gni`: Android native and general/UI flags both required; Sandium already excludes both.
- `browser/sources.gni`, `renderer/sources.gni`, `browser/web_discovery/sources.gni`: guarded dependencies for those modules.

Base source URL: https://github.com/brave/brave-core/tree/44a84b1f89d9a35287289d6a3d493e362f5a5123

### Still pending

- Independent foundation review, official CI config validation and real pinned-source GN execution.
- Full compiler/link/APK/resource proof and fresh-install/upgrade-device checks.
- First actual new-delta restore roundtrip, still unproven by #1075's shortcut.
- Actual removal work for AI, Wallet/Web3, VPN, Rewards/Ads, News, Playlist, remaining reporting services, and residual Android integration cleanup.
- Android shared-source/resource references require source-level adaptations; mere GN flags are not enough.

No claim is made that the final lean product is ready, or that source-level exclusion alone proves no network activity.
