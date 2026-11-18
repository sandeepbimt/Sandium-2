# Explicit final full archive exception

Set only `run_raw_final_archive=true`. All pipeline parameters default false.
Normal RawS Full retains its existing early completion exit and is unchanged.
Do not run the exception until the active baseline workflow has resolved.

The serial `raws-final-chain` has three jobs:

1. `raws-final-compile` restores compatible accepted state, finishes the same
   target, and saves a new immutable incremental checkpoint under a separate
   `raws-final-*` namespace. A timed-out slice is saved/read back before the job
   reports incomplete; rerunning the exception resumes that independent progress.
2. `raws-final-pack` accepts only the exact completed receipt from this pipeline,
   workflow and source revision. It restores all layers, verifies restore proof,
   runs no hooks or compiler, and archives the complete restored tree. After
   native cache save it deletes the disposable local archive, restores the exact
   saved key, validates all shards, and extracts/hashes the APK member before
   publishing an independent final receipt.
3. `raws-final-probe` restores that exact final full base on a fresh worker. It
   records Siso state hashes/version, runs the unchanged target without deleting
   the APK, and reports remote/local/cache work plus before/after APK integrity.
   A changed APK digest fails the exact-reuse check. Missing action metrics or
   missing incremental state are reported as inconclusive, not as a no-op pass.
   The probe publishes evidence only and never promotes a checkpoint.

This is a reconstructed final workspace, not a capture of another job's vanished
filesystem. The old normal accepted checkpoint is never overwritten. The final
receipt is not automatically promoted into the normal Full head. Promotion must
be explicit and verified separately if desired.

Each job starts its budget clock before installation/setup. Operations are
watchdog-bounded inside a 55-minute internal horizon. Native CircleCI cache
transfers do not have a proven duration bound: the two-job split creates room,
but actual full-archive timings and restore remain to be validated in CI. Failure
must not create a final success receipt; the independent compiled checkpoint
remains available if archive packaging fails.

Local validation covers receipt/source/workflow/digest guards, default-off
configuration, no changes to existing jobs/workflows, and a real tar+zstd APK
extraction fixture. It is not a claim of production-sized archive validation.

## Completion-marker correction after #1387

#1387 produced and verified the ARM64 APK in stage 2. Stage 3 then restored
stage 2's completed marker followed by stage 1's incomplete marker into the
same path. The older marker overwrote success, so stage 3 wrongly attempted
normal checkpoint preparation and failed its exact prior-stage guard.

Later stages now use one native `restore_cache` operation whose ordered keys
prefer the newest preceding stage. CircleCI selects the first matching key,
preventing older incomplete markers from overwriting newer completion evidence.
No compiler, checkpoint payload or produced APK changes are involved.
