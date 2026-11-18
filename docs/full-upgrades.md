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

### Android host dependency recipe

RawS follows the pinned Chromium Android guide at
https://chromium.googlesource.com/chromium/src/+/d331de35ca8ab1358c7a17e4bd41627d55eaef51/docs/android_build_instructions.md:
run `build/install-build-deps.sh` (with `--no-prompt` for CI), without the legacy
`--android` flag. At this revision, `build/install-build-deps.py` marks that flag
deprecated and uses it solely to enable `lib32`; the guide reserves `--lib32` for
32-bit builds. RawS builds ARM64. This removes the unnecessary forced i386
package family without inventing an unsupported minimal host package list.
The standard host dependencies remain required for Android build tools.

Run #1376 hit the 15-minute installer bound before any compilation; its log ends
at package configuration/libc triggers, not a compiler error. The dependency
recipe change and independently cached APT archives are prospective fixes;
a successful fresh-worker install and APK build must still verify them. APT
archives reduce downloads, but do not preserve installed root-filesystem state
between workers. Do not skip installation merely because an archive cache exists.

### Dependency installer retry after #1377

#1377 verified source setup in 10m58s and live dependency logging, but host
installation again hit the 15-minute bound before compilation. Package output
paused for minutes and resumed around timeout; this does not identify a specific
package as the cause. The next candidate removes redundant outer sudo (the pinned
installer invokes sudo itself), disables apt's pseudo-terminal, and supplies closed
stdin to the unattended installer. Process state and wait-channel diagnostics
separate stalled installation from a child retaining the output pipe. This is a
CI compatibility hypothesis, not a validated fix until a run passes installation.
The dependency time bound and strict compilation/checkpoint rules are unchanged.

#1378 validated the unattended dependency change: installation completed in 67
seconds and runhooks in 24 seconds. It then exposed a first-use adapter error:
`.sisorc` is an optional local Siso configuration and was absent in clean Chromium.
Unlike a restored Brave checkout, a fresh RawS checkout must create its initial
ninja configuration explicitly before applying the Full-mode options. This
failure was before GN or compilation; no APK or accepted checkpoint was produced.

#1382 passed remote configuration, but GN exposed the next fresh-checkout
contract: DEPOT_TOOLS_UPDATE=0 skips gclient's usual bootstrap, while vpython3
initializes only its own CIPD runtime. GN and autoninja invoke the selected
checkout's python-bin/python3, which requires bootstrap_python3's manifest.
Use pinned upstream ensure_bootstrap without moving its Git revision; verify
that revision and the real wrapper Python/GN before compiling. Dependencies
completed in 68 seconds and hooks in 20 seconds. No compiler actions or accepted
checkpoint were produced by this run.
