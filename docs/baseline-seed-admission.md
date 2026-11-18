# Exact #1396 baseline seed admission (local proposal)

No CI config, normal compatibility validator, integration checkout or remote reference is changed. This patch is a small library/interface, not an activated transport pipeline. Based on exact `e7e782067daef429073e54c2bd8fbb91da7c8439`; no AGENTS.md or applicable local .agents skills were found in the baseline checkout. All work is separate from raws-1396-integration.

## Verified existing evidence

Read-only API observation: workflow `ceaa5f4e-7a36-4fa1-a5e9-e5633b70bf26` succeeded. Compile4270, pack4271 and fresh probe4272 all succeeded. Workflow API: https://circleci.com/api/v2/workflow/ceaa5f4e-7a36-4fa1-a5e9-e5633b70bf26/job

Frozen exact bytes from these artifact locations are included in docs/evidence/baseline1396, with SHA256 in hashes.json:

- Pack job `154f8d76-e108-4d8b-89bb-8bb317929dfb`, artifact prefix `https://output.circle-artifacts.com/output/job/154f8d76-e108-4d8b-89bb-8bb317929dfb/artifacts/0/raws-final-archive-evidence/`: receipt.json, archived-apk-proof.json, readback-required.json.
- Fresh job `91330a1a-8f71-4129-b280-beb29158fc21`, prefix `https://output.circle-artifacts.com/output/job/91330a1a-8f71-4129-b280-beb29158fc21/artifacts/0/`: raws-fresh-restore-probe/restore-probe.json and raws-fresh-restore-evidence/restored-proof.json.

Receipt `c84a3f88d74b96fc5c8f4b38e3946e85e1a253e1bccc61550f43f59af39c15fe` validates against its canonical payload. Full base/head `d0bf5cf09ce9adf4d176ba8271357f1d22aafa60cc120a54e215d58561b1e631`; no deltas. Manifest SHA256 `38ae30c1610ba11f5d8e23d1d6e6b812678948af628b5a7ed854c10ed928202d`. Compressed archive31248194531bytes. Expiry Unix1796239322; admission checks actual current time.

APK309980548bytes, SHA256 `7feb138bacb61dd9f77fca29c579330a2209f1ccd754c5e443962e76a76a977b`, extracted from remotely restored shard03 of08. Fresh restore proof binds exact receipt/head. Probe status completed, exit0, identical before/after APK, ARM64, signature/ZIP verified, incremental state present, normal head unmodified. Metrics say no action records; do not infer an independently measured zero-action guarantee. Remote execution enabled; not offline completeness certification. This task verified published receipts/proofs, not a second local31GB download.

Exact native physical keys below are deterministically derived from the fetched raw receipt bytes and logical base-key bytes using the published CircleCI checksum templates; not inferred from a newest-prefix search:

- Receipt: `raws-final-receipt-v1-1okrnzzf7a7dVnuYH3RZUQh3v8ABzZh4G4yc4YAiROY=`
- Archive: `raws-final-base-v1-xLg0fZPI+fw9SpoFza6mLhAhAB2lVxH6jMOzj9OmBBU=`

## Integration contract

`tools/baseline_seed.py` exposes `evidence()`, `restore_plan()` and `transition(root,new_fingerprint,verify_baseline=...,apply_features=...,generate_gn=...,verify_features=...)`.

1. Explicit opt-in chooses only this pinned baseline receipt. Fetch exact receipt/archive keys into a fresh isolated job/root. Use unchanged baseline tools at BASELINE_COMMIT and their original fingerprint for selection with precheck=True, restore-base and restore-finish. Do not import current feature modules into that baseline process or temporarily relax its COMPAT. Existing restore validates all shard content and manifest hashes. A cache miss, prefix collision or expired dependency fails closed.
2. Keep baseline transport and feature code in separate checkouts/processes. Move the verified tree only with its exact current-job selected.json/restored-proof.json; never modify a remote cache. Transition checks those files and rehashes the restored APK. Mandatory `verify_baseline` callback validates actual source/depot pins, approved old overlay, effective old GN/profile/toolchain and no open writers. This callback must use baseline validation, before applying any feature patch.
3. Transition invalidates job-local completion receipts, selected/restored metadata, final build status, inherited APK and build.ninja. Object files/Siso dependency state remain available for incremental rebuilding. Callback `apply_features` installs exact reviewed patch/overlay. `generate_gn` must run real GN with new args and fail-on-unused-args. `verify_features` computes/checks the actual new recipe fingerprint, exact new overlays and effective GN/profile/toolchain. No callbacks may execute commands supplied by a receipt.
4. A successful handoff writes only `.baseline-seed/admission.json` with `feature-inputs-ready`, apk_verified=false, checkpoint_accepted=false and old/new provenance. Failure records failed and cannot resume in place; start from another fresh isolated baseline restore. No old APK completion marker may be restored afterward. New compilation and APK validation must run before emitting a new completion receipt.
5. Do not place old receipt into the new feature head or pass it to a weakened normal validator. First feature checkpoint must be a new full base snapshot in the feature namespace, then exact remote readback/fresh restore before acceptance. Subsequent feature runs use ordinary strict compatibility checks. Never represent an old base plus a cross-identity delta as a normal compatible chain.

The integration owner still needs to wire the reviewed callbacks and explicit transport job. This library cannot establish GN/source verification by callback name alone; those implementations and pipeline wiring must be reviewed/tested before any future activation. No CI run is authorized by this patch.

## Validation and rollback

125 local tests passed (existing118 +7 admission tests): frozen real proof/receipt integrity, exact key construction, expiration, tampering, completion invalidation order, retained object files, distinct feature identity, feature/GN/validation failure, wrong restore binding, symlink escape, missing regenerated graph and duplicate transition refusal. Unit transition fixtures mock the large APK hash and callback operations; actual Chromium restore/feature-GN execution is not exercised locally.

Rollback is omission/revert of these added files. No baseline mutation or normal-flow change needs undoing. No push, new pipeline, rerun or cancellation was performed.

## Integration under construction

The feature candidate integrates this library plus real isolated source/GN callbacks. Transport is separately reviewed. To keep a one-hour worker bounded, the planned flow is: exact old baseline restore → source/GN transition → full prepared feature snapshot → independent fresh-worker verification → feature compilation. Preparation does not claim an APK; old completion remains invalidated. The first prepared snapshot requires the actual final feature-verification proof and always has apk_verified=false.

The original job-start epoch must survive the transition's deletion of old checkpoint metadata. Recreating new feature metadata must copy that original clock, not reset the deadline. Callback execution reserves archive/upload/readback time and must terminate its owned process group before quiescence on failure. No production CI activation is established by this design note.
