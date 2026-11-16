# Build #1223: reviewed copied-resource inventory mismatch

## Evidence

Commit `7dc21601d2203e238ace045396a3d0f59bd363c2` failed in
`product-overlay-30-0.sh` during the UI/removal composition audit, before Android
compilation. `sync-sandium-removal-overlays.py` raised
`ValueError: Unreviewed UI-owned copied resource`. Stages 2–5 did not run.

The production removal recipe now registers
`android/java/res/xml/developer_preferences.xml` in both `core_restore` and
`ui_only_core_restore`, for the final browser-branding hint correction. The
resource publisher's explicit UI allowlist still contained only the two color
files. Their set difference reproduces precisely the developer XML omission.

## Correction and regression

Add only that reviewed developer XML to the allowlist, preserving the existing
source-to-Chromium mapping. Do not broaden copied roots, bypass the inventory
check, or recopy all resources. Unknown additions still fail before writes.
Include rejected paths in future diagnostics.

The added host test uses the actual production recipe, rather than constructing
its inventory from the allowlist under test. It failed with the exact CI error
before the fix; afterwards it publishes five reviewed resources and verifies
idempotence, the branded developer hint, original copyright, and preservation
of an unrelated compiled customization. Existing tests retain unknown-input,
removed-reference and symlink rejection checks.

This corrects a deterministic pre-build guard failure. It does not establish
Android compilation or runtime success; those require the next Full build and
APK testing. The complete source composition replay requires the pinned
Chromium checkout/fixtures and remains enforced in CI.
