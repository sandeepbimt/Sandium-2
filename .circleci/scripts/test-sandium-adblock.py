#!/usr/bin/env python3
"""Offline transformation tests for Sandium's Brave/uBO filter integration."""
from __future__ import annotations

import tempfile
from pathlib import Path
import runpy

# The production patch filename intentionally uses hyphens, so it cannot be
# imported with a normal "from module import ..." statement.
_PATCH = runpy.run_path(
    str(Path(__file__).with_name("apply-sandium-adblock.py"))
)
FRESH_INSTALL_FILTER_UUIDS = _PATCH["FRESH_INSTALL_FILTER_UUIDS"]
apply_patches = _PATCH["apply_patches"]
verify_patches = _PATCH["verify_patches"]

MANAGER_FIXTURE = """#include "base/location.h"

  // If there are currently no components to update, then run the callback with
  // a success value in a future turn.
  if (component_filters_providers_.empty()) {
    std::move(callback).Run(true);
    return;
  }

  std::vector<std::string> component_ids = {

void AdBlockComponentServiceManager::OnFilterListCatalogLoaded(
    const std::string& catalog_json) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  SetFilterListCatalog(FilterListCatalogFromJSON(catalog_json));

  update_check_timer_.Start(
"""

FRAGMENT_FIXTURE = """import android.content.Context;
import android.content.Intent;
import android.os.Bundle;

import java.util.ArrayList;
import java.util.Arrays;

public class ContentFilteringFragment extends BravePreferenceFragment
        implements FragmentSettingsNavigation,
                BraveContentFilteringListener,
                BottomInsetViewProvider {
    private RecyclerView mRecyclerView;

    private void getFilterLists() {
        if (mFilterListAndroidHandler != null) {
            mFilterListAndroidHandler.getFilterLists(filterLists -> {
                mFilterLists = filterLists.storage;
                mAdapter.setFilterLists(mFilterLists);
            });
        }
    }

        } else if (item.getItemId() == R.id.update_filter_list_id) {
            if (mFilterListAndroidHandler != null) {
                mFilterListAndroidHandler.updateFilterLists(
                        isSuccess -> {
                            if (isSuccess) {
                                setData();
                            }
                            String message =
                                    isSuccess
                                            ? getString(R.string.update_filter_list_success_text)
                                            : getString(R.string.update_filter_list_fail_text);
                            Toast.makeText(getActivity(), message, Toast.LENGTH_SHORT).show();
                        });
            }
            return true;
        }

    @Override
    public void onDestroy() {
        if (mFilterListAndroidHandler != null) {
"""

ADAPTER_FIXTURE = """    public void setFilterLists(Value filterLists[]) {
        mFilterLists = filterLists;
        // mSubscriptionFilterLists could be null if setSubscriptionFilterLists
        // hasn't been called yet. notifyItemRangeInserted is called inside
        // setSubscriptionFilterLists, so we are good to skip it in that place
        if (mSubscriptionFilterLists != null) {
            notifyItemRangeInserted(
                    mSubscriptionFilterLists.size() + THREE_ITEMS_SPACE,
                    mFilterLists.length + ONE_ITEM_SPACE);
        }
    }
"""

MAIN_PARTS_FIXTURE = """#include "base/command_line.h"
#include "build/build_config.h"

int ChromeBrowserMainParts::PreMainMessageLoopRun() {
  brave_component_updater::BraveOnDemandUpdater::GetInstance()
      ->RegisterOnDemandUpdater(
          base::CommandLine::ForCurrentProcess()->HasSwitch(
              switches::kDisableComponentUpdate),
          &g_browser_process->component_updater()->GetOnDemandUpdater());

  return ChromeBrowserMainParts_ChromiumImpl::PreMainMessageLoopRun();
}
"""

MAIN_DELEGATE_FIXTURE = """void BraveMainDelegate::AppendCommandLineOptions() {
  auto* command_line = base::CommandLine::ForCurrentProcess();
  command_line->AppendSwitch(switches::kDisableDomainReliability);
}
"""

COMPONENT_DELEGATE_FIXTURE = """#include "base/task/sequenced_task_runner.h"

void BraveComponentUpdaterDelegate::Register(
    const std::string& component_name,
    const std::string& component_base64_public_key,
    base::OnceClosure registered_callback,
    BraveComponent::ReadyCallback ready_callback) {
  if (!BraveOnDemandUpdater::GetInstance()->is_component_update_disabled()) {
    RegisterComponent(base::to_address(component_updater_), component_name,
                      component_base64_public_key,
                      std::move(registered_callback),
                      std::move(ready_callback));
  }
}
"""

INSTALLER_FIXTURE = """#include "base/functional/callback.h"

void OnRegistered(const std::string& component_id) {
  // Unlike other components, which are only installed but not updated in
  // `OnRegistered`, we do always want to update the ad block component upon
  // registration.
  BraveOnDemandUpdater::GetInstance()->OnDemandUpdate(
      component_id, component_updater::OnDemandUpdater::Priority::FOREGROUND);
}
"""

CATALOG_PROVIDER_FIXTURE = """#include "base/files/file_path.h"

void AdBlockFilterListCatalogProvider::OnComponentReady(
    const base::FilePath& path) {
  TRACE_EVENT("brave.adblock",
              "AdBlockFilterListCatalogProvider::OnComponentReady",
              perfetto::Flow::FromPointer(this), "path", path.value());
  component_path_ = path;

  // Load the filter list catalog (as a string)
}
"""

FILTER_SERVICE_FIXTURE = """#include "base/feature_list.h"

void FilterListService::GetFilterLists(GetFilterListsCallback callback) {
  std::move(callback).Run(
      ad_block_service_->component_service_manager()->GetRegionalLists());
}
"""



def main() -> None:
    assert len(FRESH_INSTALL_FILTER_UUIDS) == 6
    assert len(FRESH_INSTALL_FILTER_UUIDS) == len(set(FRESH_INSTALL_FILTER_UUIDS))

    with tempfile.TemporaryDirectory(prefix="sandium-adblock-test-") as tmp:
        core = Path(tmp)
        manager = core / (
            "components/brave_shields/core/browser/"
            "ad_block_component_service_manager.cc"
        )
        fragment = core / (
            "android/java/org/chromium/chrome/browser/shields/"
            "ContentFilteringFragment.java"
        )
        adapter = core / (
            "android/java/org/chromium/chrome/browser/shields/"
            "ContentFilteringAdapter.java"
        )
        main_parts = core / "browser/brave_browser_main_parts.cc"
        main_delegate = core / "app/brave_main_delegate.cc"
        component_delegate = core / (
            "components/brave_component_updater/browser/"
            "brave_component_updater_delegate.cc"
        )
        installer = core / (
            "components/brave_shields/core/browser/"
            "ad_block_component_installer.cc"
        )
        catalog_provider = core / (
            "components/brave_shields/core/browser/"
            "ad_block_filter_list_catalog_provider.cc"
        )
        filter_service = core / (
            "components/brave_shields/content/browser/"
            "filter_list_service.cc"
        )
        for path in (
            manager, fragment, adapter, main_parts, main_delegate,
            component_delegate, installer, catalog_provider, filter_service
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
        manager.write_text(MANAGER_FIXTURE, encoding="utf-8")
        fragment.write_text(FRAGMENT_FIXTURE, encoding="utf-8")
        adapter.write_text(ADAPTER_FIXTURE, encoding="utf-8")
        main_parts.write_text(MAIN_PARTS_FIXTURE, encoding="utf-8")
        main_delegate.write_text(MAIN_DELEGATE_FIXTURE, encoding="utf-8")
        component_delegate.write_text(COMPONENT_DELEGATE_FIXTURE, encoding="utf-8")
        installer.write_text(INSTALLER_FIXTURE, encoding="utf-8")
        catalog_provider.write_text(CATALOG_PROVIDER_FIXTURE, encoding="utf-8")
        filter_service.write_text(FILTER_SERVICE_FIXTURE, encoding="utf-8")

        apply_patches(core)
        verify_patches(core)

        # All transforms must be idempotent on a second application.
        apply_patches(core)
        verify_patches(core)

        fragment_text = fragment.read_text(encoding="utf-8")
        adapter_text = adapter.read_text(encoding="utf-8")
        main_parts_text = main_parts.read_text(encoding="utf-8")
        manager_text = manager.read_text(encoding="utf-8")
        main_delegate_text = main_delegate.read_text(encoding="utf-8")
        component_delegate_text = component_delegate.read_text(encoding="utf-8")
        installer_text = installer.read_text(encoding="utf-8")
        catalog_provider_text = catalog_provider.read_text(encoding="utf-8")
        filter_service_text = filter_service.read_text(encoding="utf-8")
        assert "allow-brave-component-update" in main_parts_text
        assert "SANDIUM_COMPONENT_UPDATER_EARLY_ENABLE" in main_delegate_text
        assert "SANDIUM_COMPONENT_REGISTRATION" in component_delegate_text
        assert "SANDIUM_ADBLOCK_COMPONENT_REGISTERED" in installer_text
        assert "SANDIUM_FILTER_CATALOG_COMPONENT_READY" in catalog_provider_text
        assert "SANDIUM_FILTER_CATALOG_PARSED" in manager_text
        assert "SANDIUM_FILTER_LIST_UI_COUNT" in filter_service_text
        assert "SANDIUM_BRAVE_COMPONENT_UPDATES" in main_parts_text
        assert "if (component_filters_providers_.empty())" in manager_text
        assert "SANDIUM_FILTER_CATALOGUE_BOOTSTRAP" not in manager_text
        assert "requestFilterListCatalogueRefresh" in fragment_text
        assert "MAX_FILTER_LIST_UPDATE_ATTEMPTS = 3" in fragment_text
        assert "notifyDataSetChanged();" in adapter_text
        for uuid in FRESH_INSTALL_FILTER_UUIDS:
            assert uuid in fragment_text, f"missing selected catalogue UUID: {uuid}"

    print("SANDIUM_ADBLOCK_UNIT_TEST=PASS transformation=idempotent catalogue=curated")


if __name__ == "__main__":
    main()
