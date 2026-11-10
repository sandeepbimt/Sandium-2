# Sandium native ad-block engine reload ordering

## Symptom

On a fresh install, the first page can initially behave as though Brave's native ad-block engine has not yet activated. Opening Content Filtering and switching one enabled subscription off and on makes blocking start. A successful filter download or a non-zero source-rule count alone does not prove that the active engine has consumed the current provider set.

## Source-level cause addressed

The pinned Brave v1.98.62 subscription providers notify the filter-provider manager independently. Each accepted provider notification starts an asynchronous aggregation and engine-build pipeline:

1. `AdBlockFiltersProviderManager::OnChanged`
2. `AdBlockService::SourceProviderObserver::OnChanged`
3. `LoadFilterSetForEngine`
4. `SourceProviderObserver::OnFilterSetLoaded`
5. `OnFilterSetCreated`
6. `LoadResources` / `OnAllLoaded`
7. `AdBlockService::OnResourcesLoaded` and the engine wrapper

When DAT caching is enabled, Brave intentionally consumes the first startup provider-change notification. That optimization is appropriate when a complete cached DAT is already being loaded. Sandium, however, registers its URL subscriptions during native service startup. This can leave the freshly registered provider set without the explicit rebuild notification that a user-triggered OFF/ON operation later causes.

The normal Android toggle path is:

`ContentFilteringAdapter` → `ContentFilteringFragment.onSubscriptionFilterToggle()` → `FilterListAndroidHandler.enableSubscription()` → `FilterListService::EnableSubscription()` → `AdBlockSubscriptionServiceManager::EnableSubscription()`.

When the subscription is enabled, the native manager creates an `AdBlockSubscriptionFiltersProvider`, calls `OnListAvailable()`, and that calls `NotifyObservers()`. The observer chain above then rebuilds the engine. Sandium's startup patch reproduces the underlying provider-manager notification, not the UI action or the preference mutation.

## First-launch native activation

After `OnGetDownloadManager()` has called both `LoadSubscriptionServices()` and `EnsureSandiumDefaultSubscriptions()`, Sandium issues one explicit notification for the additional engine (`ForceNotifyObservers(false)`). This is guarded by the existing `kSandiumAdBlockEngineWarmupDone` preference and sets `kSandiumAdBlockEngineWarmupRequested` before dispatch.

The existing `ForceNotifyObservers` implementation is deliberately used: it clears the one-time DAT-cache startup-notification suppression, remembers a pending request if providers are not yet initialized, and notifies the engine observer when the complete provider set is ready. The same asynchronous filter-set loading, resource loading, and engine update code used by the normal subscription-toggle path is therefore exercised.

This startup operation does **not** call `EnableSubscription`, change any subscription's enabled state, write subscription preferences, force a filter download, call the Brave component-catalogue updater, or add a Java/Mojo/New Tab Page hook. Normal download completion still calls `OnListAvailable()`, so newly downloaded source content is loaded through Brave's existing notification path.

The warm-up request is considered complete only after the additional engine reports a successful `FilterListLoadResult::kLoaded`. On later launches after that success, the explicit first-launch request is skipped and Brave's normal DAT-cache startup behavior remains in place.

## Asynchronous download boundary

This activation fixes the missing initial engine-rebuild notification. It does not make remote list downloads synchronous and does not create filter data that is not already in the profile cache. On a genuinely fresh/offline install, the 29 selected URL subscriptions still need their first successful downloads before their full rules can be enforced. Until then, the engine can be initialized but some or all subscription rule data may not yet be available. A guaranteed offline first-page baseline requires a separately maintained rules snapshot bundled in the APK, which is outside this change.

## Concurrent reload ordering

The first-launch bootstrap creates subscriptions separately, and each successful subscription download notifies again. These operations can overlap. An older aggregation can finish after a newer, more complete aggregation and publish its older filter set last.

The native reload-race patch adds a monotonically increasing generation to each `SourceProviderObserver`. Every provider change advances the generation. The generation is carried through provider aggregation, filter-set creation, and resource loading. Stale completions are discarded at each asynchronous boundary; only the newest requested build can be published.

This does not change filter URLs, filter contents, subscription enablement, refresh behavior, or the selected list catalogue.

## Regression coverage

The offline patcher test verifies that the startup activation is idempotent, occurs after subscription seeding, precedes update scheduling, targets only the additional engine, and does not call the toggle API or write subscription preferences.

The reload-race patcher adds C++ regression cases for a forced notification bypassing DAT-cache startup suppression and for a forced notification waiting until provider initialization. The latest-build-wins test uses a delayed provider to verify that a stale asynchronous build cannot overwrite the newest filter set.

## Validation

The CircleCI Full Mode pipeline runs the pin guards and offline patcher tests, applies the native startup activation after the provider-manager reload API, then builds the ARM64 Release APK using the existing Siso/remote-execution configuration. A passing patcher test proves source transformation and ordering; it does not prove runtime enforcement. Final acceptance still requires installing the generated APK on a clean profile, opening a first website before visiting filter settings, and checking that the expected ads are blocked. Also test slow/offline first-run behavior separately because source downloads remain asynchronous.
