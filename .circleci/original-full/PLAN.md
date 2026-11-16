# Original Full restoration candidate (not active)

Baseline: exact repository `.circleci/config.yml` at fc220e7f, retained beside this plan.
Current product base: tree at published 8477b46, plus reviewed JSONReader fix.

## Allowed differences from baseline

1. Full only, explicitly gated run; no unrelated Afterbird/Fast workflows.
2. Stage 1 restores the fixed verified legacy eight-shard reference. No branch-prefix fallback and no cumulative delta replay. Metadata must bind exact cache key, manifest digest, byte size, pinned source compatibility, and conservative expiry.
3. Stage 2–5 retain workflow-scoped full archive handoffs, not cross-workflow increment chains. APK-first delivery and marker short circuit remain.
4. Existing selected Sandium feature transformations, source/reset protections, thirteen-component audits, and APK binary validation remain. Their current commands replace stale baseline conditional overlays.
5. Original 1200-second Full compile slice, eight parallel shard workers and `zstd -T1 --fast=5` compressor preserved. Decompression uses original `zstd -T1 -d`; there is no `--fast=5` decompression mode.
6. No automatic promotion of newly compiled handoffs into the fixed future reference. Scheduled near-expiry maintenance can only copy the identical verified compressed reference, read it back, and advance its physical immutable cache key. The logical content reference remains unchanged.
7. Preserve original final-stage/continuation behavior exactly. The baseline permits failed actions to remain pending and continue through subsequent stages; unlike the recent experimental pipeline, it does not stop deterministic compiler errors early. This consequence must be disclosed, not silently changed.
8. Native `save_cache` uploads remain as in baseline. Parallel shard compression is not a claim of parallel independent uploads.

## Safety and evidence gates

- Current reference key: `sandium-bridge-base-v1-qPgQ5VYKvKjfebPZMGkn2QqAn0I_pgCmZ64n7Kzs6rg=`.
- Archive bytes: 32,775,343,758; eight shards. Verified current #1199 base-cache download selects this key from #1171 job3634.
- Conservative recorded deadline: 2026-11-29T08:22:53Z; two-day maintenance margin. This is capture+14days, not service-reported eviction time.
- #1171 refresh recopied unchanged base and rolled two deltas into one. It did not produce a newer standalone compiled source snapshot. Starting from this base preserves current source changes by explicit overlays, but may require recompiling work cached only in subsequent increments.
- Exact manifest digest/base ID must be recovered from a valid accepted receipt and match this fixed key before bootstrap. Do not infer a manifest digest from cache suffix or size.
- Existing branch and checkpoint remain intact. Candidate must be independently reviewed, all step differences enumerated, and only one run authorized before activation.
- Full archive creation and actual peak disk/storage performance remain CI-only validation; do not promise a faster successful run from source tests alone.
