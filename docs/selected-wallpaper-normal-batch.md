# Selected wallpaper: current normal build batch

Sandeep selected Quiet Charcoal on 2026-11-16. This change belongs only to the
current normal-build batch, not the separate emulator translation experiment.
It does not establish a policy to propagate the wallpaper to other branches.

The supplied PNG (819 x 1920, SHA-256
`f7eacf40403809ad74d97662146b0db81736635e679c54cc768ac8e7ce9ee384`)
is packaged as lossless WebP. RGB pixel equality was verified against the PNG.
The existing bundled drawable resource is replaced, not profile preferences or
custom image files. Default-wallpaper users see the selected artwork on fresh
installation and upgrade. Background-disabled users remain background-disabled.
No custom-wallpaper selection logic is added, removed, or reset. Existing upstream
custom selection behavior is unchanged; this is not an APK-level claim that a
custom photo feature exists or was exercised.

The bundled resource focal point moves from (270, 480) for the old 540 x 960
asset to (409, 960) for the new 819 x 1920 asset. Old branded source checkpoints
are migrated idempotently before the normal overlay. No default preference is
written on startup or upgrade.

Validation: lossless pixel comparison; three selected-wallpaper packaging tests
(fresh resource install, old resource replacement/replay, unchanged mock profile
preferences, checkpoint focal geometry); seven branding checkpoint tests.
Device install/upgrade and rendered crop inspection still require the built APK.
