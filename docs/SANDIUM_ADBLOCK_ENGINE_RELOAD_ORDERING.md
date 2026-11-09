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

## Regression coverage

NewestFilterSetBuildWinsWhenOlderBuildFinishesLast uses a delayed test provider. It deliberately holds an older build, lets a newer build containing a test blocking rule finish and activate, then releases the old build. The test verifies that the rule remains active after the stale build completes.

The existing provider notification and DAT-cache tests remain in place.

## Validation

The Fast Mode lightweight test runs the patcher's fixture/idempotency tests. The ARM64 APK build compiles the modified native Brave source. The new C++ regression test is added to the existing ad_block_service_unittest.cc target; it must also be run in a native test build before declaring runtime regression coverage executed.