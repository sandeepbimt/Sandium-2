# Distinct RawS test APK workflow

This is an opt-in, project-scoped test identity. It is not a production
release or a way to bypass device security warnings. A normal RawS build does
not use the new workflow or new signing context.

Enable only `run_raw_signed_test=true`, on `raw-sandium/official158`, leaving
all other booleans at their defaults. Mixing the flags schedules neither the
signed-test workflow nor an ordinary build. Both workers verify the checked-out
revision. The same RawS serial group keeps the compile-to-sign chain together.

The compile worker restores the exact approved #1396 archive as a read-only
input. It has no signing context, no cache writes, no artifact upload and no
alternate seed. Only `candidate.apk` and `receipt.json` cross the workflow
workspace. The signing worker does not compile, restore checkpoints, or
attach a remote build cache. The signature verifier must reject a different
workflow, commit, artifact digest, package or project key. Verified output is
published only after a successful atomic directory move.

Before enabling, configure the restricted CircleCI context
`RawS-Test-Signing` for the intended project and reviewed, protected branch.
Use an access group appropriate for the project and disable SSH reruns by
context restriction. Restrict who may modify the CI config and the signing
tool. Do not put signing credentials in project-wide variables, build
parameters, source, workspaces or caches. Use the separately identified RawS
test key, not any production or default Chromium key.

Before placing credentials there, set only the nonsecret canary
`RAWS_SIGNING_CONTEXT_CANARY=raws-test-signing-probe-v1` and trigger
`run_raw_signing_probe=true` alone. The single probe job does not check out
source, pull or push a cache, compile, sign, or publish artifacts. It fails
if any signing credential variable is present, including as an empty value,
then verifies the same official Android Build Tools archive used by the
signer. Use it to verify restricted context transfer and SDK bootstrap on
the approved branch before provisioning the key.

Context inputs:

- `RAWS_TEST_KEYSTORE_B64`, `RAWS_KEYSTORE_PASSWORD`, `RAWS_KEY_PASSWORD`:
  test signing credentials; never log their values.
- `RAWS_TEST_SIGNER_PIN_SHA256`: expected exact test certificate fingerprint.

The official Linux Android Build Tools 36.0.0 archive is source-pinned at
63,737,259 bytes and SHA-256
`5d9ac77fb6ff43d9da518a337b4fcf8f9097113df531d99ccefe80ef7ce8250b`.
Both jobs reject mismatches before extraction and verify revision 36.0.0
under `/tmp/raws-signer-sdk/android-16`. An SDK upgrade requires reviewed
source changes; no context variable can replace the pinned digest.

The old `org.chromium.chrome` package and signer are not accepted here. Do not
uninstall a browser or allowlist a result merely to make a test pass. Start a
new checked-out pipeline instead of re-running into an old workspace if
anything about source or signing identity changes.
