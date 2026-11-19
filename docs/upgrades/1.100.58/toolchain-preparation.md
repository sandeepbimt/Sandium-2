# Target-specific Full-U 158 toolchain preparation

Owner entrypoint: `.circleci/upgrades/toolchain.py prepare|gn|verify --root PROJECT`.
It requires the exact owned source-synced receipt from `source.py`, Brave core
`bd6d26d1bced03c17a98baa86d2cd3425d543d1b` and Chromium
`52bdd21723d5db0c9ab11716d38feac74828cf84`. The caller owns the overall process-group
deadline and verified local Node/pnpm PATH. No legacy 156 clone/sync, global npm
installation, global pnpm configuration, or graph-reuse branch is invoked.

## Reviewed actual target changes

* Compiler diagnostic assignment in `build/config/compiler/compiler.gni` is still
  upstream's parent-relative `rebase_path`. Normalize to output-local
  `clang-crashreports`; exact full-file pre/postimages are checked.
* Brave's `brave_custom.py` generator has changed formatting since 156: tuple
  argument and trailing commas. The old exact marker fails. The new reviewed
  transform binds `wrapper_path`, writes the same template and sets mode0755.
  The current generated wrapper also receives mode0755.
* Brave's Siso configuration retains the `__remove_labels_from_platforms` seam.
  Patch both canonical source and generated copy to keep canonicalization and
  include real `./args.gn` in remote action input trees. The generated copy is
  absent from the Chromium Git tree; its reset owner is generated-overwrite.
* Actual `sisoUtils.ts` retains the native exec-stream, flush timeout and byte
  stream flags plus googlechrome rules. Preserve them; add remote-link and cache
  writes. Fail on readonly/local-only conflicts, never silently override them.
* Target Chromium google.star image is pinned by full-file SHA256 and remains
  `docker://gcr.io/chops-public-images-prod/rbe/siso-chromium/linux@sha256:d7cb1ab14a0f20aa669c23f22c15a9dead761dcac19f43985bf9dd5f41fbef3a`.
  Its actual configure_siso.py still accepts the reviewed REAPI instance/address,
  backend and credential-helper arguments. No generic distro image is substituted.
* Native build entrypoint is now `build/commands/scripts/build.ts`; util.js became
  util.ts. Actual native build calls GN then target execution, accepts --ninja,
  and util.ts consumes extraNinjaOpts. Use `--force_gn_gen` plus `--ninja=n` for
  unconditional native GN/dryrun without compilation. This is not an old graph
  compatibility claim. Runtime Siso preparation is reapplied afterward in case
  native tools regenerated configuration.
* Actual `envConfig.ts` still exposes constructor(configDir)/getAny, and
  buildArgs.ts still declares the four service configuration names. Reuse the
  non-authenticating placeholder resolver, preserving all existing resolved
  values. This grants no Brave service access and does not bypass a payment gate.
* GN keeps official ARM64 release, single ABI, ThinLTO, PGO0, Siso+remoteexec,
  no reclient, no updater, and the reviewed removal args. The existing resolved
  official/compiler/Skia gate runs after the fresh graph. No graph-ready claim is
  made on dryrun or resolved-gate failure.

## Ordering and evidence

Product owner resets declared inputs and applies all product overlays first,
then `prepare`, then `gn` (which calls `verify`). Source-only and product-preparing
checkpoints remain distinct from build-ready. Exact four-source fixtures were
read from the two pinned Git clones; fixture SHA256s are independently checked
against helper constants. Six host tests prove exact transforms, replay,
unknown-drift rejection, remote policy and GN command construction. These tests
are **not actual GN, BuildBuddy, compilation or APK evidence**. Actual generated
wrapper/Siso/host-dependency availability and full GN execution remain live
integration gates. No CI was started by this work.
