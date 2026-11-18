# Explicit #1396 transport coordinator (not activated)

`tools/feature_seed_transport.py` implements only local transport coordination.
It does not restore/save native caches, download network data, trigger CI, modify
normal compatibility, or admit a feature build. Full Brave upgrade remains held.

## Interface and ordering

Run from the feature harness, with current `CIRCLE_WORKFLOW_ID`,
`CIRCLE_BUILD_NUM`, `RAWS_PIPELINE_NUMBER`, existing checkpoint-review/project
settings, `RAWS_STAGE=1`, `RAWS_NATIVE_FEATURE_SEED=true`, and
`CIRCLE_BRANCH=raw-sandium/native-ui158` supplied by the actual job. The coordinator
checks this explicit feature caller before every phase. Only its isolated unchanged
baseline subprocess receives `CIRCLE_BRANCH=raw-sandium/official158` together with
the pinned baseline SHA/root, so the old validation gate sees its original identity.
The actual caller environment and new-feature gates are never changed. Original job-start epoch must
come from job start, not a timer reset after cache downloads.

1. `prepare --repository REPO --session NEW_SESSION --job-start-epoch EPOCH`
   creates a detached local clone of the small harness at exact baseline `e7e7820`.
   Uses `--no-hardlinks --no-checkout`, then exact checkout; no source clone.
   A shallow harness checkout may lack the pinned baseline object. Only in that
   case, fetch the exact frozen commit into the isolated clone (no tags or branch
   fallback), bounded to 120 seconds and the original remaining job budget. The
   source origin must be a strict GitHub HTTPS/SSH URL matching both current
   `CIRCLE_REPOSITORY_URL` and `CIRCLE_PROJECT_USERNAME` / `Sandium-2`; missing or
   conflicting repository identity fails closed. Fetched commit/FETCH_HEAD and
   tree identity are checked before checkout. Existing objects require no fetch.
   Existing sessions fail. `plan.json` exposes frozen exact physical receipt and
   archive keys, logical key, expiry, manifest ID and provenance for CI artifacts.
2. Native CI separately restores the **exact** receipt key into its usual cache
   path. `select --session SESSION --receipt DOWNLOADED_RECEIPT` requires raw bytes
   identical to reviewed frozen receipt, then runs unchanged baseline selection
   with `precheck=True`. No completion short-circuit is used.
3. Native CI separately restores the **exact** archive key into INCOMING.
   `restore --session SESSION --incoming INCOMING` checks the pinned manifest,
   eight named shards and sizes, renames manifest/shards into baseline on the same
   filesystem, then runs unchanged baseline `restore-base` and `restore-finish`.
   The baseline engine performs actual shard integrity verification/extraction
   and releases verified compressed inputs as usual. No 31 GB duplicate copy.
4. `adopt --session SESSION --feature-root FEATURE_CHECKOUT` requires an existing
   separate feature Git checkout with **no** work/state/head/completion/admission
   or other stale marker destinations. It rechecks exact selected/current-job
   proof, then renames only `work` and `.checkpoint-state` into the feature root.
   It returns `baseline_checkout` for the parent's `SeedCallbacks`. No old head,
   completion receipt, APK artifact directory, or remote reference is transferred.
   Selected/restored metadata is intentionally temporary: the mandatory next
   `baseline_seed.transition()` consumes and invalidates it before feature work.

Fetch tests use a fake runner and perform no network requests. A real shallow
CI checkout may need its existing repository credentials for this exact-object
fetch; unavailable credentials or timeout fail closed without a branch fallback.

The Python functions use the same argument names with underscores. `adopt` does
not call transition: the parent owns reviewed callbacks and must run transition
before any feature build. An adopted tree is not a normal resumable checkpoint.

## Boundaries and failure behavior

All subprocess phases use a fixed reviewed program and isolated Python mode,
importing only unchanged baseline tools. They assert baseline fingerprint and
root, preserve original job timing, and never run commands from receipt fields.
Baseline HEAD/tree/tracked cleanliness and untracked import-directory contents
are checked before phases. The baseline checkout remains available for callbacks.

Every phase revalidates frozen evidence/expiry, current workflow/build identity,
and remaining original budget. At least 1620 seconds are withheld for subsequent
callbacks and checkpoint preservation, plus a separate ten-second process cleanup
allowance. The remaining restore deadline is recomputed after native downloads
and before every baseline subprocess; it never resets the original 3300-second
job deadline. Repeated, partial, colliding or cross-job sessions
fail closed. Once execution starts its phase is marked in-progress; failure
requires a fresh session. No failed run publishes a current-job success proof. Baseline subprocesses own
new process groups. Failure/timeout sends TERM, then KILL even if the leader has
already exited. PID birth identities track owned descendants that create separate
sessions, and baseline TERM handling unwinds its existing nested-process cleanup;
successful leaders also have remaining group descendants killed.
The unchanged baseline quiescence check runs after restore-finish before the
coordinator preserves its current-job proof.

Renames preflight every destination and device. Cross-filesystem moves fail,
never falling back to copies; partial rename failures attempt reversal. No old
remote cache/reference is changed. A partially restored local tree remains for
inspection rather than being silently reused or destructively cleaned up.

Host tests exercise exact bytes, selection precheck, state/proof binding,
expiration/budget/job identity, collision refusal, same-device inode-preserving
moves, move rollback, partial-restore refusal and the real detached baseline
checkout/fingerprint subprocess. Archive execution is mocked in these tests;
no 31 GB download, production extraction, GN/build, APK validation or remote
readback has been performed by this patch. CI assembly/activation is separate.
