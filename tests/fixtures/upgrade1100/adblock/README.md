# Exact158 active adblock replay

41 upstream files, validated against exact Git tree blob IDs, preserve upstream copyrights.
Brave 1.100.58 bd6d26d1bced03c17a98baa86d2cd3425d543d1b and corresponding Chromium 52bdd21723d5db0c9ab11716d38feac74828cf84.

`python3 tests/test_adblock_158.py` replays subscriptions, native 30-list bootstrap, homepage warmup, generation-aware engine rebuild, resource bootstrap/DAT snapshots, and two-state Shields over real target sources. It repeats transformations at their valid pipeline stage to test idempotence. Later stage transformations deliberately supersede earlier bodies; the production pipeline resets its owned shared inputs before reconstruction.

All six source transformations fit target anchors without functional rewrites. The only production change admits the exact new pins in addition to the retained legacy pins; homepage checks the corresponding Chromium revision, rejecting cross-version pairs. This is not blanket acceptance of future tags or historical helpers.

These are host source-transformation tests, not native compile/runtime tests. Full composition, generated Mojo/Rust/C++ compilation, Android first-launch filtering and device blocking behavior remain integration gates. This does not establish uBlock engine integration: these scripts retain Brave native engine with Sandium subscriptions and resource hardening.
