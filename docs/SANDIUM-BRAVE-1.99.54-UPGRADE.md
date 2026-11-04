# Sandium Brave v1.99.54 upgrade

## Source pins and identity

- Brave Core: `v1.99.54`
- Chromium: `157.0.8103.30`; Stage 1 resolves the immutable commit SHA and records it in `source-pins.env`.
- Build: optimized Android Release, ARM64.
- Package: `com.brave.browser_default`.
- App label: `Sandium Browser`.

The successful v1.98.62 / Chromium 156 reference at commit `3c8004b` remains untouched. The new Chromium source requires a Full Mode upgrade and new GN/Ninja graph. The new reference must not be promoted until APK, workspace, Siso state, manifest and every archive shard have passed validation.

## Native ad filtering

Keep Brave Shields and its native Rust ad-blocking engine. Brave's default resources contain uBlock Origin-compatible filter rules; this patch does not bundle the uBlock extension or replace Brave's engine.

The v1.99.54 fix removes the empty-provider early return in `UpdateFilterLists`. That old path could return success without requesting Brave's base adblock resources and filter-list catalogue. The Sandium patch always requests the base resources/catalogue, uses Brave's development component feed for this non-official app build and refreshes the Android Content filters UI when the component catalogue is ready.

The UI uses a bounded update/poll sequence: up to 3 component update requests and 12 one-second catalogue polls per request. Manual UPDATE uses the same flow. It does not silently enable many optional community lists; users remain in control of additional lists so browsing performance and false-positive risk are not needlessly degraded.

Only Brave's component updater receives the development-feed/allow-Brave-components override. Chromium's global component-update policy is not removed.

## ARM64 APK size

Keep Brave's `create_dist` target and `AAB -> Bravearm64Universal.apk` conversion:

- `target_arch=arm64`
- `target_android_output_format=aab`
- `android_aab_to_apk=true`
- `enable_android_secondary_abi=false`
- `is_official_build=false`
- `android_channel=default`
- `brave_channel=development`
- `chrome_public_manifest_package=com.brave.browser_default`

Brave's CI build helper can force a second ABI when CI outputs an APK directly. The AAB-to-APK path avoids that direct-APK override. A strict package audit records ZIP entry sizes, native library size, largest entries and ELF machine types, and fails unless every packaged native library is in `arm64-v8a` and has an AArch64 ELF header.

The upstream Brave release asset in the supplied screenshot is 203 MB. That is the comparison target, not a result to assume for the Sandium build; actual size is reported from the generated APK.

## Pipeline preparation

- Cache Node 24.16 and PNPM 11.11 together under a versioned CircleCI cache key.
- Stage 1 resolves Chromium's pin; later stages validate and reuse the SHA from restored `source-pins.env` instead of repeating `git ls-remote`.
- Keep the existing BuildBuddy/Siso setup and required flags: `use_remoteexec=true`, `use_siso=true`, `use_reclient=false`.
- Full Mode build slices are 30 minutes, maximum five sequential stages; each stage must restore its predecessor and build only remaining targets.
- Stage restoration verifies the Sandium adblock patch and branding without rewriting restored assets.

## Acceptance criteria

1. Brave/Chromium pins match v1.99.54 / Chromium 157.0.8103.30.
2. The component updater requests Brave's filter resources/catalogue; Content filters populates from the component feed.
3. Release APK ZIP integrity, APK signature, package ID and Sandium label pass.
4. APK contains only `arm64-v8a` native libraries with AArch64 ELF headers.
5. The APK size report is archived with the APK.
6. Actual Siso remote execution and useful restored Ninja/Siso state are verified; a cache hit alone is insufficient.
7. All archive shards, manifest and workspace restore validate before promoting the new reference.
