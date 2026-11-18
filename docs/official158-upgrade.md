# Chromium 158 official candidate

Verified 2026-11-18: Android Stable 158.0.8127.42, Chromium
`52bdd21723d5db0c9ab11716d38feac74828cf84`. Exact canonical chrome/VERSION,
ChromiumDash metadata, and SHA256 hashes of reviewed official source files are
recorded in [official158-provenance.json](official158-provenance.json).
The exact depot_tools pin remains `fed8b43f48c4f4c2ac0c34aafbf0ec07a4e600cb`.

The isolated branch is `raw-sandium/official158`. All branch gates/filters follow
that branch; only `run_raw_full=true` is intended for this build. Other parameters
remain false. It uses the established Full pipeline, not a test-only pipeline.

## Official inputs and gates

The only product GN change is `is_official_build=true`. Symbol level 1 and strict
BuildBuddy/Siso configuration are retained. No optimization is disabled or new
browser feature enabled. Official DEPS defaults `checkout_pgo_profiles` to false;
the lock now explicitly sets it true through gclient custom_vars, enabling the
pinned optimization hooks, including V8 profiles. ARM64's PGO profile comes from
the DEPS-pinned `chromium/chrome/android/orderfiles/arm64` CIPD package; its exact
instance is recorded in provenance. Upstream update_pgo_profiles.py selects
`chrome/android/orderfiles/arm64/pgo_profile.arm64.profdata` for ARM64.
The pinned Clang source expects `llvmorg-24-init-14453-ge063be79-1`.

GN generation now fails on unused arguments. Before compilation, effective GN
settings must show official release, ARM64, ThinLTO and the retained remote
configuration. The native base graph must have ThinLTO and a nonempty exact
upstream-selected profile (PGO or upstream Android AFDO); it cannot pass with
profile optimization disabled. The receipt records the actual profile SHA256,
DEPS SHA256, Clang revision, args hash and source/tool locks. GN and the pinned
hooks perform their existing toolchain consistency checks. The pre-existing
Siso adapter's single insertion anchor was checked against exact 158 source.
Real GN execution and compilation still require the CI source checkout.

## Preservation and costs

The source lock, args, acquisition recipe and official-input gate participate in
`ci/cache-identity.txt`, creating a new `raws-full-v1-<fingerprint>` scope. No old
source/output/checkpoint receipt is an accepted fallback. Only BuildBuddy actions
with identical content-addressed inputs can naturally reuse results; expect a
cold source acquisition and substantial or complete rebuild, including new
ThinLTO/link and profile costs. No runtime or credit-saving estimate is proven.

The five serialized Full stages retain their maximum 25-minute strict-remote
slices, early verified-APK delivery, eight archive shards (at most five concurrent
archive tasks, up to eight restore workers), sequential deltas, readback-before-
publish and 15-day cache requests. Receipt expiry remains conservatively 14 days,
with maintenance due two days before dependency expiry. These are expiring
checkpoints, not permanent archives. The separate final archive remains opt-in;
this run does not trigger it or promote its receipts.

Protected 156 final archive: pipeline #1390, workflow
`dc852993-dbb8-440f-85dc-47cdacdfd24f`, commit
`c0d050f4a5cbfd07ea00004de1939c35247f54f3` on `raw-sandium/bootstrap`.
It passed compile, pack, all eight remote shard readbacks and a fresh unchanged-
target probe (15 seconds, zero build steps, identical signed ARM64 APK).
That probe allowed remote execution; it is not an offline-completeness certificate.
No existing baseline head, final receipt, branch or Sandium #1391 work is changed.

Rollback is to the preserved 156 branch/artifact, not a mixed 156/158 checkpoint.
APK/device behavior, build cost and CI-scale profile/LTO behavior remain pending.

## Pre-run validation

All 118 unittest cases pass, including existing real archive/restore fixtures and
new fail-closed official settings, exact-profile and configuration-regeneration
tests. Python compileall and git diff --check pass. Independent read-only review
found no blocking defects and separately checked GN's --list --short semantics,
base target optimization configs, namespace guards and unchanged Full lifecycle.
The CircleCI CLI is not installed here; local YAML/regeneration and workflow
tests pass, while server-side config acceptance is checked on the actual run.
