# SanB build feasibility and continuation

## Current evidence

- The connected workspace had 15 GiB free; `/tmp` had 5 GiB. The only
  other listed machine, SANDIVYA-PC, was offline. The saved cloud
  configurations are only the default, without any identified larger
  provisioned repository environment. No available long-lived SanB runner
  or separate remote service was observed.
- The existing source descriptor is explicit `rebase-incomplete`: the three
  verified Bare navigation patches are a tested slice, not an admitted Bare
  Android Desktop port. The real adapter's `verify` returned exit 1
  with “rebase or exclusions are incomplete,” without creating a receipt
  or using network. A native overlay cannot resolve missing Bare owners.
- The native overlay is finite reviewed input (~18 MiB, 1,674 exact paths),
  not proof of a native Android build or an independent compiled cache.
  Its existing focused tests pass. In particular the bundled EasyList is
  covered, but the 30-source catalogue is not 30 enabled lists. Current
  admission has no approved remote feeds.
- Official [Chromium Android build instructions](https://chromium.googlesource.com/chromium/src/+/main/docs/android_build_instructions.md)
  require an x86-64 Linux build host, at least 100 GB free, and ≥8 GB RAM
  (>16 GB recommended). An AMD x64 Windows PC is a viable **host candidate**
  only after an authorized Linux/WSL2 setup is available, capacity is measured,
  and the actual checkout/SDK/toolchain works there. Choose a Linux filesystem;
  Android ARM64 is a cross-compile target, not an Arm runner requirement.
- The already-used CircleCI worker shape `machine: large` is nominally
  4 vCPU / 15 GB RAM / 150 GB disk according to the
  [Linux machine table](https://circleci.com/docs/guides/execute/using-linuxvm/).
  `large.gen2` has the same nominal disk and 16 GiB RAM; xlarge also has
  150 GB nominal. None establishes actual free space or account entitlement.
  The [Free-plan 60-minute job ceiling](https://circleci.com/docs/reference/configuration-reference/#jobs)
  applies even when changing resource class. Working free-disk reserve must
  be measured. The present SanB 130 GiB guard is deliberate and might reject
  an ordinary worker after system overhead; do not lower it without measuring
  source, native output, and any archive headroom.
- A previous warm RawS restoration does not prove SanB timing, output
  compatibility, or permission to use those resources. Do not restore its
  canonical archive, use its object server/credential or change RawS signing.

## Safe progression after exact source acceptance

1. Prove the complete intended M158 Bare patch/disposition inventory and
   no-bundled-uBlock package changes. Bind Chromium/depot/SDK pins, the Bare
   donor and exact resulting staged source tree, the independent native
   overlay manifest and its whole integration digest. Stable `verify` and
   `prepare` identity must be identical. Any shared tracked owner needs
   reviewed 3-way or an exact composed postimage and clean upstream preimage;
   no fuzzy patches or provisional stages marked complete.
2. Run **only** the manual isolated SanB preflight first. Validate actual
   workspace capacity and tool access, then a bounded preparation/GN run with
   phase timings if it fits. Prove native host smoke and both host binaries,
   Android Java compilation on the same build graph, and the selected
   package/unsigned/no-uBlock graph. Source assertions or archive contents
   never replace native compile evidence.
3. Cold release compilation belongs on an independently approved persistent
   Linux worker or a separately authorized SanB remote-execution/CAS identity,
   not on a fresh ephemeral 4-vCPU worker by assumption. Start with one exact
   monitored build and reserve time/storage for validating the result. Empty
   SANB remote configuration is the current default. No new service, credentials,
   plan use or spend is assumed approved.
4. If the user instead explicitly approves testing an ephemeral staged chain,
   measure source/deps, compilation and **separately** pack/restore timings
   before committing to it. To progress between jobs, each slice must have
   evidence of more completed reusable actions and leave positive slack within
   each separate 60-minute cap. Store only independently owned `out/SanB-arm64`
   output under an exact versioned SanB-only fingerprint (Chromium/DEPS/
   depot/toolchain, Android ABI, effective GN args, admitted composed source
   digest, workflow/stage). Preserve dependency/action bookkeeping required for
   safe incremental use; validate manifest file modes/hashes, archive member
   paths, capacity and exact prior stage identity before use. No prefix fallback
   to other profiles or retries on corrupted evidence; no APK/receipt replacement
   after verification. Immutable cross-run cache, if ever used, needs explicit
   policy and separate namespace. Repeated source sync and 20+ GB layer movement
   may consume the useful build budget; quantify first.
5. CircleCI's [workspace rules](https://circleci.com/docs/guides/orchestrate/workspaces/)
   and [credit quotas](https://circleci.com/docs/guides/plans-pricing/credits/)
   matter: a large workspace consumes transfer/storage allotment and workers,
   and reruns can inherit stale workspace layers. Owner consent and actual
   organization allowance must be verified for a multi-stage experiment.
   Source/checkpoint isolation is required even on the same project.
6. Any first artifact must be labeled **unsigned, not installable**. The zip
   must contain only valid AArch64 ELF libraries, exact application identity,
   no known uBlock assets, no signatures or v4 sidecar, and verified SDK
   alignment. Do not use the existing RawS signing identity; a separate
   reviewed signer and phone tests are distinct milestones.

There is no admitted SanB build target, APK, signing run or overnight finish
estimate from current evidence. The fastest safe work now is the hard source
review/merge, not spending a CI job on the known failing gate.
