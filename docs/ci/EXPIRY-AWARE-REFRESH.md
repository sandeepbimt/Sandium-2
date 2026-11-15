# Expiry-aware optional refresh (next run only)

This change does not alter the running #1171 workflow or trigger a build. It changes only the Full driver's eligibility policy, tests and this document. APK-first upload, durable increment publication, remote cache readback and accepted-head replacement ordering are unchanged.

## Decision

After the APK and increment are safely published, inspect the accepted head's base plus every required incremental layer. Their immutable `expires_at` deadlines are inherited from the restored checkpoint. Restoring a cache or creating a new head receipt does not renew them. Use the earliest dependency deadline, not the latest receipt timestamp or only the base date.

Request an optional full refresh only when that earliest dependency expires within two days (inclusive), the APK is verified, exact source/workflow/pipeline/stage bindings match, and more than20 minutes remained after publication. The separate serialized optional job recomputes expiry from its exact accepted head; a previously eligible request cannot force refresh of a fresh head.

The two-day margin preserves the existing maintenance threshold. Current cache objects use conservative14-day metadata against configured15-day retention. The reported due/expiry values describe stored dependency deadlines, not a guarantee of service availability.

## Scheduled maintenance

Existing scheduled maintenance is untouched and still checks the earliest dependency date. It also compacts at11 layers to reserve five build-stage slots within the16-layer cap. This capacity exception remains necessary even when caches are young; the optional post-APK refresh itself is age-gated. Scheduling/serialization and maintenance restore/readback proofs are unchanged. This patch does not create or claim verification of any external schedule.

## Invalid metadata

Missing plan/base/layers or expiry, booleans, strings, nonfinite values, already-expired timestamps and deadlines beyond configured15-day retention plus five-minute clock allowance are rejected. Do not guess a fresh TTL, silently skip with a false freshness claim, or overwrite the accepted head. This can fail the checkpoint step after the APK is already safely uploaded; investigate/recover the metadata rather than relaxing validation. No base-only fallback is introduced.

## Verification

Tests cover oldest incremental dependency, fresh base, inclusive two-day boundary, malformed/expired metadata, stale eligible requests against fresh heads, exact workflow/APK bindings, remote readback and preservation after failures. Python tests are not live CircleCI execution; first deployment still requires observation of the reported eligibility decision and maintenance results.

Independent review: no source blocker; eight focused maintenance tests and all236 repository host tests passed. The inherited CircleCI optional-job label mentions only the time budget; the structured eligibility/report fields additionally show the expiry decision. No live schedule or running job was changed.

## Live schedule inspection, Nov15 around07:54UTC

Read-only CircleCI Project Setup inspection found exactly two enabled daily schedules: UI-only at23:30UTC (`experiment/sandium-ui-only`, `sandium-exp-single-v1-bridge-ui1088`) and removal at23:00UTC (`experiment/sandium-overnight-removal`, `sandium-exp-single-v1-bridge-crash01`). Both specify run_maintenance=true, run_build=false, allow_seed_import=false, publication_reviewed=true. No navigation/backpreview01 recurring schedule was listed. Therefore this code alone does not protect the current navigation lineage during inactivity; that schedule still needs explicit registration and readback. No schedules were modified during inspection.

Expiry metadata is a conservative deadline computed at capture as current time plus14 days, before the cache save completes. It is not an expiry queried from CircleCI. Renewed deadlines become accepted only after verified full replacement publication; ordinary restore/new increment publication cannot renew older objects.
