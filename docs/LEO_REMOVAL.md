# Leo compile-out candidate

Pinned Brave 44a84b1; apply after existing overlays and before final GN regeneration. Required GN `enable_ai_chat=false`; subordinate tab-management/agent flags derive false. Origin paid entitlement remains unchanged. Shared billing removal is independently supplied by annoyance_update and required before final audit.

Removes exclusive Java classes, JNI registration, Java Mojo dependency, Plans manifest activity, exclusive settings/layout/drawable registrations. Removes Android native tab observer/WebMCP injector and unconditional AI target dependency. Shared Java callers removed from Activity, omnibox, settings, clearing history, sync, widget, adaptive toolbar and menus. Widget preview and settings row removed. Normal search/voice, tab browsing, local history clearing and private widgets retained. Appearance retains migration from obsolete persisted LEO toolbar choice to normal default.

Protocol-only exceptions: upstream browser/sources.gni172-176 intentionally retains //brave/components/ai_chat/core/common/mojom for shared NTP WebUI compilation (upstream issue53190). Exact buildflag targets also remain. No AI engine/service/provider/injection targets are allowed by audit. Shared IDs/string/icon metadata may remain for persisted selections and common resource contracts; these are not callable feature paths.

Verification: four helper regression tests; pristine-source apply twice identical; all transformed Java parses without errors using tree-sitter-java; XML resources parse (manifest is upstream XML fragment, not standalone XML). No GN generation, Android/JNI compilation, APK or runtime claim. Upstream tests specifically expecting removed Leo UI/classes need rebase before full test-suite success; they are not disabled here. Existing profile AI data migration/deletion policy is unresolved; patch does not destructively erase prior user data.

Use audit-sandium-leo-removal.py --core CORE --deps-file DEPENDENCIES --report REPORT, with actual `gn desc OUT //brave:brave deps --all` listing. Source-only grep is not product proof.

Touched pinned paths:
- `android/brave_java_sources.gni`
- `build/android/config.gni`
- `android/java/AndroidManifest.xml`
- `android/BUILD.gn`
- `browser/android/BUILD.gn`
- `browser/android/brave_tab_features.cc`
- `browser/android/brave_tab_features.h`
- `android/java/org/chromium/chrome/browser/app/BraveActivity.java`
- `android/java/org/chromium/chrome/browser/settings/BraveMainPreferencesBase.java`
- `android/java/org/chromium/chrome/browser/browsing_data/BraveClearBrowsingDataFragment.java`
- `android/java/org/chromium/chrome/browser/sync/settings/BraveManageSyncSettings.java`
- `android/java/org/chromium/chrome/browser/settings/AppearancePreferences.java`
- `android/java/org/chromium/chrome/browser/ui/BraveAdaptiveToolbarUiCoordinator.java`
- `android/java/org/chromium/chrome/browser/omnibox/suggestions/BraveAutocompleteMediator.java`
- `browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/BraveDropdownItemViewInfoListBuilder.java`
- `browser/ui/android/omnibox/java/src/org/chromium/chrome/browser/omnibox/suggestions/BraveOmniboxViewHolderFactory.java`
- `android/java/org/chromium/chrome/browser/widget/quickactionsearchandbookmark/QuickActionSearchAndBookmarkWidgetProvider.java`
- `android/java/org/chromium/chrome/browser/tabbed_mode/BraveTabbedAppMenuPropertiesDelegate.java`
- `browser/ui/android/omnibox/BUILD.gn`
- `browser/ui/android/toolbar/java/src/org/chromium/chrome/browser/toolbar/adaptive/settings/BraveRadioButtonGroupAdaptiveToolbarPreference.java`
- `android/java/brave-res/layout/quick_action_search_and_bookmark_widget_layout.xml`
- `browser/ui/android/toolbar/java/brave-res/layout/brave_adaptive_preference_buttons.xml`
- `android/java/brave-res/xml/brave_main_preferences.xml`
- `android/java/brave-res/layout/widget_search_preview.xml`
