# Exact #1402 follow-up provenance

The active baseline is the frozen `bba47961` configuration in
`tests/fixtures/1402-approved-ui/baseline-config.yml.gz`. The new
`1402-step-provenance.json` binds its full commit, Git blob and SHA256, and the
unchanged historical `step-provenance.json` SHA256.

The original fc220e7f file and historical task-index evidence remain unchanged.
Every historically byte-identical task still has exactly one matching task in
#1402 under the existing namespace normalization. The new mapping records that
location explicitly. The active task must equal the frozen #1402 task without
normalization; all complete job objects must also remain equal. Thus inserted
historical tasks do not silently shift the evidence onto unrelated tasks.

#1402 intentionally has no experimental-head fallback. Its exact verified
stage-2 reference key is asserted instead; the prohibitions on current-head
capture and reference promotion remain. Only the five build workflow branch
filters move from `fix/1394-official-lint` to `work/1402-approved-ui`; the separate
structural fixture test checks that exact delta. Maintenance remains unchanged.

This is test/provenance migration only, not a pipeline behavior change and not
Full-U activation.
