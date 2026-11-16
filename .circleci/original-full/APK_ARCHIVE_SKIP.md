# Verified APK skips the large handoff (16 November 2026)

The stage-1 run in pipeline #1207 built and exported a validated APK but still
entered the original Full archive path. That archive was a workflow stage
handoff, not a renewal of the fixed reference. It was unnecessary after the APK
was ready. The user explicitly approved skipping it.

## Narrow orchestration change

After the existing APK validation/export, native artifact upload, and small
revision/workflow-scoped completion-marker cache save, a new gate:

1. Checks all existing completion flags and the removal-audit flag. When they
   are true, it halts the job successfully before checkpoint validation,
   compression, large cache upload, and the archive-receipt completion gate.
2. Continues into the unchanged eight-shard handoff only for an incomplete,
   attested time-slice (`TIME_SLICE_COMPLETE`, expiry true, handoff allowed).
3. Fails without archiving if APK validation is incomplete after a supposedly
   successful build, or if the build status is missing/unattested. Genuine
   compiler failures still fail earlier under the existing fail-fast policy.

Stages 2–5 retain their existing revision/workflow-scoped completion-marker
checks before large restore or source preparation, so a producing stage lets
later stages halt quickly. Small marker/identity cache saves remain intentional;
the request is to avoid the large archive, not to remove completion signalling.

The fixed base, source pins, product overlays, build budget, archive mechanics
for unfinished slices, and expiry-only reference maintenance are unchanged.
Ordinary runs never promote compiled state into the fixed reference.

## Validation and limits

`test_apk_archive_skip.py` executes the serialized gate with a stub CircleCI
agent: verified APK at each of five stages, incomplete attested slices, missing
and false validation flags, unattested status, artifact/marker ordering, and
downstream shortcut ordering. The tests do not replace an actual CircleCI
native `step halt`/cache round trip or an Android device test.

Validation completed before publication: 262 active product/general tests
passed (one pre-existing Java-tool availability skip), 49 original-Full focused
tests passed, and 19 retired architecture cases passed against their historical
fixture. The exact lightweight continuation self-test passed, as did syntax
checks of all 38 generated shell commands. Independent review reproduced the
candidate, digest and provenance from the generator and confirmed the only
pipeline task change is this inserted gate.

Rollback is the single archive-skip commit. It restores the prior unconditional
Full handoff after a completed APK without changing the accepted fixed base.
