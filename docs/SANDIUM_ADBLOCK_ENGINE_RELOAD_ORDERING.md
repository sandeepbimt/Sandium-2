# Sandium native ad-block engine reload ordering

## Symptom

On a fresh install, URL filter subscriptions can finish downloading and show non-zero rule counts while the active ad-block engine still behaves as though some rules are missing. Toggling an affected subscription off and on causes blocking to start.

## Source-level cause addressed

The pinned Brave v1.98.62 subscription providers notify the filter-provider manager independently. Each notification starts an asynchronous aggregation and engine-build pipeline:

1. AdBlockFiltersProviderManager::OnChanged
2. AdBlockService::SourceProviderObserver::OnChanged
3. LoadFilterSetForEngine
4. SourceProviderObserver::OnFilterSetLoaded
5. OnFilterSetCreated
6. LoadResources / OnAllLoaded
7. AdBlockService::OnResourcesLoaded and the engine wrapper

The first-launch bootstrap creates subscriptions separately, and each successful subscription download notifies again. These operations can overlap. An older aggregation can finish after a newer, more complete aggregation and publish its older filter set last. Rule counts in the Content filters UI are read from cached list text; they do not establish which aggregate is currently active in the engine.

The native patch adds a monotonically increasing generation to each SourceProviderObserver. Every provider change advances the generation. The generation is carried through provider aggregation, filter-set creation and resource loading. Stale completions are discarded at each asynchronous boundary; only the newest requested build can be published.

This does not change filter URLs, filter contents, subscription enablement, refresh behavior, or the selected list catalogue.

## First-install engine warm-up

The warm-up is triggered when Chromium's NewTabPage reports that the
homepage is actually visible (`recordNtpShown()`), not during profile
construction or while a background NTP is loading. The Java homepage hook calls
a narrow Mojo method on FilterListService, which delegates to AdBlockService.

AdBlockService records the request with the subscription manager. The manager
keeps the homepage request pending in memory until every enabled subscription
has a successful-download timestamp; provider objects alone are not considered
ready because Brave's base provider reports initialized even when a cached list
file is empty. The pending request is rechecked after each successful download
and after subscription enable/disable or deletion changes.

Once every enabled list is downloaded, the manager asks the provider manager
for one explicit additional-engine rebuild. This is the native equivalent of
the engine refresh caused by toggling a filter, but it does not toggle any real
subscription, change its enabled preference, or initiate another download.
The provider manager bypasses the one-time DAT-cache startup notification
suppression. A session guard prevents duplicate rebuild requests.

The persistent warm-up-requested preference is set only when the final
subscription set is ready and the explicit rebuild is dispatched. This prevents
an earlier partial engine load from falsely marking the warm-up complete. The
warm-up-done preference is written only after the additional engine reports a
successful filter-list load. If the process exits before success, the next
homepage opening in a later session can request the rebuild again. After
success, normal DAT-cache startup remains unchanged and the forced rebuild is
not repeated on subsequent launches.

## Regression coverage

NewestFilterSetBuildWinsWhenOlderBuildFinishesLast uses a delayed test provider. It deliberately holds an older build, lets a newer build containing a test blocking rule finish and activate, then releases the old build. The test verifies that the rule remains active after the stale build completes.

The existing provider notification and DAT-cache tests remain in place.

## Validation

The Fast Mode lightweight test runs the patcher's fixture/idempotency tests. The ARM64 APK build compiles the modified native Brave source. The new C++ regression test is added to the existing ad_block_service_unittest.cc target; it must also be run in a native test build before declaring runtime regression coverage executed.