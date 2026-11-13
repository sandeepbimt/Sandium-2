# Sandium – Flow: experimental crash-fix candidate

Base: `0a85c0b6665f4960069ddaaaeb933f56c63b3444`. All 60 base Git blobs were
materialized through GitHub and their Git object hashes verified. The crash-fix
code/fixture patch was applied. The old branch-routing config patch was not
retained because the entire workflow is replaced by this single-mode candidate.

## What is wired, not merely proposed

- One workflow (`sandium-flow`, user-facing Sandium – Flow), one serialized job-group, one product recipe, no Full/Fast selector.
- Initial seed job reads the existing job-949 shard cache without writing its key.
  It restores/verifies that base, inventories it and exports a new experimental base.
  Subsequent runs halt that seed job when an accepted experimental head exists.
- Five bounded real Brave build jobs use the actual source preparation, credential
  helper, overlay commands, GN checks, remote smoke, bounded Siso compilation and
  APK validation from the successful baseline, with the crash-fix composition.
- Product overlays selected for the baseline's branding branch are now unconditional
  in this candidate. Native build flags are a fixed recipe, not tied to mode or
  branch. This does not assert that missing #850 features have been restored.
- Every stage reads the accepted head under the group lock, validates its exact
  predecessor (or valid same-revision completed APK), restores every required layer,
  then reconstructs source/generated/output state.
- Actual new-state capture exports changed file blobs. Native `save_cache` stores
  that one outgoing payload; the accepted experimental head is saved only afterward.
- Subsequent runs consume the same accumulated chain. Expiry/length triggers an
  independent compacted base inside this one mode. Expired chains fail closed.
- Later stages halt only on a verified APK receipt with its saved checkpoint.
- Deterministic build failure is recorded/checkpointed but then stops the workflow,
  rather than repeatedly executing unchanged failing work across remaining stages.

## Isolation and review gates

Execution is disabled by default (`run_experiment=false`). Publication review and
initial seed import also default false. A new experimental namespace is required;
canonical reference/promotion keys are never written. No settings were changed.

`publication_reviewed=true` is an explicit operator attestation, not proof of
protected writers. It must not be enabled until the actual trust boundary,
serialized job-group semantics and checkpoint content policy have been reviewed.
Admin access and dynamic configuration alone are not sufficient evidence.

The namespace currently scopes one experimental lane. Do not run different branches
or unrelated product recipes in that lane. Revisions must follow the intended
crash-fix branch history. A separate namespace is required for a divergent branch.

## Verification completed locally

- Official CircleCI CLI/server config validation: **valid**.
- Crash composition tests: **11 passed**, including reset/bootstrap/warmup/race order.
- Candidate integration tests: **3 passed**, including actual seed payload capture,
  incremental mutation, native-cache boundary simulation and next-run reconstruction.
- Shell syntax checks for extracted commands and preparation: passed.
- Python compilation checks: passed.
- Underlying checkpoint prototype's **53 tests** passed independently.

Native CircleCI caching, serialization and Chromium compilation were not executed.
No push, CI run or APK was produced by this implementation work.

## Runtime blockers and limitations before enabling

1. **First seed migration:** the existing 26 GiB cache is compressed shards. The new
   format stores content blobs and native caches package them. Migration resaves a
   base once; it is not an incremental-only upload on that first import. It needs
   disk/time measurement under the one-hour job limit. The driver checks available
   disk conservatively and refuses insufficient headroom rather than filling disk.
2. **Current hash/package cost:** capture/export use quiescent hardlinks, not full
   copies. Restore consumes downloaded blobs via hardlinks, creates independent
   copies for duplicate-content source paths, then drops transport/object links
   before build writers resume. Large changed
   libraries are uploaded as whole files, not chunk deltas. No speedup is promised.
3. **Secret/content policy:** checkpoint scope must be reviewed before any upload.
   The selected tree is `brave-work`; do not assume existing caching automatically
   makes every generated file safe to retain. No new secret storage is authorized
   by the review flags themselves.
4. **Trust:** hashes protect integrity, not origin. Cache writers and manual group
   release must be controlled. No repository/organization security settings changed.
5. **Expiry:** declared native cache retention is 15 days. A disappeared/expired
   dependency stops rather than silently using the old base; explicitly reseed a
   new namespace if recovery is required. Publication history is not permanently
   durable when caches expire.
6. **Build correctness:** real source/graph restoration, APK features, startup crash
   behavior and device tests remain unverified. A valid config is not a working APK.

The crash fix is the first intended real workload. This candidate does not trigger
an old Full pipeline or claim a successful old run verifies the new mode.

## Independent-review corrections

Native stages now use `verify-flow-state.sh`: it checks the selected complete-chain
restore proof plus the original exact Git/tag, GN graph and Siso state checks. Only
the seed job uses the original root-level shard verifier. Artifact upload precedes
APK-success head publication. Native restore and snapshot hardlink lifetimes are
limited to quiescent phases; duplicate-content source paths get independent inodes.
The integration fixture verifies this and confirms no imported blob links remain
when compilation may begin. Cache packaging scratch demand still needs measuring.

### Fresh-machine host prerequisites and disk guards
The pinned Chromium Android host installer now lives in `install-flow-host-deps.sh`.
Stage 1 invokes it at its original post-source-sync point. Stages 2–5 invoke the
same installer separately, without entering stage-1 source reset/configuration or
reapplying its destructive work. Installer and tee failures remain fatal. Existing
APT setup and Node setup still occur on every machine. This has been shell-syntax
and routing-tested, not run against a live CircleCI machine.

Before restoring native layers the driver logs filesystem capacity/free bytes and
requires the sum of layer content sizes plus a 32 MiB minimum metadata reserve.
The consuming restore separately checks independent duplicate-content bytes plus
32 MiB. Capture logs its minimum native-packaging reserve. These are fail-closed
lower-bound checks, not measured guarantees for native CircleCI archive temporary
space, OS package installation, inode counts, or remaining compilation growth.
Full-scale peak disk and duration remain required first-run measurements.
Local integration tests now number 5; crash composition tests remain 11.
