#!/usr/bin/env python3
"""Apply latest-build-wins protection to Brave's asynchronous adblock engine reloads."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

EXPECTED_CORE_TAG = "v1.98.62"
EXPECTED_CORE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"


def replace_once(source: str, old: str, new: str, marker: str, label: str) -> str:
    if marker in source:
        if new not in source:
            raise RuntimeError(f"{label}: marker exists but replacement differs")
        return source
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one source anchor, found {count}")
    return source.replace(old, new, 1)


def read(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"missing pinned source file: {path}")
    return path.read_text(encoding="utf-8")


def write(path: Path, transform, label: str) -> None:
    before = read(path)
    after = transform(before)
    if after != before:
        path.write_text(after, encoding="utf-8")
    if read(path) != after:
        raise RuntimeError(f"{label}: write verification failed")
    print(f"SANDIUM_ADBLOCK_RELOAD_{label}=PASS")


def transform_header(source: str) -> str:
    old_methods = (
        "    void LoadResources(\n"
        "        std::unique_ptr<rust::Box<adblock::FilterSet>> filter_set);\n"
        "    void OnFilterSetLoaded(\n"
        "        base::OnceCallback<void(rust::Box<adblock::FilterSet>*)> cb);\n"
        "    void OnFilterSetCreated(\n"
        "        std::unique_ptr<rust::Box<adblock::FilterSet>> filter_set);\n"
    )
    new_methods = (
        "    void LoadResources(\n"
        "        std::unique_ptr<rust::Box<adblock::FilterSet>> filter_set,\n"
        "        uint64_t generation);\n"
        "    void OnFilterSetLoaded(\n"
        "        uint64_t generation,\n"
        "        base::OnceCallback<void(rust::Box<adblock::FilterSet>*)> cb);\n"
        "    void OnFilterSetCreated(\n"
        "        uint64_t generation,\n"
        "        std::unique_ptr<rust::Box<adblock::FilterSet>> filter_set);\n"
    )
    source = replace_once(source, old_methods, new_methods,
                          "void LoadResources(\n        std::unique_ptr<rust::Box<adblock::FilterSet>> filter_set,\n        uint64_t generation);",
                          "generation-aware callbacks")

    old_all_loaded = (
        "    void OnAllLoaded(std::unique_ptr<rust::Box<adblock::FilterSet>> filter_set,\n"
        "                     AdblockResourceStorageBox storage);\n"
    )
    new_all_loaded = (
        "    void OnAllLoaded(uint64_t generation,\n"
        "                     std::unique_ptr<rust::Box<adblock::FilterSet>> filter_set,\n"
        "                     AdblockResourceStorageBox storage);\n"
    )
    source = replace_once(source, old_all_loaded, new_all_loaded,
                          "void OnAllLoaded(uint64_t generation",
                          "generation-aware resource completion")

    old_member = (
        "    const bool engine_is_default_;\n"
        "    const bool debug_mode_;\n\n"
        "    scoped_refptr<base::SequencedTaskRunner> task_runner_;\n"
    )
    new_member = (
        "    const bool engine_is_default_;\n"
        "    const bool debug_mode_;\n"
        "    // Async filter-set builds may finish out of order. Only the newest\n"
        "    // generation is allowed to publish rules to the active engine.\n"
        "    uint64_t filter_set_generation_ = 0;\n\n"
        "    scoped_refptr<base::SequencedTaskRunner> task_runner_;\n"
    )
    return replace_once(source, old_member, new_member,
                        "filter_set_generation_ = 0;",
                        "filter-set generation state")


def transform_service_cc(source: str) -> str:
    old_on_changed = (
        "void AdBlockService::SourceProviderObserver::OnChanged(bool is_default_engine) {\n"
        "  if (engine_is_default_ != is_default_engine) {\n"
        "    return;\n"
        "  }\n\n"
        "  auto on_loaded_cb =\n"
        "      base::BindOnce(&AdBlockService::SourceProviderObserver::OnFilterSetLoaded,\n"
        "                     weak_factory_.GetWeakPtr());\n"
        "  filters_provider_manager_->LoadFilterSetForEngine(is_default_engine,\n"
        "                                                    std::move(on_loaded_cb));\n"
        "}\n"
    )
    new_on_changed = (
        "void AdBlockService::SourceProviderObserver::OnChanged(bool is_default_engine) {\n"
        "  if (engine_is_default_ != is_default_engine) {\n"
        "    return;\n"
        "  }\n\n"
        "  // Filter providers notify independently as subscriptions are added or\n"
        "  // downloaded. Their asynchronous builds can complete out of order, so\n"
        "  // each notification supersedes every older in-flight build.\n"
        "  const uint64_t generation = ++filter_set_generation_;\n"
        "  auto on_loaded_cb =\n"
        "      base::BindOnce(&AdBlockService::SourceProviderObserver::OnFilterSetLoaded,\n"
        "                     weak_factory_.GetWeakPtr(), generation);\n"
        "  filters_provider_manager_->LoadFilterSetForEngine(is_default_engine,\n"
        "                                                    std::move(on_loaded_cb));\n"
        "}\n"
    )
    source = replace_once(source, old_on_changed, new_on_changed,
                          "const uint64_t generation = ++filter_set_generation_;",
                          "stamp each filter-set build")

    old_filter_set_loaded = (
        "void AdBlockService::SourceProviderObserver::OnFilterSetLoaded(\n"
        "    base::OnceCallback<void(rust::Box<adblock::FilterSet>*)> cb) {\n"
        "  task_runner_->PostTaskAndReplyWithResult(\n"
    )
    new_filter_set_loaded = (
        "void AdBlockService::SourceProviderObserver::OnFilterSetLoaded(\n"
        "    uint64_t generation,\n"
        "    base::OnceCallback<void(rust::Box<adblock::FilterSet>*)> cb) {\n"
        "  if (generation != filter_set_generation_) {\n"
        "    return;\n"
        "  }\n"
        "  task_runner_->PostTaskAndReplyWithResult(\n"
    )
    source = replace_once(source, old_filter_set_loaded, new_filter_set_loaded,
                          "uint64_t generation,\n    base::OnceCallback<void(rust::Box<adblock::FilterSet>*)> cb) {\n  if (generation != filter_set_generation_)",
                          "discard stale provider aggregation")

    old_created_bind = (
        "      base::BindOnce(\n"
        "          &AdBlockService::SourceProviderObserver::OnFilterSetCreated,\n"
        "          weak_factory_.GetWeakPtr()));\n"
    )
    new_created_bind = (
        "      base::BindOnce(\n"
        "          &AdBlockService::SourceProviderObserver::OnFilterSetCreated,\n"
        "          weak_factory_.GetWeakPtr(), generation));\n"
    )
    source = replace_once(source, old_created_bind, new_created_bind,
                          "weak_factory_.GetWeakPtr(), generation));",
                          "carry generation through filter-set creation")

    old_load_resources = (
        "void AdBlockService::SourceProviderObserver::LoadResources(\n"
        "    std::unique_ptr<rust::Box<adblock::FilterSet>> filter_set) {\n"
        "  // multiple AddObserver calls are ignored\n"
        "  resource_provider_->AddObserver(this);\n"
        "  resource_provider_->LoadResources(\n"
        "      base::BindOnce(&SourceProviderObserver::OnAllLoaded,\n"
        "                     weak_factory_.GetWeakPtr(), std::move(filter_set)));\n"
        "}\n"
    )
    new_load_resources = (
        "void AdBlockService::SourceProviderObserver::LoadResources(\n"
        "    std::unique_ptr<rust::Box<adblock::FilterSet>> filter_set,\n"
        "    uint64_t generation) {\n"
        "  // multiple AddObserver calls are ignored\n"
        "  resource_provider_->AddObserver(this);\n"
        "  resource_provider_->LoadResources(\n"
        "      base::BindOnce(&SourceProviderObserver::OnAllLoaded,\n"
        "                     weak_factory_.GetWeakPtr(), generation,\n"
        "                     std::move(filter_set)));\n"
        "}\n"
    )
    source = replace_once(source, old_load_resources, new_load_resources,
                          "uint64_t generation) {\n  // multiple AddObserver calls are ignored",
                          "carry generation through resource loading")

    source = replace_once(
        source,
        "  LoadResources(nullptr);\n",
        "  LoadResources(nullptr, filter_set_generation_);\n",
        "LoadResources(nullptr, filter_set_generation_);",
        "tag startup DAT resource loading",
    )

    old_created = (
        "void AdBlockService::SourceProviderObserver::OnFilterSetCreated(\n"
        "    std::unique_ptr<rust::Box<adblock::FilterSet>> filter_set) {\n"
        "  TRACE_EVENT(\"brave.adblock\", \"OnFilterSetCreated\");\n"
        "  LoadResources(std::move(filter_set));\n"
        "}\n"
    )
    new_created = (
        "void AdBlockService::SourceProviderObserver::OnFilterSetCreated(\n"
        "    uint64_t generation,\n"
        "    std::unique_ptr<rust::Box<adblock::FilterSet>> filter_set) {\n"
        "  if (generation != filter_set_generation_) {\n"
        "    return;\n"
        "  }\n"
        "  TRACE_EVENT(\"brave.adblock\", \"OnFilterSetCreated\");\n"
        "  LoadResources(std::move(filter_set), generation);\n"
        "}\n"
    )
    source = replace_once(source, old_created, new_created,
                          "LoadResources(std::move(filter_set), generation);",
                          "discard stale filter-set creation")

    old_all_loaded = (
        "void AdBlockService::SourceProviderObserver::OnAllLoaded(\n"
        "    std::unique_ptr<rust::Box<adblock::FilterSet>> filter_set,\n"
        "    AdblockResourceStorageBox storage) {\n"
        "  on_resources_loaded_.Run(engine_is_default_, std::nullopt,\n"
        "                           std::move(filter_set), std::move(storage));\n"
        "}\n"
    )
    new_all_loaded = (
        "void AdBlockService::SourceProviderObserver::OnAllLoaded(\n"
        "    uint64_t generation,\n"
        "    std::unique_ptr<rust::Box<adblock::FilterSet>> filter_set,\n"
        "    AdblockResourceStorageBox storage) {\n"
        "  if (generation != filter_set_generation_) {\n"
        "    return;\n"
        "  }\n"
        "  on_resources_loaded_.Run(engine_is_default_, std::nullopt,\n"
        "                           std::move(filter_set), std::move(storage));\n"
        "}\n"
    )
    return replace_once(source, old_all_loaded, new_all_loaded,
                        "void AdBlockService::SourceProviderObserver::OnAllLoaded(\n    uint64_t generation,",
                        "discard stale completed engine builds")


def transform_unit_test(source: str) -> str:
    source = replace_once(
        source,
        '#include "base/files/file_path.h"\n',
        '#include "base/check.h"\n#include "base/files/file_path.h"\n',
        '#include "base/check.h"',
        "explicit CHECK include for delayed provider fixture",
    )
    source = replace_once(
        source,
        '#include <string_view>\n',
        '#include <string_view>\n#include <utility>\n',
        '#include <utility>',
        "explicit utility include for delayed provider fixture",
    )
    provider_class = """// Holds the first filter-set build so a newer build can finish first. This
// reproduces the subscription startup race: list providers become available
// independently, and old aggregation work must not replace the latest rules.
class DeferredFirstLoadFiltersProvider : public AdBlockFiltersProvider {
 public:
  using AddToFilterSetCallback =
      base::OnceCallback<void(rust::Box<adblock::FilterSet>*)>;
  using LoadFilterSetCallback =
      base::OnceCallback<void(AddToFilterSetCallback)>;

  DeferredFirstLoadFiltersProvider()
      : AdBlockFiltersProvider(/*engine_is_default=*/true,
                               /*filters_provider_manager=*/nullptr) {}
  ~DeferredFirstLoadFiltersProvider() override = default;

  void RegisterAsSourceProvider(AdBlockService* service) {
    filters_provider_manager_ =
        service->GetFiltersProviderManagerForTesting();
    filters_provider_manager_->AddProvider(this, /*is_for_default_engine=*/true);
  }

  void LoadFilterSet(LoadFilterSetCallback callback) override {
    ++load_count_;
    if (load_count_ == 1) {
      pending_first_load_ = std::move(callback);
      return;
    }
    std::move(callback).Run(base::BindOnce([](rust::Box<adblock::FilterSet>*) {}));
  }

  void ReleaseFirstLoad() {
    CHECK(!pending_first_load_.is_null());
    std::move(pending_first_load_)
        .Run(base::BindOnce([](rust::Box<adblock::FilterSet>*) {}));
  }

  bool HasPendingFirstLoad() const { return !pending_first_load_.is_null(); }

  std::string GetNameForDebugging() override {
    return "DeferredFirstLoadFiltersProvider";
  }

 private:
  int load_count_ = 0;
  LoadFilterSetCallback pending_first_load_;
};

"""
    anchor = "class AdBlockServiceTestBase : public testing::Test {\n"
    source = replace_once(source, anchor, provider_class + anchor,
                          "class DeferredFirstLoadFiltersProvider",
                          "deterministic delayed provider fixture")

    test = """TEST_F(AdBlockServiceTest, NewestFilterSetBuildWinsWhenOlderBuildFinishesLast) {
  auto service = CreateService();

  // Register before the deferred test catalog notification runs. The first
  // aggregate build is held at this provider so that an older, incomplete
  // snapshot cannot win merely because it finishes after the newer build.
  DeferredFirstLoadFiltersProvider delayed_provider;
  delayed_provider.RegisterAsSourceProvider(service.get());

  ASSERT_TRUE(base::test::RunUntil(
      [&]() { return delayed_provider.HasPendingFirstLoad(); }))
      << "Timed out waiting for the initial asynchronous filter-set build";

  auto rules_provider = std::make_unique<TestFiltersProvider>(
      "||newest-subscription-rule.com^", /*engine_is_default=*/true);
  rules_provider->RegisterAsSourceProvider(service.get());

  ASSERT_TRUE(base::test::RunUntil([&]() {
    return ShouldStartRequest(service.get(), EngineType::kDefault,
                              "https://newest-subscription-rule.com/script.js")
        .matched;
  })) << "The newer filter-set build did not activate its subscription rule";

  // Complete the older build after the newer rules are already active. It
  // must be ignored rather than replacing the active engine with stale rules.
  delayed_provider.ReleaseFirstLoad();
  task_environment_.RunUntilIdle();

  EXPECT_TRUE(
      ShouldStartRequest(service.get(), EngineType::kDefault,
                         "https://newest-subscription-rule.com/script.js")
          .matched);
}

"""
    anchor = "TEST_F(AdBlockServiceTest, EmptyFilterSetDoesNotCrash) {\n"
    return replace_once(source, anchor, test + anchor,
                        "NewestFilterSetBuildWinsWhenOlderBuildFinishesLast",
                        "out-of-order subscription reload regression test")




def transform_manager_header(source: str) -> str:
    old_public = (
        "  void ForceNotifyObserver(AdBlockFiltersProvider::Observer& observer,\n"
        "                           bool is_default_engine);\n"
    )
    new_public = (
        "  void ForceNotifyObserver(AdBlockFiltersProvider::Observer& observer,\n"
        "                           bool is_default_engine);\n"
        "  // Explicitly reload an engine after Sandium's initial subscription set\n"
        "  // has been registered, bypassing the DAT-cache startup notification skip.\n"
        "  void ForceNotifyObservers(bool is_default_engine);\n"
    )
    source = replace_once(source, old_public, new_public,
                          "void ForceNotifyObservers(bool is_default_engine);",
                          "explicit startup engine reload API")

    old_state = (
        "  bool suppress_default_engine_startup_change_notification_ = false;\n"
        "  bool suppress_additional_engine_startup_change_notification_ = false;\n\n"
        "  base::CancelableTaskTracker task_tracker_;\n"
    )
    new_state = (
        "  bool suppress_default_engine_startup_change_notification_ = false;\n"
        "  bool suppress_additional_engine_startup_change_notification_ = false;\n"
        "  bool force_default_engine_reload_pending_ = false;\n"
        "  bool force_additional_engine_reload_pending_ = false;\n\n"
        "  base::CancelableTaskTracker task_tracker_;\n"
    )
    return replace_once(source, old_state, new_state,
                        "force_additional_engine_reload_pending_ = false;",
                        "deferred startup reload state")


def transform_manager_cc(source: str) -> str:
    old_changed = (
        "void AdBlockFiltersProviderManager::OnChanged(bool is_for_default_engine) {\n"
        "  if (!AreAllProvidersInitialized(is_for_default_engine)) {\n"
        "    return;\n"
        "  }\n\n"
        "  // All startup providers are initialized so we can safely consume the startup\n"
        "  // notification. The next call to OnChanged will trigger NotifyObservers\n"
        "  if (MaybeConsumeEngineStartupChangeNotification(is_for_default_engine)) {\n"
        "    return;\n"
        "  }\n\n"
        "  NotifyObservers(is_for_default_engine);\n"
        "}\n"
    )
    new_changed = (
        "void AdBlockFiltersProviderManager::OnChanged(bool is_for_default_engine) {\n"
        "  if (!AreAllProvidersInitialized(is_for_default_engine)) {\n"
        "    return;\n"
        "  }\n\n"
        "  bool& force_reload_pending =\n"
        "      is_for_default_engine ? force_default_engine_reload_pending_\n"
        "                         : force_additional_engine_reload_pending_;\n"
        "  if (force_reload_pending) {\n"
        "    force_reload_pending = false;\n"
        "    NotifyObservers(is_for_default_engine);\n"
        "    return;\n"
        "  }\n\n"
        "  // All startup providers are initialized so we can safely consume the startup\n"
        "  // notification. The next call to OnChanged will trigger NotifyObservers\n"
        "  if (MaybeConsumeEngineStartupChangeNotification(is_for_default_engine)) {\n"
        "    return;\n"
        "  }\n\n"
        "  NotifyObservers(is_for_default_engine);\n"
        "}\n"
    )
    source = replace_once(source, old_changed, new_changed,
                          "force_reload_pending =",
                          "honor deferred explicit startup reload")

    old_force = (
        "void AdBlockFiltersProviderManager::ForceNotifyObserver(\n"
        "    AdBlockFiltersProvider::Observer& observer,\n"
        "    bool is_for_default_engine) {\n"
        "  // Consume the startup change notification if it hasn't been consumed already.\n"
        "  // If it has been consumed this will return false and continue to OnChanged.\n"
        "  // If it has not been consumed then we're still waiting for a startup provider\n"
        "  // to initialize and it will notify when it does instead of suppressing it.\n"
        "  if (MaybeConsumeEngineStartupChangeNotification(is_for_default_engine)) {\n"
        "    return;\n"
        "  }\n\n"
        "  if (AreAllProvidersInitialized(is_for_default_engine)) {\n"
        "    observer.OnChanged(is_for_default_engine);\n"
        "  }\n"
        "}\n\n"
    )
    new_force = old_force + (
        "void AdBlockFiltersProviderManager::ForceNotifyObservers(\n"
        "    bool is_default_engine) {\n"
        "  // This is an explicit recovery path for a cold subscription bootstrap.\n"
        "  // Clear the cache optimization and remember the request if providers are\n"
        "  // still initializing; the final provider notification will publish the\n"
        "  // complete filter set instead of being swallowed as a startup event.\n"
        "  bool& suppress_startup_notification =\n"
        "      is_default_engine\n"
        "          ? suppress_default_engine_startup_change_notification_\n"
        "          : suppress_additional_engine_startup_change_notification_;\n"
        "  bool& force_reload_pending =\n"
        "      is_default_engine ? force_default_engine_reload_pending_\n"
        "                         : force_additional_engine_reload_pending_;\n"
        "  suppress_startup_notification = false;\n"
        "  force_reload_pending = true;\n"
        "  if (!AreAllProvidersInitialized(is_default_engine)) {\n"
        "    return;\n"
        "  }\n"
        "  force_reload_pending = false;\n"
        "  NotifyObservers(is_default_engine);\n"
        "}\n\n"
    )
    return replace_once(source, old_force, new_force,
                        "void AdBlockFiltersProviderManager::ForceNotifyObservers(",
                        "force complete subscription bootstrap")


def transform_manager_test(source: str) -> str:
    tests = """// Sandium explicitly asks for one complete additional-engine build after
// registering its first-launch subscriptions. This must bypass the normal DAT
// cache startup suppression, for both cache-enabled and cache-disabled builds.
TEST_P(AdBlockFiltersProviderManagerDATCacheTest,
       ForceNotifyObserversBypassesStartupSuppression) {
  brave_shields::AdBlockFiltersProviderManager m;
  FiltersProviderManagerTestObserver observer;
  m.AddObserver(&observer);

  brave_shields::TestFiltersProvider provider("rules", true, 0);
  provider.RegisterAsSourceProvider(&m);
  const int notifications_before_force = observer.changed_count;

  m.ForceNotifyObservers(/*is_default_engine=*/true);

  EXPECT_EQ(observer.changed_count, notifications_before_force + 1);
}

// If a provider is not ready when the explicit warm-up is requested, preserve
// the request and publish once the last provider initializes.
TEST_P(AdBlockFiltersProviderManagerDATCacheTest,
       ForceNotifyObserversWaitsForProviderInitialization) {
  brave_shields::AdBlockFiltersProviderManager m;
  FiltersProviderManagerTestObserver observer;
  m.AddObserver(&observer);

  brave_shields::TestFiltersProvider provider("rules", true, 0);
  m.AddProvider(&provider, /*is_for_default_engine=*/true);
  m.ForceNotifyObservers(/*is_default_engine=*/true);
  EXPECT_EQ(observer.changed_count, 0);

  provider.Initialize();
  EXPECT_EQ(observer.changed_count, 1);
}

"""
    anchor = "// Disabled: startup OnChanged notifies observer for each provider init.\n"
    return replace_once(source, anchor, tests + anchor,
                        "ForceNotifyObserversBypassesStartupSuppression",
                        "one-time subscription warm-up regression tests")


def verify(core: Path) -> None:
    header = read(core / "components/brave_shields/content/browser/ad_block_service.h")
    service = read(core / "components/brave_shields/content/browser/ad_block_service.cc")
    test = read(core / "components/brave_shields/content/test/ad_block_service_unittest.cc")
    manager_header = read(core / "components/brave_shields/core/browser/ad_block_filters_provider_manager.h")
    manager_cc = read(core / "components/brave_shields/core/browser/ad_block_filters_provider_manager.cc")
    manager_test = read(core / "components/brave_shields/core/test/ad_block_filters_provider_manager_unittest.cc")
    checks = {
        "generation stamped on every provider change":
            "const uint64_t generation = ++filter_set_generation_;" in service,
        "stale aggregation discarded":
            "if (generation != filter_set_generation_) {" in service,
        "generation carried into resource completion":
            "OnAllLoaded,\n                     weak_factory_.GetWeakPtr(), generation," in service,
        "DAT resource load retains current generation":
            "LoadResources(nullptr, filter_set_generation_);" in service,
        "generation field present":
            "uint64_t filter_set_generation_ = 0;" in header,
        "out-of-order regression test present":
            "NewestFilterSetBuildWinsWhenOlderBuildFinishesLast" in test,
        "test explicitly completes older build last":
            "delayed_provider.ReleaseFirstLoad();" in test,
        "explicit provider-manager warm-up API":
            "void ForceNotifyObservers(bool is_default_engine);" in manager_header,
        "startup suppression is bypassed for explicit warm-up":
            "suppress_startup_notification = false;" in manager_cc,
        "deferred warm-up waits for providers":
            "force_reload_pending" in manager_cc and "ForceNotifyObserversWaitsForProviderInitialization" in manager_test,
        "DAT-cache cold-start regression tests":
            "ForceNotifyObserversBypassesStartupSuppression" in manager_test,
    }
    if has_homepage_warmup(core):
        for name in (
            "explicit provider-manager warm-up API",
            "startup suppression is bypassed for explicit warm-up",
            "deferred warm-up waits for providers",
            "DAT-cache cold-start regression tests",
        ):
            checks.pop(name)
        body = manager_cc.split("void AdBlockFiltersProviderManager::ForceNotifyObservers(", 1)[1].split("std::string AdBlockFiltersProviderManager::GetNameForDebugging", 1)[0]
        checks["preserved explicit homepage activation"] = (
            "MaybeConsumeEngineStartupChangeNotification(is_for_default_engine)" in body
            and "NotifyObservers(is_for_default_engine);" in body
            and "AreAllProvidersInitialized" not in body
            and manager_cc.count("void AdBlockFiltersProviderManager::ForceNotifyObservers(") == 1
        )
        verify_composed_service(service)
    failures = [name for name, ok in checks.items() if not ok]
    if failures:
        raise RuntimeError("Adblock reload verification failed: " + ", ".join(failures))
    print("SANDIUM_ADBLOCK_RELOAD_VERIFY=PASS latest_build_wins=true startup_warmup=true "
          "stale_callbacks_dropped=true homepage_composition=" + str(has_homepage_warmup(core)).lower())


def has_homepage_warmup(core: Path) -> bool:
    header = read(core / "components/brave_shields/core/browser/ad_block_filters_provider_manager.h")
    return "void ForceNotifyObservers(bool is_for_default_engine);" in header


def verify_composed_service(source: str) -> None:
    begin = source.index("void RegisterPrefsForAdBlockService(PrefRegistrySimple* registry) {")
    end = source.index("\n}", begin)
    body = source[begin:end]
    for name in ("kSandiumDefaultFilterListsMigrated", "kSandiumAdBlockEngineWarmupRequested",
                 "kSandiumAdBlockEngineWarmupDone", "kSandiumAdBlockEngineWarmupRequestedV2",
                 "kSandiumAdBlockEngineWarmupDoneV2"):
        statement = f"registry->RegisterBooleanPref(prefs::{name}, false);"
        if body.count(statement) != 1:
            raise RuntimeError("Missing/duplicate final local-state registration: " + name)
    if body.count("registry->RegisterListPref(prefs::kSandiumDefaultFilterListsSeeded);") != 1:
        raise RuntimeError("Missing/duplicate final seeded-list registration")
    # Check the actual callback and its ordered guards, not a token anywhere
    # in the translation unit. Pinned formatting is deliberate: fail closed.
    begin = source.index("void AdBlockService::OnEngineLoaded(")
    end = source.index("\n}", begin)
    callback = source[begin:end]
    completion = "local_state_->SetBoolean(prefs::kSandiumAdBlockEngineWarmupDoneV2, true);"
    guarded_completion = (
        "  if (local_state_ && !is_default_engine &&\n"
        "      local_state_->GetBoolean(prefs::kSandiumAdBlockEngineWarmupRequestedV2) &&\n"
        "      load_result == FilterListLoadResult::kLoaded) {\n"
        "    " + completion + "\n  }"
    )
    if source.count(completion) != 1 or guarded_completion not in callback:
        raise RuntimeError("Missing or incorrectly guarded native warm-up completion write")
    unpack = "auto [load_result, serialized_dat] = std::move(result);"
    notify = "observers_.Notify(&Observer::OnFilterListLoaded"
    if not (callback.index(unpack) < callback.index(guarded_completion) < callback.index(notify)):
        raise RuntimeError("Incorrect native warm-up completion ordering")
    # The publication callback must reject obsolete resource builds before
    # invoking the service path that eventually reaches OnEngineLoaded.
    begin = source.index("void AdBlockService::SourceProviderObserver::OnAllLoaded(")
    end = source.index("\n}", begin)
    publication = source[begin:end]
    guard = "  if (generation != filter_set_generation_) {\n    return;\n  }"
    if guard not in publication or publication.index(guard) > publication.index("on_resources_loaded_.Run("):
        raise RuntimeError("Missing/late stale-generation guard before completion publication")



def transform_pref_test(source: str) -> str:
    marker = "SandiumWarmupPrefsRegisteredAndRoundTrip"
    if marker in source:
        return source
    test = '''TEST_F(AdBlockServiceTest, SandiumWarmupPrefsRegisteredAndRoundTrip) {
  for (const char* name : {"sandium.ad_block.engine_warmup_requested_v2",
                           "sandium.ad_block.engine_warmup_done_v2"}) {
    ASSERT_NE(prefs_.FindPreference(name), nullptr);
    EXPECT_FALSE(prefs_.GetBoolean(name));
    prefs_.SetBoolean(name, true);
    EXPECT_TRUE(prefs_.GetBoolean(name));
  }
}

'''
    anchor = "TEST_F(AdBlockServiceTest, NewestFilterSetBuildWinsWhenOlderBuildFinishesLast) {"
    if source.count(anchor) != 1:
        raise RuntimeError("pref test anchor missing/duplicated")
    return source.replace(anchor, test + anchor, 1)


def reset_shared_sources(core: Path) -> None:
    # Called only before the bootstrap/homepage sequence. Every changed shared
    # file is subsequently reconstructed, including from legacy checkpoints.
    owned_paths = [
        "components/brave_shields/core/browser/ad_block_filters_provider_manager.h",
        "components/brave_shields/core/browser/ad_block_filters_provider_manager.cc",
        "components/brave_shields/core/test/ad_block_filters_provider_manager_unittest.cc",
        "components/brave_shields/content/browser/ad_block_service.h",
        "components/brave_shields/content/browser/ad_block_service.cc",
        "components/brave_shields/content/test/ad_block_service_unittest.cc",
    ]
    subprocess.run(
        ["git", "-C", str(core), "restore", "--source=HEAD", "--worktree", "--", *owned_paths],
        check=True,
    )
    dirty_owned = subprocess.run(
        ["git", "-C", str(core), "diff", "--name-only", "HEAD", "--", *owned_paths],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if dirty_owned:
        raise SystemExit(
            "SANDIUM_ADBLOCK_RELOAD_RESET=FAIL owned_paths_not_clean=" + dirty_owned
        )
    print("SANDIUM_ADBLOCK_RELOAD_RESET=PASS owned_paths=6 source=pinned_HEAD")



def main() -> None:
    args = sys.argv[1:]
    reset_shared = len(args) == 2 and args[0] == "--reset-shared"
    if not (len(args) == 1 or reset_shared):
        raise SystemExit("usage: apply-sandium-adblock-engine-race.py [--reset-shared] <brave-core-dir>")
    core = Path(args[-1]).resolve()
    if not core.is_dir():
        raise SystemExit(f"Brave Core directory does not exist: {core}")
    tag = subprocess.run(["git", "-C", str(core), "describe", "--tags", "--exact-match"],
                         check=True, capture_output=True, text=True).stdout.strip()
    sha = subprocess.run(["git", "-C", str(core), "rev-parse", "HEAD"],
                         check=True, capture_output=True, text=True).stdout.strip()
    if tag != EXPECTED_CORE_TAG or sha != EXPECTED_CORE_SHA:
        raise SystemExit(f"SANDIUM_ADBLOCK_RELOAD_PIN=FAIL expected={EXPECTED_CORE_TAG}@{EXPECTED_CORE_SHA} "
                         f"actual={tag}@{sha}")
    print(f"SANDIUM_ADBLOCK_RELOAD_PIN=PASS {tag}@{sha}")

    if reset_shared:
        reset_shared_sources(core)
        return

    # Shared files were reset before bootstrap, never here: a late reset erases
    # native pref registrations and warm-up completion logic while Java survives.
    homepage = has_homepage_warmup(core)
    if not homepage:
        write(core / "components/brave_shields/core/browser/ad_block_filters_provider_manager.h",
              transform_manager_header, "MANAGER_HEADER")
        write(core / "components/brave_shields/core/browser/ad_block_filters_provider_manager.cc",
              transform_manager_cc, "MANAGER")
        write(core / "components/brave_shields/core/test/ad_block_filters_provider_manager_unittest.cc",
              transform_manager_test, "MANAGER_UNIT_TEST")
    write(core / "components/brave_shields/content/browser/ad_block_service.h",
          transform_header, "HEADER")
    write(core / "components/brave_shields/content/browser/ad_block_service.cc",
          transform_service_cc, "SERVICE")
    write(core / "components/brave_shields/content/test/ad_block_service_unittest.cc",
          transform_unit_test, "UNIT_TEST")
    if homepage:
        verify_composed_service(read(core / "components/brave_shields/content/browser/ad_block_service.cc"))
        write(core / "components/brave_shields/content/test/ad_block_service_unittest.cc",
              transform_pref_test, "PREF_UNIT_TEST")
    verify(core)


if __name__ == "__main__":
    main()
