# Sandium bundled Brave adblock DAT baseline

## Purpose and build mode

This change is a **Full Mode** native integration. It changes Brave C++ and the pinned Rust adblock engine data path. It must run only on `feature/sandium-filter-bootstrap-full`, which is already routed through the five-stage Full Mode workflow. The ordinary two-state Fast branch remains free of this native cache/asset overlay.

Pinned inputs:

- Brave Core: `v1.98.62` / `44a84b1f89d9a35287289d6a3d493e362f5a5123`
- Chromium: `156.0.8078.74` / `d331de35ca8ab1358c7a17e4bd41627d55eaef51`
- Rust adblock runtime and generator: `adblock 0.13.3`

## Runtime behavior

Brave retains its existing profile cache at `<profile>/adblock_cache/engine1.dat`.

1. Brave first reads the profile cache using its normal asynchronous DAT cache manager.
2. A profile DAT that deserializes successfully is left untouched. The packaged asset is not consulted and cannot overwrite a valid, newer user cache.
3. Only when the additional-engine profile DAT is missing or rejected by native deserialization does Sandium asynchronously read `assets/sandium/adblock/engine1.dat` from the APK.
4. The packaged DAT is passed through Brave's normal `AdBlockEngineWrapper::LoadDAT` deserializer. It is copied to the profile cache only after the native engine reports successful deserialization.
5. After a packaged DAT succeeds, the provider manager's one-time startup notification suppression is explicitly released. This lets cached/downloaded subscriptions progressively replace the bundled snapshot while the baseline protects the first navigation; no homepage reload is requested.
6. If the APK asset is missing, empty, or rejected, Brave falls back to its existing subscription-provider aggregation path and explicitly releases startup suppression for the additional engine, so live lists can still activate.

The baseline is `engine1.dat` (the additional/subscription engine). Brave's `engine0.dat` default engine remains unchanged. The asset is uncompressed so `base::android::OpenApkAsset` can map it from the APK without extracting it first.

Brave continues loading redirect/scriptlet resources separately through its existing `resources.json` resource provider. The DAT contains serialized network/cosmetic engine state; it is not represented as a substitute for Brave's resource component.

## Snapshot generation and cross-stage reuse

`.circleci/scripts/generate-sandium-adblock-dat.py` reads the existing 29-entry Sandium subscription catalogue and downloads filter snapshots into:

`out/android_Release_arm64/gen/sandium_adblock/`

The Rust generator in `.circleci/scripts/sandium-adblock-datgen/` is built offline against the pinned Chromium vendored crate tree. It uses the exact `adblock 0.13.3` API used by Brave: `FilterSet`, `ParseOptions::default()`, `Engine::new_with_filter_set()`, `Engine::serialize()`, and `Engine::deserialize()`.

Before publishing the output, the Rust generator deserializes its own DAT using the same crate version. The Python wrapper records the source hashes, byte counts, URL/title/license attribution, Brave/Chromium pins, DAT SHA-256 and engine rule counts in `sources.json` and `snapshot.json`.

- The source snapshot is reused unchanged between stages of the same CircleCI workflow.
- A validated snapshot no older than six hours can be reused by a subsequent workflow.
- Existing validated source files can be used as a clearly logged fallback for up to seven days if an upstream filter host is temporarily unavailable.
- Source files, DAT, source manifest and Cargo target output live under the staged `out` workspace, so they travel with the normal Full Mode checkpoint.
- A corrupt or incomplete source/DAT checkpoint fails validation rather than silently being treated as a valid APK seed.

The `brave/BUILD.gn` target `sandium_adblock_assets` packages the DAT and `sources.json` at the stable APK paths `assets/sandium/adblock/engine1.dat` and `assets/sandium/adblock/sources.json`, with compression disabled.

## Filter-list redistribution notes

The selected subscription catalogue has 29 sources. The published uBlock Origin filter-list license inventory identifies two of the selected feeds as non-commercial:

- Peter Lowe's list: McRae GPL with non-commercial terms.
- Dan Pollock's hosts list: informal attribution / non-commercial terms.

Those two sources are **not included in the APK baseline**. They remain present in Sandium's existing profile subscription catalogue and can still be fetched by the browser's normal subscription mechanism. The other 27 bundled sources carry the license/attribution information recorded in `sources.json` (including GPL-3.0, CC-BY-SA-3.0, CC-BY-3.0 and CC0-1.0 entries).

The filter license inventory is a source reference, not legal advice. Review the individual upstream terms before public redistribution of a Sandium release.

## Validation gates

Offline script tests:

- `test-sandium-adblock-dat-cache.py`: transformation idempotency, cache-miss/invalid-cache fallback, write only after native deserialization, provider-notification release after packaged DAT success, uncompressed asset destination and no homepage warmup hook.
- `test-sandium-adblock-dat.py`: crate pin, expected filter-source count, non-commercial exclusions, license mapping and Rust serialize/deserialize source checks.

Full Mode CI must additionally prove:

- all patchers apply to the exact pinned Brave Core revision;
- Rust `cargo run --offline --release` builds with the vendored toolchain and emits a round-trip-valid `engine1.dat`;
- GN accepts the generated asset paths and Ninja/Siso rebuilds the native cache manager and APK packaging targets;
- actual Siso remote execution is observed under `use_remoteexec=true`, `use_siso=true`, `use_reclient=false`;
- checkpoint state and generated `out/gen/sandium_adblock` files are restored and reused in later stages;
- final APK is ARM64 Release, ZIP-valid and installable.

No successful APK is claimed until these CI and install checks pass.
