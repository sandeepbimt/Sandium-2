# Feature-layer boundaries and upstream upgrades

1. **Upstream:** stock full Chromium Android browser, not content_shell/WebView.
   Do not fork Blink/V8/compositor to reproduce Sandium UI.
2. **Sandium modules:** own homepage, wallpaper/shortcut presentation, menu model,
   persisted settings, typography UI, diagnostics and Shields presentation.
3. **Adapters:** minimum explicit hooks into browser toolbar, navigation,
   profiles and request policy. Maintain reviewed patches with upstream context,
   reason, owner module and regression-test names in patches/manifest.json.
4. **Blocking:** standalone engine adapter, exactly one effective blocking owner.
   Full uBO is not filter-list reuse. Android extension APIs, content scripts,
   scriptlets, redirects, cosmetics, private profiles, readiness and updates must
   be demonstrated. Do not silently substitute Brave and call it uBO.

There is no guarantee that Chromium internals are stable plugin APIs. The layer
reduces change spread; it does not remove upgrade maintenance.

## Port order
- Build and measure untouched ARM64 Chromium on the actual phone.
- Isolated app identity/signing and branding, without importing user profiles.
- Wallpaper/homepage/shortcuts, then menu/persistence and settings.
- Toolbar visuals with upstream controls/navigation behavior retained.
- Dark-page policy and persisted correction rules, typography disabled by default.
- uBO/Shields integration and independent startup/parity tests.

Every feature is disabled until its adapter and tests exist. Use thin hooks, not
broad text replacements across upstream Java/C++. Preserve the current Sandium
branch as rollback; never overwrite user data for an experiment.

## Upgrade contract
Pin Chromium + depot_tools; review DEPS and source notices; reapply minimal
patches with exact context (failure blocks build); compile; execute feature and
navigation tests; check cold/warm/startup/back-forward/hidden-toolbar transitions,
retained settings and rule migrations; review privacy/security changes; sign only
a verified candidate. Rehearse at least one Chromium revision upgrade before
claiming this design is cheaper to maintain. No fixed upgrade-time promise.

## License/provenance boundary
Retain Chromium and third-party notices. Any copied Brave MPL2 files remain
covered by their original terms. uBlock Origin is GPLv3; distribution and source
obligations must be reviewed before embedding/releasing. Sandium's name does not
make upstream code wholly owned. Original Sandium-only files here do not relicense
any imported code. No third-party source is bundled in this scaffold.
