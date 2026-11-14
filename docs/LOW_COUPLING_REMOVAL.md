# Lower-coupling removal package

Pin audited: Brave `44a84b1f89d9a35287289d6a3d493e362f5a5123` (actual checkout HEAD verified). Product baseline supplied by coordinator: Sandium `104df3f`.

## Six groups

- Email aliases: upstream derived `enable_email_aliases` is false on Android; not a valid `--gn` override. Native service/UI dependencies in browser/sources.gni are conditional.
- Speedreader: upstream Android default excludes; enforce `enable_speedreader=false`.
- Talk: enforce `enable_brave_talk=false`; generic website WebRTC untouched.
- Tor: enforce `enable_tor=false`; Android defaults false, normal private browsing untouched.
- Wayback: enforce `enable_brave_wayback_machine=false`; Android defaults false, browsing archive.org unaffected.
- Web Discovery: enforce BOTH `enable_web_discovery_native=false` and `enable_web_discovery=false`. Native browser, renderer, extension API and browser-core sources are conditional. Existing runtime hiding is insufficient for the Android pref/control residue.

## Actual additional changes in this package

`apply-sandium-low-coupling-removal.py` removes WDP search-settings control code/XML, its generated WebDiscoveryPrefs Java dependency, old onboarding enable setter, WDP adapter page/viewholder/callback and five exclusive layout registrations. Coordinated reporting cleanup also removes MakeBraveBetter reporting page/viewholder/setters/callbacks, its layout registrations, and Welcome reporting consent callsites. The remaining blocker introduction is step0 and its Continue dismisses onboarding. Local diagnostics elsewhere are untouched. It also replaces the legacy Origin destination with a neutral explanatory page retaining the class/extra-key caller contract but no controllers, entitlement calls, purchase or feature toggles. Old Origin XML is excluded from packaging. This does not bypass or grant Origin purchases, nor does it delete the shared native Origin service.

Apply **after** existing functional/branding/welcome/UI-prune overlays, before final GN regeneration. Must reset touched source to the pinned baseline before reapplying old overlays on restored runs; the old prune test expects the WDP XML row and cannot run after this final removal. The final absence audit supersedes that earlier UI-hiding expectation.

Touched pinned files:
- `android/java/org/chromium/chrome/browser/settings/BraveSearchEnginesPreferences.java`
- `android/java/org/chromium/chrome/browser/firstrun/WelcomeOnboardingActivity.java`
- `android/java/org/chromium/chrome/browser/settings/BraveOriginPreferences.java`
- `android/java/brave-res/xml/brave_search_engines_preferences.xml`
- `build/android/config.gni` (one generated WDP pref dependency removed)
- `android/BUILD.gn` (one Origin XML source removed)
- `browser/first_run/android/BUILD.gn`
- `browser/first_run/android/java/src/org/chromium/chrome/browser/firstrun/OnboardingStepAdapter.java`
- `browser/first_run/android/javatests/src/org/chromium/chrome/browser/firstrun/OnboardingStepAdapterTest.java`

## Audit contract

`audit-sandium-low-coupling.py --src SRC --out OUT --report REPORT` queries generated full `//brave:brave` dependency closure and direct `//brave/browser:core` sources. It rejects implementations from all six group prefixes, permitting only exact compile-time buildflag metadata actions. Both stderr and stdout are reported on GN failure; established Brave Python paths are supplied. Optional deps/source fixture files allow offline audit tests. Android residual controls/packaging targets are verified separately.

This is NOT complete APK or runtime proof. Shared strings/legal metadata can remain. Post-build DEX/resource/manifest/link inspection and runtime/upgrade checks remain necessary. Tests cannot claim absence simply from false GN args. Actual graph execution remains CI work.

## Verification

Six fixture tests cover graph rejection for every group, buildflag metadata allowance, unexpected target rejection, direct browser sources, Java pref generator and no-entitlement Origin shell. Exact pinned settings/onboarding transformations, composed with current Sandium welcome overlay, run twice successfully and pass source audit.

Android compilation, generated GN execution, device UI, native runtime and adapter Robolectric execution remain pending. Upstream adapter tests are rebased to the remaining single blocker introduction: count/type, Continue dismissal and recycle remain covered. Tests for deleted WDP/reporting behavior are removed, not ignored. No publishing or build performed by this package author.
