# RawS Full lifecycle and Chromium upgrades

RawS reuses the established Full checkpoint implementation: immutable sharded base,
ordered deltas, exact receipt binding, sequential reconstruction, expiry validation,
local compressed-input reclamation, and verified maintenance publication. Adapted
files and source hashes are recorded in `.circleci/full-vendor-provenance.json`.
These are code-level tests, not proof that a full Chromium build has finished.

## Normal pipeline
Five serialized stages, each with at most 25 minutes of strict BuildBuddy Siso
execution (including the cold remote smoke). Source sync, OS packages, hooks,
restore and checkpoint transfer are additional time. Full safety reserves can
shorten the first stage, not overrun the one-hour worker. Only intentional timeout
is resumable; real failure stops subsequent stages. Verified APK completion skips
large checkpoint work and later stages. The first stage bootstraps pinned Chromium
when this **RawS-only identity** has no accepted checkpoint, then compiles before
archiving. No Brave checkpoint, source overlay, or output is accepted.

The sharded fresh base uses eight independently verified shards, five archive
workers, and up to eight restore workers. Later stages save only incremental
changes. Native cache saves must be read back and hashes checked before the
candidate becomes the accepted head. Failed publication preserves the old head.

## Expiry protection
Jobs explicitly request 15-day cache retention. Receipts use a conservative
14-day dependency deadline; restoring an object or saving its existing immutable
key never extends that deadline. Maintenance becomes due two days before the
oldest dependency expires or as the bounded layer chain approaches capacity.
The separately serialized `RawS checkpoint maintenance` workflow verifies the old
chain, saves refreshed objects under **new keys**, clears downloaded copies,
reads back the new remote objects, verifies them, then publishes the new receipt.
The previous accepted receipt is preserved. A missing/expired chain fails closed;
it is not silently reset to base. Caches are not permanent archives. Maintenance
consumes worker time, network, and storage, so it is not run every build.

## Chromium upgrades
1. Pin official Chromium revision/version and depot_tools commit in
   `upstream.lock.json`; review DEPS/toolchain and upstream security notes.
2. Check the feature manifest and small version-specific patches independently.
   Keep Sandium feature modules outside upstream source, with explicit adapters.
3. Run tests and regenerate `ci/cache-identity.txt`. The identity includes the
   source/tool pins, GN settings, remote recipe, patches, and feature manifests.
4. A changed compatibility identity creates a new RawS checkpoint namespace.
   Do not layer a new compiler/toolchain/source tree onto the old output chain.
   BuildBuddy may reuse content-addressed actions only when their inputs match.
5. Build and test the candidate APK before changing a release pointer. Retain
   the old source lock, branch, and APK for rollback. Cache retention alone does
   not constitute a rollback archive.

No promise of patch-free Chromium updates: upstream API changes require adapter
and feature tests. Initial baseline has no uBO, Sandium branding, or custom UX.
