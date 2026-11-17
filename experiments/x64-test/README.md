# Native x86_64 emulator build: pinned feasibility audit

This is a generated isolated experimental pipeline. The ARM source scripts and
checkpoint identities remain unchanged. Native dependency sync and GN compilation
are not locally verified; the first isolated CI run is the integration test.

## Verified pinned source

`brave/build/commands/lib/config.ts` outputDir omits architecture suffix for x64:
`out/android_Release` (NOT `android_Release_x64`).
`brave/build/config.gni` appends target_cpu to BraveMono output:
`out/android_Release/apks/BraveMonox64.apk`.
`build/commands/lib/buildArgs.ts` explicitly handles Android Release x64.
Use `--target_arch=x64` and keep `enable_android_secondary_abi=false`.

## Required safe pipeline split

1. Keep immutable ARM reference restore and verification intact as source bootstrap.
   Do not relabel an ARM manifest as x64; ARM object files cannot be reused as x64.
2. Generate a fresh separate x64 GN graph after pinned dependencies/source overlays.
   Synchronize architecture-specific dependencies if required. Do not silently
   retain an ARM gclient/checkpoint-preservation decision for x64 setup.
3. Every output consumer must use the x64 directory: prepare, graph validation,
   remote smoke, bounded build, checkpoint capture/shards/archive, restored APK
   validation, export and completion. Existing `.circleci/scripts` has at least
   eleven hardcoded consumers; `.circleci/experimental-steps` has more.
4. Stage 2+ must restore exact x64 workflow/revision handoff, never normal ARM or
   previous test architecture. First-stage ARM bootstrap validation and later x64
   handoff validation need separate contracts.
5. Write only x64-specific branch/workflow handoff/marker keys. Keep immutable
   normal reference and promotion disabled. Later stages must halt once verified
   APK exists or any stage fails, as in the user's production contract.
6. Retain signature/package/removal/branding gates and add actual ELF ABI validation.
   Naming an APK x64 is insufficient. `contract.py` validates x64 ELF headers,
   GN target and exact handoff provenance, with three regression tests.
7. Expect new target-architecture compile work. Existing BuildBuddy action cache
   may reuse host tools, Java, resources and compatible actions, but no completion
   deadline is established. Five slices may be insufficient for a cold x64 graph.

A blind replacement of `arm64` with `x64` would break output paths and reference
verification. A runtime script rewriter after audited preflight is also unsuitable:
verify the generated architecture-specific scripts/configuration before dispatch.
No translation guard is required for native x64. Keep phone ARM artifact separate.

## Generated dispatch candidate

`build_config.py` statically derives `.circleci/x64-test/config.yml` and scoped
script copies from the successful native-status configuration. All input/output
hashes and deterministic regeneration are checked before each stage. The active
config must be copied from that generated file on `experiment/native-x64-api15`
only. No normal reference promotion is present.

Stage 1 verifies the original ARM fixed source bootstrap, then the derived prepare
forces Brave target-aware x64 dependency sync and GN generation. Continuations
accept only exact x64 workflow handoffs. The archived x64 tree excludes copied ARM
output objects, but stage1 preserves them locally and requires 30GiB free before
compilation. Export adds x86_64 ELF checks before existing product/signature gates.

13 tests include real shard archive/restore retaining x64 objects and excluding ARM,
shell syntax, deterministic derivation, cache isolation and ABI validation. No
claim is made that a native Android build or emulator execution has passed yet.
