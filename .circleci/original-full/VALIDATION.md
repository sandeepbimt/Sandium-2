# Original Full candidate validation and limits

## Source provenance

- Original Full config is the exact `fc220e7f` Git blob `9512ffcdfc8ff52a534c9025cfee61abf1d39bc1`.
- Original archive wrapper: `a5e3b626f0b9ef46fe0a60e56e355cfe5cefc2be`.
- Original shard implementation: `eaafba1374f5447f0c7c09084a2779c0a39bbdbc`.
- `step-provenance.json` identifies every original step retained unchanged and every approved exception. `product-steps.json` preserves the current seven Sandium overlay commands and current APK validation/export rather than reverting product features.
- Original compression is eight independent `zstd -T1 --fast=5` workers. Original decompression is eight `zstd -T1 -d` workers. Native CircleCI upload does not expose an independent parallel-upload control here.

## Explicit approved exceptions

1. Full-only, opt-in workflow on the current experiment branch; unrelated Afterbird/Fast workflows excluded.
2. Stage 1 selects the fixed complete base by exact accepted identity, not broad branch fallbacks or cumulative increment replay. Only base metadata is read from the legacy receipt during first bootstrap. Every shard hash and restored source pin is checked.
3. Current Sandium product overlays and binary validation remain. UI, removal, Dark Pages and manual-correction code is not reverted with the orchestration.
4. The separate reference-promotion workflow is removed. Ordinary runs only publish workflow-scoped original Full handoffs and small fixed-reference metadata (unchanged metadata keeps the same immutable key). They never upload the fixed reference archive.
5. Maintenance copies the identical compressed reference only inside the two-day expiry margin. Save, clear local copies, exact remote restore, and hash validation precede accepting renewed metadata. Native cache retention is explicitly 15 days; the recorded deadline remains conservative capture + 14 days.
6. User approved the confirmed original incomplete-handoff correction: stage 1 still requires a completed reference, while stages 2–5 accept consistent false/false readiness flags with exact prior stage, workflow and revision. The writer uses the actual shell `CIRCLE_SHA1`, not a cache-template literal. Pins, hashes and build-state validation are not relaxed.
7. The UI-pruning wiring validator recognizes the exact reviewed original config hash and still runs every existing product wrapper sequence and argument/readback check. Future generator/hash changes require fresh review.

Original compile slice, source preparation, original archive mechanics, stage handoff cache keys, APK marker shortcuts and final-stage continuation remain unchanged. In particular, an unchanged deterministic compiler failure may be retried by later stages, as in the original; there is no unrequested new early-stop policy.

## Test targets, not suppressed failures

Running the old generic suite directly against the new config produced 35 failures/errors. Independent review found that 16 were current product negative tests whose temporary fixture lacked the new config hash. Their fixture is corrected, and they run against the active candidate. Only the remaining 19 genuinely retired configuration-shape cases use the historical fixture. Both lists and reasons are recorded in `legacy-test-targets.json`.

`python .circleci/original-full/run_architecture_tests.py` executes every test:
- 262 existing product/general cases against the candidate configuration: passed, one pre-existing Java-tool availability skip.
- 29 new original-config, reference, handoff and product-wiring cases: passed.
- All 19 retired architecture cases against the exact `205e2a9` configuration fixture (published `8477b46` equivalent tree): passed.

The original lightweight Full self-test command was also executed verbatim against current product source and passed. All 37 generated shell commands passed `bash -n`.

The native #1201 fix adds the pinned API's required `base::JSON_PARSE_RFC` argument. Independent actual-header compiler regression and old-call negative control passed. This is not a full native Android compilation.

## Runtime limitations

No new native cache/bootstrap operation, actual eight-shard peak disk measurement, end-to-end Android build, installation or device behavior has been validated for this candidate yet. Some helper tests use mocked large-archive verification or source pin commands. A hash-pinned accepted receipt supplies the actual base manifest digest at runtime; unknown/mismatched metadata stops the run rather than inventing a digest or falling back.

The fixed archive is an older complete base, not a complete snapshot of all later deltas. Current source overlays are preserved, but build work that existed only in later increments may need recompilation. No speed or successful APK outcome is promised.

Schedule inventory found existing UI/removal schedules only. A fixed-reference schedule must be explicitly created and read back after this configuration is published; no schedule is claimed by merely defining the maintenance workflow.
