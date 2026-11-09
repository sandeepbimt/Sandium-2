#!/usr/bin/env python3
"""Offline patcher tests for latest-build-wins adblock engine reload protection."""
from __future__ import annotations

import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATCHER = HERE / "apply-sandium-adblock-engine-race.py"
MODULE = runpy.run_path(str(PATCHER))


def apply_twice(transform, source: str, label: str) -> str:
    first = transform(source)
    second = transform(first)
    assert second == first, f"{label}: transform is not idempotent"
    return first


header_fixture = """    void LoadResources(
        std::unique_ptr<rust::Box<adblock::FilterSet>> filter_set);
    void OnFilterSetLoaded(
        base::OnceCallback<void(rust::Box<adblock::FilterSet>*)> cb);
    void OnFilterSetCreated(
        std::unique_ptr<rust::Box<adblock::FilterSet>> filter_set);

    void OnAllLoaded(std::unique_ptr<rust::Box<adblock::FilterSet>> filter_set,
                     AdblockResourceStorageBox storage);

    OnResourcesLoadedCallback on_resources_loaded_;
    const bool engine_is_default_;
    const bool debug_mode_;

    scoped_refptr<base::SequencedTaskRunner> task_runner_;
"""
header = apply_twice(MODULE["transform_header"], header_fixture, "header")
assert "uint64_t filter_set_generation_ = 0;" in header
assert "OnFilterSetLoaded(\n        uint64_t generation," in header
assert "OnAllLoaded(uint64_t generation," in header


service_fixture = """void AdBlockService::SourceProviderObserver::OnChanged(bool is_default_engine) {
  if (engine_is_default_ != is_default_engine) {
    return;
  }

  auto on_loaded_cb =
      base::BindOnce(&AdBlockService::SourceProviderObserver::OnFilterSetLoaded,
                     weak_factory_.GetWeakPtr());
  filters_provider_manager_->LoadFilterSetForEngine(is_default_engine,
                                                    std::move(on_loaded_cb));
}

void AdBlockService::SourceProviderObserver::OnFilterSetLoaded(
    base::OnceCallback<void(rust::Box<adblock::FilterSet>*)> cb) {
  task_runner_->PostTaskAndReplyWithResult(
      FROM_HERE,
      base::BindOnce(
          [](bool debug_mode,
             base::OnceCallback<void(rust::Box<adblock::FilterSet>*)> cb) {
            auto filter_set = std::make_unique<rust::Box<adblock::FilterSet>>(
                adblock::new_filter_set(debug_mode));
            std::move(cb).Run(filter_set.get());
            return filter_set;
          },
          debug_mode_, std::move(cb)),
      base::BindOnce(
          &AdBlockService::SourceProviderObserver::OnFilterSetCreated,
          weak_factory_.GetWeakPtr()));
}

void AdBlockService::SourceProviderObserver::LoadResources(
    std::unique_ptr<rust::Box<adblock::FilterSet>> filter_set) {
  // multiple AddObserver calls are ignored
  resource_provider_->AddObserver(this);
  resource_provider_->LoadResources(
      base::BindOnce(&SourceProviderObserver::OnAllLoaded,
                     weak_factory_.GetWeakPtr(), std::move(filter_set)));
}

void AdBlockService::SourceProviderObserver::OnDATFileRead(
    DATFileDataBuffer dat) {
  on_resources_loaded_.Run(engine_is_default_, std::move(dat), nullptr,
                           adblock::new_empty_resource_storage());
  LoadResources(nullptr);
}

void AdBlockService::SourceProviderObserver::OnFilterSetCreated(
    std::unique_ptr<rust::Box<adblock::FilterSet>> filter_set) {
  TRACE_EVENT("brave.adblock", "OnFilterSetCreated");
  LoadResources(std::move(filter_set));
}

void AdBlockService::SourceProviderObserver::OnAllLoaded(
    std::unique_ptr<rust::Box<adblock::FilterSet>> filter_set,
    AdblockResourceStorageBox storage) {
  on_resources_loaded_.Run(engine_is_default_, std::nullopt,
                           std::move(filter_set), std::move(storage));
}

void AdBlockService::OnDATLoaded(bool is_default_engine, bool success) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  if (is_default_engine) {
    default_dat_loaded_for_testing_ = true;
  } else {
    additional_dat_loaded_for_testing_ = true;
  }
  // Fixture models the real cold-profile DAT-miss callback.
  if (!success) {
    if (is_default_engine) {
      filters_provider_manager_->ForceNotifyObserver(*default_service_observer_,
                                                     true);
    } else {
      filters_provider_manager_->ForceNotifyObserver(
          *additional_filters_service_observer_, false);
    }
  }
  observers_.Notify(&Observer::OnDATLoaded, is_default_engine, success);
}

void AdBlockService::OnEngineLoaded(
    bool is_default_engine,
    std::pair<FilterListLoadResult, std::optional<DATFileDataBuffer>> result) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  auto [load_result, serialized_dat] = std::move(result);

  if (load_result != FilterListLoadResult::kResourcesOnly) {
"""
service = apply_twice(MODULE["transform_service_cc"], service_fixture, "service")
assert "const uint64_t generation = ++filter_set_generation_;" in service
assert service.count("if (generation != filter_set_generation_)") == 3
assert "LoadResources(nullptr, filter_set_generation_);" in service


test_fixture = """#include "base/files/file_path.h"
#include <string_view>

class AdBlockServiceTestBase : public testing::Test {
};

TEST_F(AdBlockServiceTest, EmptyFilterSetDoesNotCrash) {
}
"""
unit_test = apply_twice(MODULE["transform_unit_test"], test_fixture, "unit test")
assert '#include "base/check.h"' in unit_test
assert "class DeferredFirstLoadFiltersProvider" in unit_test
assert "NewestFilterSetBuildWinsWhenOlderBuildFinishesLast" in unit_test
assert "delayed_provider.ReleaseFirstLoad();" in unit_test


manager_header_fixture = """  void ForceNotifyObserver(AdBlockFiltersProvider::Observer& observer,
                           bool is_default_engine);

  bool suppress_default_engine_startup_change_notification_ = false;
  bool suppress_additional_engine_startup_change_notification_ = false;

  base::CancelableTaskTracker task_tracker_;
"""
manager_header = apply_twice(
    MODULE["transform_manager_header"], manager_header_fixture, "manager header")
assert "void ForceNotifyObservers(bool is_default_engine);" in manager_header
assert "force_additional_engine_reload_pending_ = false;" in manager_header


manager_cc_fixture = """#include "base/functional/bind.h"

void AdBlockFiltersProviderManager::OnChanged(bool is_for_default_engine) {
  if (!AreAllProvidersInitialized(is_for_default_engine)) {
    return;
  }

  // All startup providers are initialized so we can safely consume the startup
  // notification. The next call to OnChanged will trigger NotifyObservers
  if (MaybeConsumeEngineStartupChangeNotification(is_for_default_engine)) {
    return;
  }

  NotifyObservers(is_for_default_engine);
}

void AdBlockFiltersProviderManager::ForceNotifyObserver(
    AdBlockFiltersProvider::Observer& observer,
    bool is_for_default_engine) {
  // Consume the startup change notification if it hasn't been consumed already.
  // If it has been consumed this will return false and continue to OnChanged.
  // If it has not been consumed then we're still waiting for a startup provider
  // to initialize and it will notify when it does instead of suppressing it.
  if (MaybeConsumeEngineStartupChangeNotification(is_for_default_engine)) {
    return;
  }

  if (AreAllProvidersInitialized(is_for_default_engine)) {
    observer.OnChanged(is_for_default_engine);
  }
}

std::string AdBlockFiltersProviderManager::GetNameForDebugging() {
  return "AdBlockFiltersProviderManager";
}
"""
manager_cc = apply_twice(
    MODULE["transform_manager_cc"], manager_cc_fixture, "manager cc")
assert "force_reload_pending = false;" in manager_cc
assert "ForceNotifyObservers(" in manager_cc
assert "NotifyObservers(is_default_engine);" in manager_cc


manager_test_fixture = """// Disabled: startup OnChanged notifies observer for each provider init.
"""
manager_test = apply_twice(
    MODULE["transform_manager_test"], manager_test_fixture, "manager test")
assert "ForceNotifyObserversBypassesStartupSuppression" in manager_test
assert "ForceNotifyObserversWaitsForProviderInitialization" in manager_test
assert "ForceNotifyObserversBypassesAdditionalEngineStartupSuppression" in manager_test
assert "ForceNotifyObserversWaitsForAdditionalEngineProviderInitialization" in manager_test



service_startup_fixture = """void AdBlockService::OnDATLoaded(bool is_default_engine, bool success) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  if (is_default_engine) {
    default_dat_loaded_for_testing_ = true;
  } else {
    additional_dat_loaded_for_testing_ = true;
  }
  // Cached DAT unavailable: recover by loading the filter-list providers.
  if (!success) {
    if (is_default_engine) {
      filters_provider_manager_->ForceNotifyObserver(*default_service_observer_,
                                                     true);
    } else {
      filters_provider_manager_->ForceNotifyObserver(
          *additional_filters_service_observer_, false);
    }
  }
  observers_.Notify(&Observer::OnDATLoaded, is_default_engine, success);
}

void AdBlockService::OnEngineLoaded(
    bool is_default_engine,
    std::pair<FilterListLoadResult, std::optional<DATFileDataBuffer>> result) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  auto [load_result, serialized_dat] = std::move(result);

  if (load_result != FilterListLoadResult::kResourcesOnly) {
"""
service_startup = apply_twice(
    MODULE["transform_startup_refresh"], service_startup_fixture, "service startup")
assert "filters_provider_manager_->ForceNotifyObservers(is_default_engine);" in service_startup
assert "ForceNotifyObserver(*default_service_observer_" not in service_startup
assert "ForceNotifyObserver(" not in service_startup
assert "SANDIUM_ADBLOCK_STARTUP_DAT_CACHE=MISS" in service_startup
assert "ForceNotifyObservers(is_default_engine);" in service_startup
assert "Cached DAT unavailable" not in service_startup
assert "SANDIUM_ADBLOCK_ENGINE_BUILD_RESULT" in service_startup


print("SANDIUM_ADBLOCK_RELOAD_PATCHER_TEST=PASS header=true callbacks=true idempotent=true "
      "out_of_order_regression=true startup_refresh=true startup_fallback=true "
      "engine_build_diagnostics=true deferred_warmup=true")
