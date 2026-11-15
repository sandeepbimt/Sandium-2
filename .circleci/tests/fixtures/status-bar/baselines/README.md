# Hermetic status-bar migration baselines

These are exact historical Sandium transformation scripts, not production overlays.
`provenance.json` records each full source commit/path and SHA-256. Tests verify
that digest before loading them. Keeping the bytes in-tree makes shallow CI and
archive checkouts independent of developer-only Git objects.

#1177 failed before compilation because its status test tried `git show 9ba8861`,
a local review commit never published as that object. The published tree had an
equivalent script, but CI was not guaranteed to contain the local commit.

The previously skipped `4b4aa9d` migration case uses the published navigation
baseline `d6b31ba` instead, which is available and explicitly recorded. It verifies
migration to the current full spacer output, not undo-to-pre-spacer output. Its
old zero-top-height assertion now checks top height equals the native status
spacer, as required by the reviewed spacer design. No production guard changed.

Validation includes running all 19 status tests from a Git-free archive, with no
skips. These remain source contracts, not Android or device-rendering proof.
