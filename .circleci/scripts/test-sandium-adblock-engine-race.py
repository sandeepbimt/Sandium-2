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

print("SANDIUM_ADBLOCK_RELOAD_PATCHER_TEST=PASS header=true callbacks=true idempotent=true "
      "out_of_order_regression=true")
