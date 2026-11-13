# Sandium – Flow: legacy-base bridge candidate

**Isolated local candidate; do not push or run until independent review completes.**
Active orchestration is `.circleci/bridge/driver.py` and `.circleci/config.yml`.
Old conversion modules remain only for shared helpers/regression tests, not active
seed/build steps. This document supersedes conversion details in EXPERIMENT.md.

## Actual workflow

1. Seed job restores the original canonical eight compressed shards READ ONLY,
   verifies them, then saves those identical compressed files to a dedicated
   experimental base cache. It does **not** extract, hash or convert 68 GiB of source.
   Candidate base receipt is published only after the base cache save succeeds.
2. Each build job restores accepted head, exact unchanged B and all ordered deltas.
   Existing shard verifier/restore verifies B compressed hashes. Delta archive and
   included-file hashes and ordered parents are verified before use.
3. Same-job metadata inventory is recorded before source preparation or build.
   Existing pinned source/GN/Siso checks, dependency installation, crash patch,
   feature overlays and bounded real build scripts remain in the active path.
4. Changed/new files, deletions, symlink targets, metadata and hardlink topology are
   captured after writer checks. Only candidate changed files are hashed/archived.
5. Artifacts are uploaded before APK-success receipt. New delta cache and any
   required base refresh must save successfully before accepted head publication.
6. Next stage and next run repeat B + every accepted delta, never B-only fallback.

The native cache boundaries are explicit save/restore steps, not mocked commands.
Local tests simulate native cache transfer with filesystem copies; no live native
cache performance or job serialization proof is asserted by those tests.

## Incremental detection boundary

Compare per-job device/inode, type, size, ctime_ns, mtime_ns, mode, symlink target
and hardlink membership. A normal same-size rewrite restoring mtime changes ctime
and is captured. Inventories are bound to root device/inode and workflow/build ID,
and never compared across machines/restores. Source preparation is inside scope.

This relies on a trusted ordinary Linux filesystem and stopped writers. It is not
cryptographic detection of silent unchanged-file corruption or privileged/kernel
manipulation of metadata. Extended attributes, special files and external
hardlinks fail closed; ownership, ACLs and sparse physical layout are not retained.
Scope is brave-work only. User-data/secret eligibility and authenticated cache-writer
protection remain unverified; review flag is an operator attestation, not protection.

## Bounded retention/rollup

Receipt leases are conservatively 14 days against native cache retention 15 days.
Missing/expired base or delta fails before build; it never silently reseeds.
Within 2 days of expiry, B is re-saved from the exact already verified compressed
shards under a new immutable key, keeping the same content identity. Otherwise
base save uses the existing immutable key and skips writing. It does not recapture
or convert the decompressed tree.

At seven prior deltas, or when a delta is within 2 days of expiry, capture rolls up
prior deltas plus the new one into one delta against B. It reads/validates delta
archives only, not unchanged B contents. Latest entries/deletions and complete
hardlink groups are preserved. Base+seven deltas is the bounded incoming layout.
Rollup/refreshed-base maintenance is automatic within Flow, not a second mode.
A long idle period beyond cache expiry still needs explicitly authorized reseed.

Native immutable caches do not implement distributed compare-and-swap. The entire
workflow remains under one serialized job-group. Receipt checks refuse old pipeline
reruns, wrong stage/source, wrong parents, prefix collisions and nonadvancing heads.
Manual group release or unauthorized cache writers can violate assumptions; no
canonical promotion is attempted. Default run/review flags remain false, namespace
is sandium-exp-single-v 1-bridge-crash 01, canonical caches never receive save steps.

## Budget and storage uncertainties

Capture has 900 s cap, with 600 s reserved for native saves. Build budget is at most 1200 s
and also limited by first-gate+3300 s minus 900 s capture,600 s saves,60 s shutdown.
This is a conservative deadline policy, not a measured feasibility prediction.
Legacy verification/restore have at most 1800 s parent deadline and bounded process-
group termination. Their no-output limit 35m is longer than that deadline because
individual tar operations do not emit byte progress; no heartbeat is used.

Inventory/hash/copy/rollup counters report completed work. Native CircleCI saves
and OS dependency preparation are not globally killed by the Python watchdog.
Native cache archive scratch and throughput remain unknown. Metadata inventories
for 1.58 million entries can consume significant RAM/time. B compressed+source+
prior deltas+new/rolled delta coexist on disk; changed-file guards do not prove
that native cache scratch or later compilation will fit. A large rebuild may
still exceed this free-tier machine/job budget.

## Local validation

- 6 pure bridge tests: metadata fidelity, restored-mtime write, hardlinks, rename,
  deletion/type changes, writer-race rejection, cross-job rejection, symlink-parent
  safety and actual eight-small-shard legacy restore followed by delta application.
- 5 delta-only rollup tests: chain equivalence, links/rename/delete/recreate,
  corruption/wrong order and immutable-output rejection.
- 3 orchestration tests (including legacy descendant timeout cleanup): actual driver seed→D 1→D 2→fresh next-run restore→near-expiry
  rollup/base-refresh→fresh reconstruction, plus active config ordering checks.
- 8 prior checkpoint regressions and 11 crash composition tests pass.
- Official CircleCI config validation passes (must revalidate after review fixes).

No 68 GiB benchmark, native cache launch or APK/device crash verification was performed.


## Python tooling correction after #1069

The previous setup installed APT python3-yaml but imported yaml with PATH-selected
python3. Those interpreters can have different site-package directories on CircleCI
machine images. The observed install-success/import-failure is consistent with this
mismatch; #1069 did not log the interpreter path, so its exact binary is unconfirmed.

`ensure-flow-tools.sh` now handles all six jobs from one shared source. It checks
zstd/tar everywhere. Only seed configuration tests need PyYAML: their APT package
and all seed test invocations explicitly use /usr/bin/python3. Normal build/helper
Python PATH is not modified. Diagnostics report selected and test interpreter paths
and the imported YAML module location, so the next run can verify image assumptions.

Four regression tests simulate a selected interpreter without system site-packages,
a separate APT-owned package directory, installation/recheck against that system
interpreter, and stage jobs that need no YAML. Seed fixture tests also pass under
the actual local /usr/bin/python3. This is not execution in the CircleCI image.

## UI-test wiring correction after #1071

#1071 saved/published the unchanged compressed base successfully. Stage 1 restored,
inventoried and prepared source, then stopped at a UI test that still expected old
branch-gated inline YAML commands. Build, delta capture/save and head advancement
did not run. This change does not remove UI assertions or change product features.

The UI test now calls a repository-policy function that validates actual Flow
wrappers and retains its branding/GN/vanilla-module source checks. Native UI/XML/
resource assertions still run against the real restored source tree. Repository-
only assertions are also directly tested locally, before expensive build work.

The stdlib wiring checker verifies direct wrapper invocations in all five stages,
actual apply/test command sequences and overlay/UI/graph/smoke/build ordering.
It accepts the generated Flow YAML/shell subset, not arbitrary YAML or shell.
It is a bounded static guard, not a proof of arbitrary script execution. No new
PyYAML dependency is added to build-stage Python. Unknown shell statements and
simple early-exit/conditional bypasses are rejected.

Ten mutation/repository-policy tests cover all stages, removed/commented apply or
test calls, stage-specific reordering/omission, conditional/early-exit bypasses,
shared reset/filter-test removal and wrong-path same-basename commands. Seed and
GitHub run these before expensive source work. The active test audit found no
other obsolete branch-gated config assumption; build-flow now shares the checker,
and remaining "Full Mode" wording in fixed-recipe test variables was corrected.

## Checkpoint quiescence correction after #1073

#1073 completed compilation and APK packaging validation, then refused checkpoint
capture because writable descriptors remained in the workspace. The old bridge
error did not identify processes, so the exact historical writer is unproven.
The original archive path had a scoped Android idle-build-server shutdown that the
bridge omitted; restoring that lifecycle step is the concrete regression fix.

The bridge now invokes that same shutdown: only this workspace's
fast_local_dev_server.py with --exit-on-idle receives SIGTERM. Other processes are
not killed. It waits briefly for naturally closing descriptors, then refuses any
remaining live workspace writer. Diagnostics include PID, executable basename,
relative path and link count, never argv or environment values.

Every visible FD is inspected. A regular open inode with nlink=0 is not in the
captured tree; it is reported separately rather than treated as a live tree writer.
A deleted pathname whose inode still has a hardlink remains blocking, and an
unlinked FD cannot hide a second live FD in the same process.

Seven real-process tests cover graceful known-server shutdown/flush, unknown-writer
refusal without killing it or logging secret argv, read-only and other-workspace
processes, unlinked-only descriptors, live hardlinked deleted names, a second live
FD, natural closure, and refusal to terminate a server without --exit-on-idle.

This retains the trusted same-user/no-new-writers contract and double-inventory
checks. Permission-inaccessible processes and writable mmap after FD closure are
outside this FD scanner's coverage; it is not proof that all machine processes
cannot mutate the tree. Unknown live writers still block, not get ignored. Browser
crash code is unchanged by this checkpoint fix; APK packaging success is not device
runtime validation.
