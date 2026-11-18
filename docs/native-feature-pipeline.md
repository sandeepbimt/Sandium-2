# Held RawS native UI seed/build configuration

`tools/generate_feature_seed_config.py` produces a **standalone** `.circleci/native-features.yml`. It does not modify normal Full configuration, publish a branch or trigger CI. Its explicit `run_raw_native_features` parameter defaults false; every job is restricted to `raw-sandium/native-ui158`, with `RAWS_NATIVE_FEATURE_BUILD=true`. The seed and new-input validator additionally use the seed opt-in.

## Flow

1. Seed worker starts its original clock before dependency/cache setup. It fetches exactly the frozen #1396 receipt and archive keys, relocates downloaded receipt/cache paths outside feature state, restores under an unchanged isolated baseline interpreter, and adopts only source plus exact current-job proof.
2. Transition callbacks invalidate old completion/APK/graph, apply native features and regenerate/verify the graph. The worker archives a **new full prepared feature base**, saves it through CircleCI, clears local archive inputs, reads back exactly the new key and only then publishes an independent prepared receipt. No compilation or normal head promotion in this job.
3. Fresh validator restores the prepared receipt/base, certifies exact restore and real feature source/GN inputs, then promotes only this new-recipe input receipt. It publishes no APK completion.
4. Five ordered compile slices restore the exact preceding verified receipt, not a newest-prefix head. Each saves and reads back reusable compilation progress **before** publishing an APK completion marker. Later jobs can cheaply halt only for a same-workflow verified completed marker. APK artifacts are uploaded before archival work.
5. A separate pack worker restores the exact completed compilation receipt and always saves/readbacks a complete APK-producing full archive. A final fresh worker restores that exact full base and performs the existing signed-APK/remote-enabled reuse probe. This is not an offline-build completeness claim.

## Runtime contracts still requiring integration/review

- `ci_feature_seed.py` must implement `select-prepared`, `verify-prepared`, `promote-prepared`, and `completed-handoff` with the exact producer/receipt/source/recipe checks. The first three use seed stage1; `completed-handoff` must support build stages1–5.
- `select-prepared` emits `.checkpoint-state/base.key`; `promote-prepared` emits `.checkpoint-head/receipt.json` only after real validation.
- `completed-handoff` is called after saved/readback progress. For slice expiry it halts the current job successfully before the completed cache save. For completion it checks the exact completed `.raws-final-progress` receipt and APK binding before allowing the immutable completed handoff save. A fifth incomplete slice leaves verified progress but cannot produce final APK/archive success.
- `ci_final_archive.state()` must use the current validated stage1–5 for compile progress; pack-only retains its existing captured-state path.
- Runtime branch gates must explicitly recognize the feature branch+enabled recipe+BUILD opt-in without changing baseline behavior or spoofing the branch globally.
- Manifest must explicitly enable exactly menu+toolbar and the cache identity must include active code. The generator keeps the all-tests preflight; baseline-only assertions need explicit feature-aware expectations, not removal.
- The original epoch survives cache transfer and transition; no restored checkpoint clock or fresh-marker fabrication may reset the job allowance. Compilation remains bounded by the runtime's original-deadline/reserve policy.
- Service-level CircleCI validation, production-size timing/disk tests, real Android/GN compilation and device validation have not been run.

## Explicit cross-run continuation

`native_resume_receipt_id` and `native_resume_cache_key` default empty. Both empty selects the fresh exact1396 seed workflow. Both populated selects a separate fresh resume validator, skipping old-baseline download/transition. Only one populated runs a deliberate failing selector-validation job instead of silently doing nothing.

The resume cache key is passed only as a cache selector, never a shell command. Before cache access, its namespace/format and the64-hex receipt ID are checked. Runtime `select-resume` must validate exact receipt digest, unchanged current source commit, new recipe compatibility, expiry and prior pipeline number. Existing ordinary compatibility remains strict. The selected new-recipe base and up to16 exact deltas are restored and source/GN verified, then promoted to a current-workflow head. Old APK completion is not inherited: compilation runs again to produce a current verified APK state, followed by full archive and fresh probe.

Workflow handoffs use `{{ .Environment.CIRCLE_WORKFLOW_ID }}` rather than pipeline ID so a workflow rerun cannot collide with an immutable cache key from an earlier workflow instance. These are immutable run handoffs, not general dependency caches. CircleCI documents both the template and workflow identity semantics: https://circleci.com/docs/guides/optimize/caching/ and https://circleci.com/docs/reference/variables/ . Runtime content checks remain required because restore keys can prefix-match.

Resume runtime phases are implemented and host-tested. They remain unproven against live native cache transport until a service run verifies them.

The five-row/no-scroll accessibility exceptions documented in `NATIVE_UI_INTEGRATION_REVIEW.md` remain separate acceptance questions. Generating CI configuration is not feature completion or permission to silently change those requirements.

## Local verification

Ten generator tests pass (including generated shell and embedded Python parsing): opt-in/branch ordering, exact old cache keys, seed/full-readback ordering, fresh validator before compile, every slice archival before completion, separate full archive/fresh probe, and no normal-config mutation. YAML serialization round-trips. These tests do not execute native cache transport or establish a successful Chromium build.

## Completed-progress archive recovery

Set `native_resume_completed=true` with the exact progress receipt ID and exact
native progress cache key only for an APK-verified progress checkpoint whose full
archive has not finished. The separate three-job recovery workflow verifies the
old same-commit/scope receipt, restores its exact chain, verifies source/features,
GN, actual APK signature/ZIP/ABI/package/hash, and creates a new-workflow
**authorization referencing the unchanged original receipt**. It never rewrites
old workflow provenance or produces a completion-halt marker.

A second fresh job consumes that authorization, restores the same chain and
rechecks the actual source/GN/APK before the existing full capture/save/clear/
readback path. The final fresh probe remains unchanged. There are no compilation
slices in this recovery route; each job uses its own original one-hour clock.
Normal final-archive `prepare-archive` admission is unchanged. Partial progress
uses the existing explicit resume route with this boolean false. Mismatched
completion kind, recipe, source, receipt, cache, signature, or worker boundary
fails closed. This is host-tested orchestration, not evidence of a live cache
restore, Android compilation, service validation, or successful remote archive.

### Fresh-worker APK verifier runtime

The exact Chromium 158 revision's DEPS declares
`src/third_party/jdk/current`, CIPD package
`chromium/third_party/jdk/${platform}`, version
`version:2@jdk-25.0.5+8.a4d27635bd.cr0`.
Source inspected: https://chromium.googlesource.com/chromium/src/+/52bdd21723d5db0c9ab11716d38feac74828cf84/DEPS
Its JDK README also identifies `//third_party/jdk/current` and describes `bin/java`
as a wrapper. APK verification now explicitly selects this restored JDK through
JAVA_HOME and PATH, executes its Java version check, and fails closed if absent,
non-executable, escaping the verified tree, or unusable. It never silently uses
an inherited machine-image Java. This applies to compile verification, completed
resume validation/pack validation and final fresh probe through their shared
`verify_apk` function. The JDK payload is part of the hash-verified restored
workspace; this helper does not independently download or invent its pin.

Before any restore, the complete host test guard uses a separately installed
Ubuntu `openjdk-21-jdk-headless`, with explicit JAVA_HOME/PATH and executable
Java/javac checks. Apt update/install are bounded to 240/420 seconds and occur
after the original job clock begins. This host test compiler is not the APK
verification JDK; APK verification overrides it with the restored pinned JDK.

## First service parse: #1403

The first authorized service attempt rejected configuration before workflows or compute: the same compile job was a member of both fresh and resume job groups. Mutually exclusive workflow conditions do not isolate CircleCI job-group membership. The repair generates distinct resume job definitions and a distinct recovery probe, byte-value identical to their original job implementations, with only group-local dependencies. A regression now checks globally unique membership, local dependencies and unchanged job definitions. Normal Full is unchanged. This is a configuration repair, not a source, checkpoint or UI fix.

## Second service parse: #1404

CircleCI then rejected an unescaped shell heredoc `<<'PYCODE'` before compute. Native command generation now emits the required escaped literal `\<<'PYCODE'` while retaining real `<< pipeline... >>` expressions unchanged. A lexical regression audits every string in both native and merged configurations; Bash and embedded-Python syntax checks emulate CircleCI removing the escape before execution. All 44 native heredoc occurrences are covered. This does not alter the executed shell payload or normal Full jobs.

## First executed seed job: #1405

Service configuration was accepted. The seed job stopped after about 7m09s in tool setup (exit124), before cache restore or compilation. Its log reports zstd and python3-yaml already installed, and four existing OpenJDK21 packages unnecessarily upgraded (132MB). Package setup messages precede the timeout; the log does not identify a specific hanging post-install hook. The corrective requirement is capability-first setup: use verified existing tools without apt work; install only missing prerequisites under a bounded, noninteractive, no-upgrade path. The original job clock must not be reset, and prior baseline archives remain untouched.

## Seed preflight: #1406

Capability-first setup passed in one second with no apt work. Two real-checkout transport tests then failed the unchanged clean-tree gate. Earlier stderr identifies the cause: checkout could not read 11 historical baseline blobs, including `.circleci/config.yml`, the old feature manifest and old helper scripts. The pinned baseline commit/tree existed in CircleCI's partial checkout, but their object contents were incomplete. This was not evidence of another test mutating the baseline. Recovery must verify the complete frozen Git object closure before checkout, fetch the same exact SHA without blob filtering when needed, then repeat closure and clean-tree verification. No archive restore or compilation occurred.
