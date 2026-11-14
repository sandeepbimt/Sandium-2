# Full baseline with incremental checkpoint transport

Baseline: sandeepbimt/Sandium-2 fc220e7f, `.circleci/config.yml` Git blob
9512ffcdfc8ff52a534c9025cfee61abf1d39bc1, retrieved directly through GitHub.

## Preserved
- Canonical eight-shard26GiB base and its original verified extraction implementation.
- Pinned Android ARM64 Release preparation, BuildBuddy strict-remote compilation,
  -j80, local=8/remote=80, bounded CAS recovery and APK export sequence.
- Current #1088/UI/crash fixes and13-component removal source patches remain
  unchanged, with graph/resource and APK removal gates active.
- Exact accepted head and ordered increments, including completed prior work.
  No missing dependency silently falls back to base only.

## Narrow pipeline changes
- Full is the only build mode; old Fast and Flow workflow choices are removed.
- Same eight-worker base extraction followed by sparse ordered increment replay.
  Changed paths/tombstones/ancestors are checked without reconstructing the entire
  filesystem map on every layer. Reliable same-job capture inventories remain.
- Ordinary jobs upload only their newly captured increment and receipt. They do
  not reupload the base or compact earlier increments.
- Compile ceiling increased from1200 to2100seconds by user request. Actual time
  is limited by elapsed setup and conservative checkpoint/export/save reserves
  inside55minutes, leaving margin under the platform's one-hour job limit.
  Thirty-five minutes is not a guaranteed allocation; current reserves reduce it.
- Product source changes are separate from pipeline baseline; nothing restores
  old UI or removed Brave product code merely to regain old pipeline performance.

## Authorized occasional maintenance
`run_maintenance=true` selects only the checkpoint-maintenance workflow.
The build chain also checks maintenance before stage1. Both use the same serial
lock; selection occurs after lock acquisition. Maintenance no-ops unless earliest
logical14-day dependency expiry is within2days or11of16increment slots are used.
The latter reserves enough capacity for the full five-stage build.

When due, maintenance validates the current complete chain, merges only the delta
layers, restores the original base and replays the replacement delta to validate
it. It saves a new immutable delta and an unchanged base under new keys. Then it
removes only local compressed transport copies, downloads the newly saved cache
keys, verifies exact identities, shard hashes, delta envelope and every delta blob,
and only then permits publication of the replacement head. Old remote caches are
never deleted. The previous receipt is retained alongside the new head.

This is a real copy to a fresh cache key, not an assumption that cache restore
resets expiry. CircleCI cache maximum is15days; logical receipts use14days.
Maintenance report records exact earliest expiry, next due time and readback status.

## Flexible post-APK refresh and early artifacts
The build copies any produced APK to an explicitly UNVERIFIED diagnostic artifact
and runs native artifact upload immediately after the bounded build step, before
APK validation and checkpoint work. The existing validated APK artifact remains
separate and is published only after its existing validation gates.

The new increment and head are saved first. Only after their native saves and the
final stage gate succeed is optional-refresh eligibility recorded: the exact
accepted head must contain a verified APK for this workflow/source, and more than
1200seconds must remain in the original stage's conservative55-minute allowance.
A tiny immutable request record binds that decision to the exact head.

A separately serialized stage6 reads and verifies that request and latest head.
It reuses the existing maintenance+readback procedure to refresh the unchanged
26GiB base plus rolled accepted increments. It does NOT recreate a new full-tree
snapshot and does not relax same-stage publication ordering. If skipped or failed,
the newly saved increment/head and APK artifact remain intact. This separate job
has a fresh one-hour clock and some VM/transfer overhead; the20-minute threshold
is measured at the originating successful stage, not a promise refresh fits in
that stage's remaining time. No cache durability or runtime guarantee is implied.

## Scheduling and limits
The workflow parameter does NOT create a schedule. This GitHub App project needs
a native CircleCI Schedule Trigger, created and verified separately after deploy:
- Branch: experiment/sandium-overnight-removal
- Daily, e.g.23:00UTC
- run_maintenance=true; run_build=false; publication_reviewed=true
- checkpoint_namespace=sandium-exp-single-v1-bridge-crash01
- allow_seed_import=false

If credits, service access or a job failure prevent refresh, alert and retry before
expiry. Missing/expired dependencies fail closed. No indefinite durability guarantee
can be made for an expiring cache service. BuildBuddy cache is not a durable backup.

## Verification
Sparse replay, maintenance readback, product composition, pipeline wiring and bridge
unit tests are run locally. These do not prove APK correctness or production speed.
Real CI timing, refreshed remote cache retrieval, schedule registration and APK
verification must be reported from the actual deployed runs.
