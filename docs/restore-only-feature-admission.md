# Regular RawS Full: local restore-only recipe boundary

Use the existing Full workflow with `run_raw_full=true` and
`raw_full_restore_only=true`. This is a single-job execution option,
not a new product or archive format. The exact #1396 receipt, exact base,
checkpoint verifier and compiler fingerprint do not change. All cache
saves, cold source setup and continuation jobs are excluded.

No feature is admitted as of this change. A reviewed candidate supplies
`raws-adblock/production-restore-recipe.json` with fields `schema` (1),
`baseline_fingerprint`, `chromium_revision`, and `files`. Each entry in
`files` maps a Chromium-relative path to `before_sha256` (null for a
generated file), `after_sha256`, and optional `mode` (`644` by default;
the exact executable dependency leaves explicitly use `755`). Non-Brave
postimages are placed in `raws-adblock/production-postimages/<after_sha256>`.
The Brave bytes instead come from the fixed disposable
`.raws-staged-engine/brave` dependency staging tree, rehashed against the
manifest before any Chromium source write. The default/off build never needs
this stage. The code must pin the
manifest digest after review; an unpinned recipe or a missing pinned recipe is
a hard error. The manifest is data only and cannot supply commands or cache
keys. Only four exact Chromium tracked paths, two exact list-resource paths
and the approved manifest's component files are supported. The sole
`src/brave` exception is the stage.py dependency slice from Brave Core
`bd6d26d1bced03c17a98baa86d2cd3425d543d1b`, frozen independently as 1,625
exact path/mode entries under 94 existing selected roots plus LICENSE and
Cargo.lock. The sole nonexistent, inactive cssparser-v0_29 vendor dir from
the original discovery does not admit any files. Both staged and installed
owned trees must match the manifest exactly, including inferred directory
structure, with no preexisting owned roots or symlinks. Staging orchestration
remains to be wired before activation; the runtime gate never fetches vendor
bytes or accepts a full Brave checkout.

The original source verifier checks the restored baseline before any feature
write. One separately fingerprinted, exact postimage overlay is applied and
validated before and after build setup. The compiler regenerates and validates
the official graph and writes its feature recipe digest into job-local evidence.
An old APK is never output proof. A feature artifact is usable only after
compilation and the existing APK checks succeed. This transition does not
publish a cache or create a compatible feature checkpoint for other runs.

Local Git fixture tests exercise admission boundaries. They do not establish
real cache availability, complete engine dependency/linkage, Android compilation,
or browser behavior. Those remain separate acceptance gates.
