# Sandium Native Shields + uBlock Filter Compatibility

Status: source audit / implementation branch
Base: `3c8004b0b01a3e7b65daee40d84c971048fe43ae`
Brave Core pin: `v1.98.62`
Branch: `sandium/shields-native-poc`

## Product requirement

Sandium's default blocker must remain Brave's native Shields/adblock-rust engine. It must consume uBlock Origin-authored static filter lists and provide a persistent, first-class My filters editor. The feature must not require the uBO extension or wait for an extension background process.

## Confirmed reusable implementation in Brave Core v1.98.62

- `components/brave_shields/content/browser/ad_block_custom_filters_provider.cc`
  - Reads and writes `prefs::kAdBlockCustomFilters`.
  - Loads the stored text into the native Rust `adblock::FilterSet`.
  - Notifies the native filter engine when custom text changes.
  - `UpdateCustomFiltersFromSettings` has a developer-mode guard; the Android Mojo service currently calls the lower-level update method directly.
- `components/brave_shields/content/browser/filter_list_service.cc`
  - Exposes native Android Mojo operations for filter lists, subscriptions and custom filter text.
- `android/java/org/chromium/chrome/browser/shields/CreateCustomFiltersFragment.java`
  - Existing Android multiline custom-filter editor; loads and saves through the native Mojo service.
- `android/java/org/chromium/chrome/browser/shields/ContentFilteringFragment.java`
  - Existing Android filter-list and custom-subscription settings screen.
- `components/brave_shields/core/browser/ad_block_component_installer.cc`
  - Registers the remote filter-list catalogue and filter components.

## Key implementation decisions

1. Preserve one native filter engine. Do not add a parallel Java/Kotlin blocker and do not make the uBO extension a dependency.
2. Audit the pinned catalogue and resource bundle before adding lists. Prefer the actual uBO project lists supported by the pinned catalogue; avoid duplicate EasyList/EasyPrivacy or duplicate uBO lists.
3. Keep user static rules in the existing native custom-filter preference/provider path. Verify that updates invalidate/rebuild the compiled DAT cache and survive browser restart.
4. Make the Android editor discoverable as **My filters** (Sandium wording/branding), with multiline editing and save feedback. Add import/export only after confirming the Android file-picker and storage patterns in this source pin.
5. Separate ordinary static rules from privileged/trusted scriptlets. Never silently grant trusted execution to arbitrary pasted text. Gate privileged rules behind an explicit developer-mode setting and user warning.
6. Test syntax against the pinned adblock-rust version. Do not claim full uBO extension parity: dynamic rules, logger, trusted filters and some procedural/scriptlet features are extension/runtime-specific or resource-dependent.

## Required source audit before app-code changes

- Identify the exact filter-list catalogue component version, source URL, UUIDs and enabled-by-default flags.
- Verify which uBO-authored lists are already included, which are optional, and whether list titles/IDs collide with existing lists.
- Trace custom-filter pref registration, sync/local-state scope and migration behavior.
- Trace custom-filter provider observer notifications through engine rebuild and DAT cache invalidation.
- Verify the Android settings route, editor input type, save path and developer-mode behavior.
- Confirm resource replacement, procedural operators and scriptlet resources supported by the pinned Rust engine; classify each as supported, partial or unsupported.

## Acceptance tests (no extension installed)

- Network block: `||ads.example.test^`
- Network exception: `@@||ads.example.test/allowed^`
- Cosmetic rule: `example.test##.advertisement`
- Domain-scoped cosmetic rule and a malformed-rule case.
- Custom list subscription add/enable/disable/delete.
- Save custom rules, force-stop, relaunch, and confirm rules still apply.
- Change custom rules after DAT cache exists; confirm updated rules apply and stale compiled data is not reused.
- Cold-start measurement with a warm DAT cache and with a cache rebuild.
- Confirm no uBO extension process is required for any native test above.

## Build safety

This branch is intentionally excluded from the current CircleCI Full Mode and Fast Mode branch allowlists. Do not add it to those allowlists or trigger a full APK build until the source audit and patch review are complete. The accepted Full Mode branch and commit remain unchanged.
