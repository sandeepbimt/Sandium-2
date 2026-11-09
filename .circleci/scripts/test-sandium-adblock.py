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
apply_manager_patch = _PATCH["apply_manager_patch"]
apply_component_updater_delegate_patch = _PATCH["apply_component_updater_delegate_patch"]
SUPPORTED_PINS = _PATCH["SUPPORTED_PINS"]

MANAGER_FIXTURE = """#include "base/location.h"

void AdBlockComponentServiceManager::UpdateFilterLists(
    base::OnceCallback<void(bool)> callback) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);

  // If there are currently no components to update, then run the callback with
  // a success value in a future turn.
  if (component_filters_providers_.empty()) {
    std::move(callback).Run(true);
    return;
  }

  std::vector<std::string> component_ids = {
      kAdBlockResourceComponentId,
      kAdBlockFilterListCatalogComponentId,
  };

  for (const auto& [key, provider] : component_filters_providers_) {
    component_ids.push_back(provider->component_id());
  }

  auto on_updated = [](decltype(callback) cb, update_client::Error error) {
    std::move(cb).Run(error == update_client::Error::NONE ||
                      error == update_client::Error::UPDATE_IN_PROGRESS);
  };

  brave_component_updater::BraveOnDemandUpdater::GetInstance()->OnDemandUpdate(
      component_ids, component_updater::OnDemandUpdater::Priority::FOREGROUND,
      base::BindOnce(on_updated, std::move(callback)));
}

void AdBlockComponentServiceManager::OnFilterListCatalogLoaded(
    const std::string& catalog_json) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  SetFilterListCatalog(FilterListCatalogFromJSON(catalog_json));

  update_check_timer_.Start(
"""


MANAGER_SHA256_FIXTURE = """#include "components/crx_file/id_util.h"

void AdBlockComponentServiceManager::UpdateFilterLists(
    base::OnceCallback<void(bool)> callback) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);

  // If there are currently no components to update, then run the callback with
  // a success value in a future turn.
  if (component_filters_providers_.empty()) {
    std::move(callback).Run(true);
    return;
  }

  std::vector<std::string> component_ids = {
      crx_file::id_util::GenerateIdFromHash(
          kAdBlockResourceComponentPublicKeySHA256),
      crx_file::id_util::GenerateIdFromHash(
          kAdBlockFilterListCatalogComponentPublicKeySHA256),
  };

  for (const auto& [key, provider] : component_filters_providers_) {
    component_ids.push_back(provider->component_id());
  }

  auto on_updated = [](decltype(callback) cb, update_client::Error error) {
    std::move(cb).Run(error == update_client::Error::NONE ||
                      error == update_client::Error::UPDATE_IN_PROGRESS);
  };

  brave_component_updater::BraveOnDemandUpdater::GetInstance()->OnDemandUpdate(
      component_ids, component_updater::OnDemandUpdater::Priority::FOREGROUND,
      base::BindOnce(on_updated, std::move(callback)));
}
"""

UPDATER_HEADER_FIXTURE = """  bool is_component_update_disabled() { return is_component_update_disabled_; }
};

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
#include "base/check.h"
#include "build/build_config.h"
#include "chrome/common/chrome_switches.h"

int ChromeBrowserMainParts::PreMainMessageLoopRun() {
  brave_component_updater::BraveOnDemandUpdater::GetInstance()
      ->RegisterOnDemandUpdater(
          base::CommandLine::ForCurrentProcess()->HasSwitch(
              switches::kDisableComponentUpdate),
          &g_browser_process->component_updater()->GetOnDemandUpdater());

  return ChromeBrowserMainParts_ChromiumImpl::PreMainMessageLoopRun();
}
"""

MAIN_DELEGATE_FIXTURE = """#include "base/lazy_instance.h"
#include "chrome/common/chrome_switches.h"

void BraveMainDelegate::AppendCommandLineOptions() {
  auto* command_line = base::CommandLine::ForCurrentProcess();
  command_line->AppendSwitch(switches::kDisableDomainReliability);
}

std::optional<int> BraveMainDelegate::PostEarlyInitialization(
    ChromeMainDelegate::InvokedIn invoked_in) {
  auto result = ChromeMainDelegate::PostEarlyInitialization(invoked_in);
  if (result.has_value()) {
    return result;
  }
  auto* command_line = base::CommandLine::ForCurrentProcess();
  std::string update_url = GetUpdateURLHost();
  if (!update_url.empty()) {
    command_line->AppendSwitchASCII(
        switches::kComponentUpdater,
        base::StrCat({"url-source=", update_url}));
  }
  return result;
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


COMPONENT_DELEGATE_SHA256_FIXTURE = """#include "base/task/sequenced_task_runner.h"

void BraveComponentUpdaterDelegate::Register(
    const std::string& component_name,
    base::span<const uint8_t, crypto::kSHA256Length>
        component_public_key_sha256,
    base::OnceClosure registered_callback,
    BraveComponent::ReadyCallback ready_callback) {
  if (!BraveOnDemandUpdater::GetInstance()->is_component_update_disabled()) {
    RegisterComponent(base::to_address(component_updater_), component_name,
                      component_public_key_sha256,
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


PROVIDER_FIXTURE = """#include "base/files/file_path.h"
#include "base/files/file_util.h"
#include "base/rand_util.h"
#include "base/task/thread_pool.h"
#include "base/trace_event/trace_event.h"

void AddDATBufferToFilterSet(uint8_t permission_mask,
                             DATFileDataBuffer buffer,
                             const perfetto::Flow& flow,
                             rust::Box<adblock::FilterSet>* filter_set) {
  TRACE_EVENT("brave.adblock",
              "AddDATBufferToFilterSet_AdBlockComponentFiltersProvider", flow);
  (*filter_set)->add_filter_list_with_permissions(buffer, permission_mask);
}

void OnReadDATFileData(
    base::OnceCallback<
        void(base::OnceCallback<void(rust::Box<adblock::FilterSet>*)>)> cb,
    uint8_t permission_mask,
    const perfetto::Flow& flow,
    DATFileDataBuffer buffer) {
  TRACE_EVENT("brave.adblock",
              "OnReadDATFileData_AdBlockComponentFiltersProvider", flow);
  std::move(cb).Run(
      base::BindOnce(&AddDATBufferToFilterSet, permission_mask, buffer, flow));
}

void AdBlockComponentFiltersProvider::OnComponentReady(
    const base::FilePath& path) {
  base::FilePath old_path = component_path_;
  component_path_ = path;

  NotifyObservers(engine_is_default_);
}

void AdBlockComponentFiltersProvider::LoadFilterSet(
    base::OnceCallback<
        void(base::OnceCallback<void(rust::Box<adblock::FilterSet>*)>)> cb) {
  base::FilePath list_file_path = GetFilterSetPath();

  const auto flow = perfetto::Flow::ProcessScoped(base::RandUint64());
  TRACE_EVENT("brave.adblock", "AdBlockComponentFiltersProvider::LoadFilterSet",
              flow);

  if (list_file_path.empty()) {
    std::move(cb).Run(base::BindOnce(AddNothingToFilterSet));
    return;
  }

  base::ThreadPool::PostTaskAndReplyWithResult(
      FROM_HERE, {base::MayBlock()},
      base::BindOnce(&brave_component_updater::ReadDATFileData, list_file_path),
      base::BindOnce(&OnReadDATFileData, std::move(cb), permission_mask_,
                     flow));
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
        provider = core / (
            "components/brave_shields/core/browser/"
            "ad_block_component_filters_provider.cc"
        )
        updater_header = core / (
            "components/brave_component_updater/browser/"
            "brave_on_demand_updater.h"
        )
        for path in (
            manager, fragment, adapter, main_parts, main_delegate,
            component_delegate, installer, catalog_provider, filter_service,
            provider, updater_header
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
        provider.write_text(PROVIDER_FIXTURE, encoding="utf-8")
        filter_service.write_text(FILTER_SERVICE_FIXTURE, encoding="utf-8")
        updater_header.write_text(UPDATER_HEADER_FIXTURE, encoding="utf-8")

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
        updater_header_text = updater_header.read_text(encoding="utf-8")
        provider_text = provider.read_text(encoding="utf-8")
        assert "allow-brave-component-update" in main_delegate_text
        assert "SANDIUM_COMPONENT_UPDATER_EARLY_ENABLE" in main_delegate_text
        assert "SANDIUM_BRAVE_COMPONENT_UPDATE_OVERRIDE" in main_delegate_text
        assert "SANDIUM_COMPONENT_UPDATER_ENDPOINT=development" in main_delegate_text
        assert "AppendSwitch(brave_component_updater::kUseGoUpdateDev)" in main_delegate_text
        assert "SANDIUM_COMPONENT_UPDATER_EFFECTIVE_URL" in main_delegate_text
        assert '" dev_switch="' in main_delegate_text
        assert '" dev_feature="' in main_delegate_text
        # Sandium's non-official Android QA build must use Brave's dev updater.
        assert """command_line->HasSwitch(
                      brave_component_updater::kUseGoUpdateDev)""" in main_delegate_text
        assert "AppendSwitch(brave_component_updater::kUseGoUpdateDev)" in main_delegate_text
        assert "#if BUILDFLAG(IS_ANDROID)" in main_delegate_text
        assert "BUILDFLAG(OFFICIAL_BUILD)" not in main_delegate_text
        assert '#include "build/branding_buildflags.h"' not in main_delegate_text
        assert "SANDIUM_COMPONENT_UPDATER_DEV_ENDPOINT" not in main_delegate_text
        assert "RemoveSwitch(switches::kDisableComponentUpdate)" not in main_delegate_text
        assert "SANDIUM_COMPONENT_REGISTRATION" in component_delegate_text
        assert "SANDIUM_ADBLOCK_COMPONENT_REGISTERED" in installer_text
        assert "SANDIUM_FILTER_CATALOG_COMPONENT_READY" in catalog_provider_text
        assert "SANDIUM_FILTER_COMPONENT_READY" in provider_text
        assert "SANDIUM_FILTER_DAT_FILE" in provider_text
        assert "const auto list_file_size = base::GetFileSize(list_file_path);" in provider_text
        assert "list_file_size.has_value()" in provider_text
        assert "list_file_size.value_or(0)" in provider_text
        assert "base::GetFileSize(list_file_path, &list_file_size)" not in provider_text
        assert "SANDIUM_FILTER_ENGINE_ATTACH=PASS" in provider_text
        assert "SANDIUM_FILTER_ENGINE_BINDING=PASS" in provider_text
        assert "base::BindOnce(\n      &AddDATBufferToFilterSet, std::move(component_id)," in provider_text
        assert "SANDIUM_FILTER_CATALOG_PARSED" in manager_text
        assert "SANDIUM_EMPTY_FILTER_CATALOGUE_UPDATE=REQUEST" in manager_text
        assert "kAdBlockFilterListCatalogComponentId" in manager_text
        assert "kAdBlockResourceComponentId" in manager_text
        assert "std::move(callback).Run(true);" not in manager_text
        assert "is_on_demand_updater_registered()" in updater_header_text
        assert "SANDIUM_ON_DEMAND_UPDATER_READINESS" in updater_header_text
        assert "SANDIUM_FILTER_LIST_UI_COUNT" in filter_service_text
        assert "SANDIUM_BRAVE_COMPONENT_UPDATES" in main_parts_text
        assert "SANDIUM_COMPONENT_UPDATER_SERVICE_CREATED" in main_parts_text
        assert "global_disable_preserved=" in main_parts_text
        assert "RemoveSwitch(switches::kDisableComponentUpdate)" not in main_parts_text
        assert "switches::kDisableComponentUpdate" in main_parts_text
        assert main_parts_text.count("->RegisterOnDemandUpdater(") == 1
        assert "&g_browser_process->component_updater()->GetOnDemandUpdater()" not in main_parts_text
        assert "&updater_service->GetOnDemandUpdater()" in main_parts_text
        assert "if (component_filters_providers_.empty())" in manager_text
        assert "requestFilterListCatalogueRefresh" in fragment_text
        assert "MAX_FILTER_LIST_UPDATE_ATTEMPTS = 3" in fragment_text
        assert "MAX_SELECTED_FILTER_VERIFY_ATTEMPTS = 6" in fragment_text
        assert "SANDIUM_SELECTED_FILTERS_VERIFIED" in fragment_text
        assert "getBoolValue()" in fragment_text
        assert "preferences.edit().putBoolean(FILTER_LIST_MIGRATION_KEY, true).apply();" in fragment_text
        assert "notifyDataSetChanged();" in adapter_text
        for uuid in FRESH_INSTALL_FILTER_UUIDS:
            assert uuid in fragment_text, f"missing selected catalogue UUID: {uuid}"

    # Validate both component-updater delegate APIs used by Brave v1.98.x
    # (Base64 key) and v1.99.x (SHA-256 key fingerprint).
    with tempfile.TemporaryDirectory(prefix="sandium-component-delegate-test-") as delegate_tmp:
        delegate_root = Path(delegate_tmp)
        legacy_delegate = delegate_root / "legacy" / "brave_component_updater_delegate.cc"
        sha_delegate = delegate_root / "sha256" / "brave_component_updater_delegate.cc"
        legacy_delegate.parent.mkdir(parents=True, exist_ok=True)
        sha_delegate.parent.mkdir(parents=True, exist_ok=True)
        legacy_delegate.write_text(COMPONENT_DELEGATE_FIXTURE, encoding="utf-8")
        sha_delegate.write_text(COMPONENT_DELEGATE_SHA256_FIXTURE, encoding="utf-8")
        apply_component_updater_delegate_patch(legacy_delegate)
        apply_component_updater_delegate_patch(sha_delegate)
        apply_component_updater_delegate_patch(legacy_delegate)
        apply_component_updater_delegate_patch(sha_delegate)
        legacy_text = legacy_delegate.read_text(encoding="utf-8")
        sha_text = sha_delegate.read_text(encoding="utf-8")
        assert "SANDIUM_COMPONENT_REGISTRATION" in legacy_text
        assert "key_mode=base64" in legacy_text
        assert "component_base64_public_key" in legacy_text
        assert "SANDIUM_COMPONENT_REGISTRATION" in sha_text
        assert "key_mode=sha256" in sha_text
        assert "component_public_key_sha256" in sha_text
        print("SANDIUM_ADBLOCK_COMPONENT_DELEGATE_COMPAT=PASS")

    # Exercise the Brave v1.99.x SHA-256 component-ID variant independently
    # from the pinned v1.98.x fixture used by the successful FAST Mode build.
    with tempfile.TemporaryDirectory(prefix="sandium-adblock-sha256-test-") as latest_tmp:
        sha_core = Path(latest_tmp)
        sha_manager = sha_core / (
            "components/brave_shields/core/browser/"
            "ad_block_component_service_manager.cc"
        )
        sha_manager.parent.mkdir(parents=True, exist_ok=True)
        sha_manager.write_text(MANAGER_SHA256_FIXTURE, encoding="utf-8")
        apply_manager_patch(sha_core)
        apply_manager_patch(sha_core)  # latest-source transform must be idempotent
        sha_text = sha_manager.read_text(encoding="utf-8")
        assert "SANDIUM_EMPTY_FILTER_CATALOGUE_UPDATE=REQUEST" in sha_text
        assert "kAdBlockResourceComponentPublicKeySHA256" in sha_text
        assert "kAdBlockFilterListCatalogComponentPublicKeySHA256" in sha_text
        assert "crx_file::id_util::GenerateIdFromHash(" in sha_text
        assert "std::move(callback).Run(true);" not in sha_text
        assert "v1.99.55" in SUPPORTED_PINS
        print("SANDIUM_ADBLOCK_LATEST_SHA256_FIXTURE=PASS")

    print("SANDIUM_ADBLOCK_UNIT_TEST=PASS transformation=idempotent catalogue=curated")


if __name__ == "__main__":
    main()
