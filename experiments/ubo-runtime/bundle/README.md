# Pinned complete uBlock Origin release payload

**Preparation only. This neither installs nor enables uBO, disables Brave, nor
changes the Android build.** A compiled APK must not be called uBO-enabled based
on this payload's presence.

Official stable release: https://github.com/gorhill/uBlock/releases/tag/1.76.4
Source commit: `3cca944b4a4c5f3473d6cb7153e6fb99b5f7d1db`.
`dist/version` in that source and the built Chromium manifest both say `1.76.4`.
The source platform manifest is a template and must not be used for versioning.

`lock.json` pins the exact official release ZIP URL, SHA256, complete 668-file
inventory, source archive URL/checksum, and normalized output checksum. The archives are held only in an ignored local download cache, not Git.
No floating tag/latest lookup occurs. Normal preparation is offline; explicit
`--fetch` downloads only these two locked URLs, with HTTPS-only redirects, a
16 MiB per-archive limit, a 60-second download budget and verified atomic cache
publication. Corrupt existing caches fail closed instead of being replaced.

Run:

```sh
# CI or first materialization only; omit --fetch for offline reuse.
python3 experiments/ubo-runtime/bundle/prepare.py --cache-dir /tmp/ubo-cache --fetch \
  --output /tmp/ubo-bundle.zip --source-artifacts /tmp/ubo-source-artifacts \
  --integration-details /path/to/exact-sandium-integration.patch
python3 experiments/ubo-runtime/bundle/test_prepare.py
```

Preparation validates the complete original archive before writing anything,
removes only its enclosing `uBlock0.chromium/` path, and repackages all files with
sorted paths, fixed metadata, and uncompressed ZIP entries for reproducibility
across zlib versions. It refuses an existing output. Content is unchanged, including
filter assets, scriptlets, background runtime, translations, fonts and notices.
The normalized ZIP is for a future APK resource/extraction loader, not a signed
CRX and not presently connected to a loader.

## License and reproducibility boundary

uBO is GPLv3; preserve LICENSE.txt and source correspondence when distributing a
modified/embedded version. Its third-party libraries, fonts and bundled lists
retain their own notices in the unmodified release. Do not claim the entire
browser's license is settled by this file; integration/distribution must retain
applicable upstream obligations and disclose any added bridge changes.

The official **release payload** is the reproducible packaging input. This tool
reproduces its normalized packaging, not the upstream compilation/minification
process. The source archive supplies source/build scripts at the exact release
commit; upstream build scripts may fetch separately maintained filter assets.
The exact assets actually used here are locked and retained in the release ZIP,
not re-fetched from moving list URLs. Runtime list-update policy is a separate
integration decision; this preparation does not alter uBO defaults.

The release is downloaded from upstream HTTPS and locked by observed digest.
This is provenance/checksum verification, not independent signature validation.
Actual MV2 Android background, webRequestBlocking, document-start all-frame
scriptlets, Shields bridge, storage/restart and exclusive engine behavior still
require implementation and testing.

## CI integration contract

The build caller must invoke the explicit materialization command above, then
include the resulting source-artifact directory alongside the APK in CircleCI
`store_artifacts`. Pass the exact integration diff/build instructions, not a vague
status note, as `--integration-details`. The directory contains the matching
source archive, GPL license, upstream lock and supplied integration details.
This helper does not alter CircleCI config or by itself establish full compliance
for a future modified integration. Tests expect verified archives in `.cache/`;
materialize that directory explicitly before running them on a new machine.
