# Isolated back-preview checkpoint fork

Branch: `experiment/sandium-back-transition`.
Writable namespace: `sandium-exp-single-v1-bridge-backpreview01`.
The removal and UI-only branches and their accepted heads are unchanged.
Every job checks the exact new branch/namespace before checkpoint operations.
The original removal scope guard remains unchanged for its own branch/tests.

## Frozen read-only source

Source scope `sandium-exp-single-v1-bridge-crash01`.
Source revision `379837c136b79902ea1a07ad0a1455b1435e0c06`, pipeline #1166,
workflow `e25623ab-de77-41be-bc8c-7d2b2ff1b7b8`.
Receipt `49ada219fa9cdb4df7b5a2a694cd5d5e23c15b23873f195de7ed34c72ee3e7aa`.
Job3612's native-save log supplies the exact immutable receipt cache key in the
initializer. Its maintenance artifact reports remote readback verified, one
increment, dependency expiry 2026-11-29T03:57:41Z. Workflow succeeded at04:07:05Z.
The new import does not reset or extend that expiry.

## First run (not started by this change)

Use `run_build=true`, `run_maintenance=false`, `publication_reviewed=true`,
`allow_seed_import=true`, and the exact new checkpoint namespace above.
Subsequent runs use `allow_seed_import=false`.

Initializer first restores ONLY the new target head. Existing valid target
halts initialization; an invalid one fails closed. Only when absent and explicit
seed import is enabled does it record a workflow/pipeline/source-bound absence
marker and restore the exact frozen source receipt cache. No latest-source-prefix
fallback is permitted.

The helper validates receipt hash, fixed ID/provenance, compatibility, exact
one-layer parent/head chain, namespace-qualified dependency keys, expiry and
pipeline ordering. It re-envelopes an unchanged deep copy of the plan under the
new namespace, source commit, workflow, pipeline and stage0. `apk_verified=false`
and no previous target receipt prevent importing a success claim from #1166.
It records provenance and preserves the locally restored source receipt as an
audit file before removing its disposable HEAD copy. Normal publication validates
the target receipt; YAML saves only under the new target head key.

This is metadata seeding, not a fresh payload verification. The report states
`payloads_verified_this_job=false`. Normal stage1 still downloads and verifies
the exact inherited base and increment before source overlays or compilation.
Missing/expired/inconsistent caches fail closed; never silently fall back to base.
Only after normal build/export gates and incremental publication can the new
revision be considered built. New deltas/refreshes use the new namespace.

## Cost and safety

No additional 26GB transfer or extraction is introduced by the initializer.
Normal Full restore and native compilation still cost time/credits. Inherited
payloads remain immutable shared read-only dependencies until target maintenance
refreshes them under target-qualified keys. There is no remote cache deletion or
rewrite. Existing removal maintenance schedule is untouched. No new recurring
schedule is registered for this experimental lineage.

If the frozen source expires before first import, stop and deliberately review a
new verified source; do not loosen identity checks or fabricate later expiries.
The project-wide serial group is unchanged. Preserve one active build at a time.

## Validation limits

Seven new metadata-isolation tests cover unchanged expiry/plan, stale/missing
marker, existing target, foreign identity/hash/provenance, broken chains, expiry,
wrong scope/stage, local transaction and YAML read-only source/new-head writes.
All232 local tests and the Full wiring test pass. Independent review cleared the seed policy; the final combined diff is reviewed
before publication. No CircleCI build/cache restore or device test is claimed by
these local tests.
