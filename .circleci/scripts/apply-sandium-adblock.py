#!/usr/bin/env python3
"""Apply Sandium's Brave-native + uBlock-compatible filter-list integration."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

PIN = "v1.98.62"

# Brave's hidden default components already ship the uBlock Origin core
# lists (General, Badware risks, Resource abuse, Unbreak, Quick Fixes and
# link shorteners), uBlock Origin Privacy, EasyList/EasyPrivacy, URLhaus,
# and Brave's Android-specific rules. The default-enabled Cookie Notice
# component also includes uBlock filters – Cookie Notices.
#
# The UUIDs below are additional visible Brave catalogue lists selected by
# Sandium. They complement the built-in uBO lists through Brave Shields.
FRESH_INSTALL_FILTER_UUIDS = (
    "4C07DB6B-6377-4347-836D-68702CF1494A",  # IndianList.
    "E2FA7D98-0BD5-493E-8AF4-950604ADE9CB",  # Tracking URL protection.
    "7911A1CB-304E-4CDB-ABB3-E2A94A37E4DD",  # Fanboy Social.
    "6b91e355-1421-4c03-9a30-911b4d0fb277",  # Anti-AI suggestions.
    "690FF3B4-8B6B-4709-8505-FEC6643D7BD9",  # Anti-newsletter popups.
    "67E792D4-AE03-4D1A-9EDE-80E01C81F9B8",  # Fanboy + uBO annoyances.
)
POST_V1_ADDITIONAL_FILTER_UUIDS = (
    "690FF3B4-8B6B-4709-8505-FEC6643D7BD9",  # New since the previous migration.
    "67E792D4-AE03-4D1A-9EDE-80E01C81F9B8",
)


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> None:
    if not path.is_file():
        raise SystemExit(f"SANDIUM_ADBLOCK_GATE=FAIL missing {path}")
    source = path.read_text(encoding="utf-8")
    if marker in source:
        if new not in source:
            raise SystemExit(
                f"SANDIUM_ADBLOCK_GATE=FAIL {label}: incomplete existing patch"
            )
        print(f"SANDIUM_ADBLOCK_PATCH={label}:ALREADY_APPLIED")
        return
    count = source.count(old)
    if count != 1:
        raise SystemExit(
            f"SANDIUM_ADBLOCK_GATE=FAIL {label}: expected one anchor, found {count}"
        )
    updated = source.replace(old, new, 1)
    if marker not in updated or new not in updated:
        raise SystemExit(
            f"SANDIUM_ADBLOCK_GATE=FAIL {label}: post-write verification failed"
        )
    path.write_text(updated, encoding="utf-8")
    print(f"SANDIUM_ADBLOCK_PATCH={label}:APPLIED")


def apply_on_demand_updater_header_patch(core: Path) -> None:
    header = core / (
        "components/brave_component_updater/browser/"
        "brave_on_demand_updater.h"
    )
    replace_once(
        header,
        "  bool is_component_update_disabled() { return is_component_update_disabled_; }\n",
        "  bool is_component_update_disabled() { return is_component_update_disabled_; }\n\n"
        "  // SANDIUM_ON_DEMAND_UPDATER_READINESS: avoid invoking the updater before\n"
        "  // Brave has connected the browser-process OnDemandUpdater instance.\n"
        "  bool is_on_demand_updater_registered() const {\n"
        "    return on_demand_updater_ != nullptr;\n"
        "  }\n",
        "is_on_demand_updater_registered()",
        "on-demand-updater-readiness-accessor",
    )


def apply_manager_patch(core: Path) -> None:
    """Make an empty catalogue actively refresh Brave's two bootstrap components."""
    manager = core / (
        "components/brave_shields/core/browser/"
        "ad_block_component_service_manager.cc"
    )
    # Match the pinned upstream source exactly. Keep Sandium diagnostics in
    # the replacement, never in the source-side anchor: otherwise a clean
    # Brave checkout cannot match this patch.
    old = """void AdBlockComponentServiceManager::UpdateFilterLists(
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
"""
    new = """void AdBlockComponentServiceManager::UpdateFilterLists(
    base::OnceCallback<void(bool)> callback) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);

  auto on_updated = [](base::OnceCallback<void(bool)> cb,
                       update_client::Error error) {
    LOG(WARNING) << "SANDIUM_FILTER_CATALOG_UPDATE_RESULT error="
                 << static_cast<int>(error);
    std::move(cb).Run(error == update_client::Error::NONE ||
                      error == update_client::Error::UPDATE_IN_PROGRESS);
  };

  auto* on_demand_updater =
      brave_component_updater::BraveOnDemandUpdater::GetInstance();
  if (component_filters_providers_.empty()) {
    // SANDIUM_EMPTY_FILTER_CATALOGUE_UPDATE: the old upstream branch returned
    // success here without requesting anything. Refresh the two components
    // which make the catalogue and default filter resources available.
    if (!on_demand_updater->is_on_demand_updater_registered() ||
        on_demand_updater->is_component_update_disabled()) {
      LOG(WARNING)
          << "SANDIUM_EMPTY_FILTER_CATALOGUE_UPDATE=SKIPPED updater_ready="
          << on_demand_updater->is_on_demand_updater_registered()
          << " updates_disabled="
          << on_demand_updater->is_component_update_disabled();
      std::move(callback).Run(false);
      return;
    }
    std::vector<std::string> bootstrap_component_ids = {
        kAdBlockResourceComponentId,
        kAdBlockFilterListCatalogComponentId,
    };
    LOG(WARNING) << "SANDIUM_EMPTY_FILTER_CATALOGUE_UPDATE=REQUEST";
    on_demand_updater->OnDemandUpdate(
        bootstrap_component_ids,
        component_updater::OnDemandUpdater::Priority::FOREGROUND,
        base::BindOnce(on_updated, std::move(callback)));
    return;
  }

  std::vector<std::string> component_ids = {
      kAdBlockResourceComponentId,
      kAdBlockFilterListCatalogComponentId,
  };

  for (const auto& [key, provider] : component_filters_providers_) {
    component_ids.push_back(provider->component_id());
  }

  on_demand_updater->OnDemandUpdate(
      component_ids, component_updater::OnDemandUpdater::Priority::FOREGROUND,
      base::BindOnce(on_updated, std::move(callback)));
}
"""
    replace_once(
        manager,
        old,
        new,
        "SANDIUM_EMPTY_FILTER_CATALOGUE_UPDATE",
        "empty-catalogue-bootstrap-component-update",
    )




def apply_early_component_updater_patch(core: Path) -> None:
    main_delegate = core / "app/brave_main_delegate.cc"
    replace_once(
        main_delegate,
        '#include "base/lazy_instance.h"\n',
        '#include "base/lazy_instance.h"\n#include "base/logging.h"\n',
        '#include "base/logging.h"',
        "early-component-updater-log-include",
    )
    old = """void BraveMainDelegate::AppendCommandLineOptions() {
  auto* command_line = base::CommandLine::ForCurrentProcess();
"""
    new = """void BraveMainDelegate::AppendCommandLineOptions() {
  auto* command_line = base::CommandLine::ForCurrentProcess();
#if BUILDFLAG(IS_ANDROID)
  // SANDIUM_COMPONENT_UPDATER_DEV_ENDPOINT: Sandium's Android build is
  // configured as a non-official Developer Build, so select Brave's
  // development component manifest. This avoids relying on an undefined
  // OFFICIAL_BUILD C++ buildflag; the updater switch is already declared by
  // Brave's existing browser/switches.h include above.
  command_line->AppendSwitch(brave_component_updater::kUseGoUpdateDev);
  LOG(WARNING) << "SANDIUM_COMPONENT_UPDATER_ENDPOINT=development";

  // SANDIUM_COMPONENT_UPDATER_EARLY_ENABLE: keep Chromium's global
  // component-update policy intact, but explicitly permit Brave's components.
  // BraveOnDemandUpdater::RegisterOnDemandUpdater() applies this Brave-only
  // override when it receives the original global-disable state below.
  const bool component_updates_globally_disabled =
      command_line->HasSwitch(switches::kDisableComponentUpdate);
  command_line->AppendSwitch("allow-brave-component-update");
  LOG(WARNING) << "SANDIUM_BRAVE_COMPONENT_UPDATE_OVERRIDE"
               << " global_disable_preserved="
               << component_updates_globally_disabled
               << " brave_component_updates=allowed";
#endif
"""
    replace_once(
        main_delegate,
        old,
        new,
        "SANDIUM_COMPONENT_UPDATER_EARLY_ENABLE",
        "early-android-component-updater-enable",
    )


def apply_component_updater_patch(core: Path) -> None:
    main_parts = core / "browser/brave_browser_main_parts.cc"
    replace_once(
        main_parts,
        '#include "base/command_line.h"\n',
        '#include "base/command_line.h"\n#include "base/logging.h"\n',
        '#include "base/logging.h"',
        "main-parts-component-updater-log-include",
    )
    old = """int ChromeBrowserMainParts::PreMainMessageLoopRun() {
  brave_component_updater::BraveOnDemandUpdater::GetInstance()
      ->RegisterOnDemandUpdater(
          base::CommandLine::ForCurrentProcess()->HasSwitch(
              switches::kDisableComponentUpdate),
          &g_browser_process->component_updater()->GetOnDemandUpdater());

  return ChromeBrowserMainParts_ChromiumImpl::PreMainMessageLoopRun();
}
"""
    new = """int ChromeBrowserMainParts::PreMainMessageLoopRun() {
  // SANDIUM_BRAVE_COMPONENT_UPDATES: preserve Chromium's global update
  // policy. Brave's allow-brave-component-update switch is applied inside
  // RegisterOnDemandUpdater(), so only Brave-owned components are exempted.
  auto* command_line = base::CommandLine::ForCurrentProcess();
  const bool component_updates_globally_disabled =
      command_line->HasSwitch(switches::kDisableComponentUpdate);
  auto* updater_service = g_browser_process->component_updater();
  CHECK(updater_service);
  LOG(INFO) << "SANDIUM_COMPONENT_UPDATER_SERVICE_CREATED ready=true"
            << " global_disable_preserved="
            << component_updates_globally_disabled
            << " brave_component_updates=allowed";
  brave_component_updater::BraveOnDemandUpdater::GetInstance()
      ->RegisterOnDemandUpdater(
          base::CommandLine::ForCurrentProcess()->HasSwitch(
              switches::kDisableComponentUpdate),
          &updater_service->GetOnDemandUpdater());

  return ChromeBrowserMainParts_ChromiumImpl::PreMainMessageLoopRun();
}
"""
    replace_once(
        main_parts,
        old,
        new,
        "SANDIUM_BRAVE_COMPONENT_UPDATES",
        "android-brave-component-updater-enable",
    )


def apply_fragment_patch(core: Path) -> None:
    fragment = core / (
        "android/java/org/chromium/chrome/browser/shields/"
        "ContentFilteringFragment.java"
    )

    replace_once(
        fragment,
        """import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
""",
        """import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
""",
        "import android.os.Handler;",
        "filter-list-runtime-imports",
    )
    replace_once(
        fragment,
        """import java.util.ArrayList;
import java.util.Arrays;
""",
        """import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
""",
        "import java.util.HashSet;",
        "filter-list-catalogue-map-imports",
    )

    replace_once(
        fragment,
        """public class ContentFilteringFragment extends BravePreferenceFragment
        implements FragmentSettingsNavigation,
                BraveContentFilteringListener,
                BottomInsetViewProvider {
    private RecyclerView mRecyclerView;
""",
        """public class ContentFilteringFragment extends BravePreferenceFragment
        implements FragmentSettingsNavigation,
                BraveContentFilteringListener,
                BottomInsetViewProvider {
    private static final String TAG = "SandiumFilterLists";
    private static final String FILTER_LIST_MIGRATION_PREFS =
            "sandium_filter_list_migration";
    private static final String FILTER_LIST_MIGRATION_KEY =
            "ubo_selected_brave_lists_v2";
    private static final String LEGACY_FILTER_LIST_MIGRATION_KEY =
            "ubo_selected_lists_seeded_v1";
    private static final int MAX_FILTER_LIST_UPDATE_ATTEMPTS = 3;
    private static final int MAX_FILTER_LIST_POLL_ATTEMPTS = 12;
    private static final long FILTER_LIST_RETRY_DELAY_MS = 2000L;
    private static final long FILTER_LIST_POLL_DELAY_MS = 1000L;

    private static final String[] FRESH_INSTALL_FILTER_UUIDS = {
        "4C07DB6B-6377-4347-836D-68702CF1494A", // IndianList.
        "E2FA7D98-0BD5-493E-8AF4-950604ADE9CB", // Tracking URL protection.
        "7911A1CB-304E-4CDB-ABB3-E2A94A37E4DD", // Fanboy Social.
        "6b91e355-1421-4c03-9a30-911b4d0fb277", // Anti-AI suggestions.
        "690FF3B4-8B6B-4709-8505-FEC6643D7BD9", // Anti-newsletter popups.
        "67E792D4-AE03-4D1A-9EDE-80E01C81F9B8"  // Fanboy + uBO annoyances.
    };
    private static final String[] POST_V1_ADDITIONAL_FILTER_UUIDS = {
        "690FF3B4-8B6B-4709-8505-FEC6643D7BD9", // New since the v1 migration.
        "67E792D4-AE03-4D1A-9EDE-80E01C81F9B8"
    };

    private final Handler mFilterListRetryHandler = new Handler(Looper.getMainLooper());
    private int mFilterListUpdateAttempts;
    private int mFilterListPollAttempts;
    private boolean mFilterListUpdateInFlight;
    private boolean mManualFilterListUpdatePending;
    private boolean mSelectedBraveListsMigrationStarted;

    private RecyclerView mRecyclerView;
""",
        "FILTER_LIST_MIGRATION_KEY",
        "curated-brave-ubo-list-selection",
    )

    replace_once(
        fragment,
        """    private void getFilterLists() {
        if (mFilterListAndroidHandler != null) {
            mFilterListAndroidHandler.getFilterLists(filterLists -> {
                mFilterLists = filterLists.storage;
                mAdapter.setFilterLists(mFilterLists);
            });
        }
    }
""",
        """    private void getFilterLists() {
        if (mFilterListAndroidHandler == null) return;
        mFilterListAndroidHandler.getFilterLists(filterLists -> {
            if (!isAdded() || mAdapter == null) return;
            mFilterLists = filterLists == null || filterLists.storage == null
                    ? new Value[0] : filterLists.storage;
            mAdapter.setFilterLists(mFilterLists);
            if (mFilterLists.length > 0) {
                onFilterListCatalogueReady();
            } else {
                handleEmptyFilterListCatalogue();
            }
        });
    }

    // SANDIUM_FILTER_LIST_CATALOGUE_STATE_MACHINE: retry the actual component
    // update request after failures, and poll separately while an update is
    // being installed. A repeated read is not counted as a successful refresh.
    private void handleEmptyFilterListCatalogue() {
        if (!isAdded() || mFilterListUpdateInFlight) return;
        if (mFilterListUpdateAttempts == 0) {
            requestFilterListCatalogueRefresh();
            return;
        }
        if (mFilterListPollAttempts < MAX_FILTER_LIST_POLL_ATTEMPTS) {
            mFilterListPollAttempts++;
            mFilterListRetryHandler.removeCallbacksAndMessages(null);
            mFilterListRetryHandler.postDelayed(
                    this::getFilterLists, FILTER_LIST_POLL_DELAY_MS);
            return;
        }
        if (mFilterListUpdateAttempts < MAX_FILTER_LIST_UPDATE_ATTEMPTS) {
            mFilterListPollAttempts = 0;
            requestFilterListCatalogueRefresh();
            return;
        }
        finishFilterListCatalogueFailure();
    }

    private void requestFilterListCatalogueRefresh() {
        if (!isAdded() || mFilterListAndroidHandler == null
                || mFilterListUpdateInFlight) {
            return;
        }
        if (mFilterListUpdateAttempts >= MAX_FILTER_LIST_UPDATE_ATTEMPTS) {
            finishFilterListCatalogueFailure();
            return;
        }
        mFilterListUpdateAttempts++;
        mFilterListUpdateInFlight = true;
        Log.i(TAG, "Requesting Brave filter catalogue; attempt "
                + mFilterListUpdateAttempts);
        mFilterListAndroidHandler.updateFilterLists(isSuccess -> {
            if (!isAdded()) return;
            mFilterListUpdateInFlight = false;
            if (mFilterLists != null && mFilterLists.length > 0) {
                onFilterListCatalogueReady();
                return;
            }
            if (isSuccess) {
                // UPDATE_IN_PROGRESS is a valid result; the component-ready
                // callback will populate the catalogue asynchronously.
                mFilterListPollAttempts = 0;
                mFilterListRetryHandler.removeCallbacksAndMessages(null);
                mFilterListRetryHandler.postDelayed(
                        this::getFilterLists, FILTER_LIST_POLL_DELAY_MS);
            } else if (mFilterListUpdateAttempts < MAX_FILTER_LIST_UPDATE_ATTEMPTS) {
                Log.w(TAG, "Brave filter catalogue update failed; scheduling retry");
                long delay = FILTER_LIST_RETRY_DELAY_MS * mFilterListUpdateAttempts;
                mFilterListRetryHandler.removeCallbacksAndMessages(null);
                mFilterListRetryHandler.postDelayed(
                        this::requestFilterListCatalogueRefresh, delay);
            } else {
                finishFilterListCatalogueFailure();
            }
        });
    }

    private void onFilterListCatalogueReady() {
        mFilterListUpdateInFlight = false;
        mFilterListUpdateAttempts = 0;
        mFilterListPollAttempts = 0;
        mFilterListRetryHandler.removeCallbacksAndMessages(null);
        Log.i(TAG, "Brave filter catalogue loaded; visible entries="
                + mFilterLists.length);
        seedSelectedBraveListsOnce();
        if (mManualFilterListUpdatePending) {
            Toast.makeText(getActivity(),
                    getString(R.string.update_filter_list_success_text),
                    Toast.LENGTH_SHORT).show();
            mManualFilterListUpdatePending = false;
        }
    }

    private void finishFilterListCatalogueFailure() {
        mFilterListUpdateInFlight = false;
        mFilterListRetryHandler.removeCallbacksAndMessages(null);
        Log.e(TAG, "Brave filter catalogue is still empty after bounded retries");
        Toast.makeText(getActivity(), getString(R.string.update_filter_list_fail_text),
                Toast.LENGTH_SHORT).show();
        mManualFilterListUpdatePending = false;
    }

    private void seedSelectedBraveListsOnce() {
        if (mSelectedBraveListsMigrationStarted
                || mFilterLists == null
                || mFilterLists.length == 0
                || mFilterListAndroidHandler == null
                || !isAdded()) {
            return;
        }

        SharedPreferences preferences = requireContext().getSharedPreferences(
                FILTER_LIST_MIGRATION_PREFS, Context.MODE_PRIVATE);
        if (preferences.getBoolean(FILTER_LIST_MIGRATION_KEY, false)) return;

        // Preserve choices made after the previous migration. Existing v1
        // installations get only the two additional lists introduced here.
        String[] targetUuids = preferences.getBoolean(
                LEGACY_FILTER_LIST_MIGRATION_KEY, false)
                ? POST_V1_ADDITIONAL_FILTER_UUIDS : FRESH_INSTALL_FILTER_UUIDS;

        Set<String> availableUuids = new HashSet<>();
        for (Value item : mFilterLists) {
            if (item == null || item.getDictionaryValue() == null
                    || item.getDictionaryValue().storage == null) {
                continue;
            }
            Map<String, Value> fields = item.getDictionaryValue().storage;
            Value uuidValue = fields.get("uuid");
            if (uuidValue != null) availableUuids.add(uuidValue.getStringValue());
        }

        int enabledCount = 0;
        boolean missingList = false;
        for (String uuid : targetUuids) {
            if (availableUuids.contains(uuid)) {
                mFilterListAndroidHandler.enableFilter(uuid, true);
                enabledCount++;
            } else {
                missingList = true;
                Log.w(TAG, "Selected filter UUID not in downloaded catalogue: " + uuid);
            }
        }
        if (enabledCount == 0) {
            Log.w(TAG, "No selected Sandium filter UUIDs were present; migration remains pending");
            return;
        }

        mSelectedBraveListsMigrationStarted = true;
        if (!missingList) {
            preferences.edit().putBoolean(FILTER_LIST_MIGRATION_KEY, true).apply();
        }
        Log.i(TAG, "Enabled " + enabledCount + " verified Brave/uBO filter-list entries");
        mFilterListRetryHandler.postDelayed(this::getFilterLists, 750L);
    }

""",
        "SANDIUM_FILTER_LIST_CATALOGUE_STATE_MACHINE",
        "catalogue-state-machine-and-curated-ubo-migration",
    )

    old_manual = """        } else if (item.getItemId() == R.id.update_filter_list_id) {
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
"""
    new_manual = """        } else if (item.getItemId() == R.id.update_filter_list_id) {
            if (mFilterListAndroidHandler != null) {
                // SANDIUM_MANUAL_FILTER_LIST_UPDATE: use the same bounded
                // update-and-poll path as first-run catalogue bootstrap.
                mFilterListUpdateAttempts = 0;
                mFilterListPollAttempts = 0;
                mManualFilterListUpdatePending = true;
                mFilterListRetryHandler.removeCallbacksAndMessages(null);
                requestFilterListCatalogueRefresh();
            }
            return true;
        }
"""
    replace_once(
        fragment,
        old_manual,
        new_manual,
        "SANDIUM_MANUAL_FILTER_LIST_UPDATE",
        "manual-update-state-machine",
    )

    replace_once(
        fragment,
        """    @Override
    public void onDestroy() {
        if (mFilterListAndroidHandler != null) {
""",
        """    @Override
    public void onDestroy() {
        // SANDIUM_FILTER_LIST_HANDLER_CLEANUP.
        mFilterListRetryHandler.removeCallbacksAndMessages(null);
        if (mFilterListAndroidHandler != null) {
""",
        "SANDIUM_FILTER_LIST_HANDLER_CLEANUP",
        "filter-list-handler-cleanup",
    )


def apply_adapter_patch(core: Path) -> None:
    adapter = core / (
        "android/java/org/chromium/chrome/browser/shields/"
        "ContentFilteringAdapter.java"
    )
    old = """    public void setFilterLists(Value filterLists[]) {
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
    new = """    public void setFilterLists(Value filterLists[]) {
        // SANDIUM_FILTER_LIST_ADAPTER_REFRESH: the catalogue is polled while
        // component updates complete, so refresh the existing rows safely.
        mFilterLists = filterLists == null ? new Value[0] : filterLists;
        notifyDataSetChanged();
    }
"""
    replace_once(
        adapter,
        old,
        new,
        "SANDIUM_FILTER_LIST_ADAPTER_REFRESH",
        "filter-list-adapter-refresh",
    )


def apply_runtime_diagnostics_patch(core: Path) -> None:
    delegate = core / (
        "components/brave_component_updater/browser/"
        "brave_component_updater_delegate.cc"
    )
    replace_once(
        delegate,
        '#include "base/task/sequenced_task_runner.h"\n',
        '#include "base/logging.h"\n#include "base/task/sequenced_task_runner.h"\n',
        '#include "base/logging.h"',
        "component-registration-log-include",
    )
    replace_once(
        delegate,
        """  if (!BraveOnDemandUpdater::GetInstance()->is_component_update_disabled()) {
    RegisterComponent(base::to_address(component_updater_), component_name,
                      component_base64_public_key,
                      std::move(registered_callback),
                      std::move(ready_callback));
  }
""",
        """  const bool updates_disabled =
      BraveOnDemandUpdater::GetInstance()->is_component_update_disabled();
  LOG(INFO) << "SANDIUM_COMPONENT_REGISTRATION name=" << component_name
            << " disabled=" << updates_disabled;
  if (!updates_disabled) {
    RegisterComponent(base::to_address(component_updater_), component_name,
                      component_base64_public_key,
                      std::move(registered_callback),
                      std::move(ready_callback));
  } else {
    LOG(ERROR) << "SANDIUM_COMPONENT_REGISTRATION_BLOCKED name="
               << component_name;
  }
""",
        "SANDIUM_COMPONENT_REGISTRATION",
        "component-registration-runtime-log",
    )

    installer = core / (
        "components/brave_shields/core/browser/"
        "ad_block_component_installer.cc"
    )
    replace_once(
        installer,
        '#include "base/functional/callback.h"\n',
        '#include "base/functional/callback.h"\n#include "base/logging.h"\n',
        '#include "base/logging.h"',
        "component-installer-log-include",
    )
    replace_once(
        installer,
        """void OnRegistered(const std::string& component_id) {
  // Unlike other components, which are only installed but not updated in
  // `OnRegistered`, we do always want to update the ad block component upon
  // registration.
  BraveOnDemandUpdater::GetInstance()->OnDemandUpdate(
""",
        """void OnRegistered(const std::string& component_id) {
  // Unlike other components, which are only installed but not updated in
  // `OnRegistered`, we do always want to update the ad block component upon
  // registration.
  LOG(INFO) << "SANDIUM_ADBLOCK_COMPONENT_REGISTERED id=" << component_id;
  BraveOnDemandUpdater::GetInstance()->OnDemandUpdate(
""",
        "SANDIUM_ADBLOCK_COMPONENT_REGISTERED",
        "adblock-component-registered-log",
    )

    catalog = core / (
        "components/brave_shields/core/browser/"
        "ad_block_filter_list_catalog_provider.cc"
    )
    replace_once(
        catalog,
        '#include "base/files/file_path.h"\n',
        '#include "base/files/file_path.h"\n#include "base/logging.h"\n',
        '#include "base/logging.h"',
        "catalog-provider-log-include",
    )
    replace_once(
        catalog,
        """  component_path_ = path;

  // Load the filter list catalog (as a string)
""",
        """  component_path_ = path;
  LOG(INFO) << "SANDIUM_FILTER_CATALOG_COMPONENT_READY path=" << path.value();

  // Load the filter list catalog (as a string)
""",
        "SANDIUM_FILTER_CATALOG_COMPONENT_READY",
        "catalog-component-ready-log",
    )

    manager = core / (
        "components/brave_shields/core/browser/"
        "ad_block_component_service_manager.cc"
    )
    replace_once(
        manager,
        '#include "base/location.h"\n',
        '#include "base/location.h"\n#include "base/logging.h"\n',
        '#include "base/logging.h"',
        "catalog-manager-log-include",
    )
    replace_once(
        manager,
        """void AdBlockComponentServiceManager::OnFilterListCatalogLoaded(
    const std::string& catalog_json) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  SetFilterListCatalog(FilterListCatalogFromJSON(catalog_json));

""",
        """void AdBlockComponentServiceManager::OnFilterListCatalogLoaded(
    const std::string& catalog_json) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  auto catalog = FilterListCatalogFromJSON(catalog_json);
  LOG(INFO) << "SANDIUM_FILTER_CATALOG_PARSED bytes=" << catalog_json.size()
            << " entries=" << catalog.size();
  SetFilterListCatalog(std::move(catalog));

""",
        "SANDIUM_FILTER_CATALOG_PARSED",
        "catalog-parse-runtime-log",
    )

    filter_service = core / (
        "components/brave_shields/content/browser/"
        "filter_list_service.cc"
    )
    replace_once(
        filter_service,
        '#include "base/feature_list.h"\n',
        '#include "base/feature_list.h"\n#include "base/logging.h"\n',
        '#include "base/logging.h"',
        "filter-service-log-include",
    )
    replace_once(
        filter_service,
        """void FilterListService::GetFilterLists(GetFilterListsCallback callback) {
  std::move(callback).Run(
      ad_block_service_->component_service_manager()->GetRegionalLists());
}
""",
        """void FilterListService::GetFilterLists(GetFilterListsCallback callback) {
  auto lists = ad_block_service_->component_service_manager()->GetRegionalLists();
  LOG(INFO) << "SANDIUM_FILTER_LIST_UI_COUNT=" << lists.size();
  std::move(callback).Run(std::move(lists));
}
""",
        "SANDIUM_FILTER_LIST_UI_COUNT",
        "filter-list-ui-count-log",
    )


def apply_patches(core: Path) -> None:
    apply_on_demand_updater_header_patch(core)
    apply_manager_patch(core)
    apply_early_component_updater_patch(core)
    apply_component_updater_patch(core)
    apply_runtime_diagnostics_patch(core)
    apply_fragment_patch(core)
    apply_adapter_patch(core)


def verify_patches(core: Path) -> None:
    manager = (
        core / "components/brave_shields/core/browser/"
        "ad_block_component_service_manager.cc"
    ).read_text(encoding="utf-8")
    main_parts = (core / "browser/brave_browser_main_parts.cc").read_text(
        encoding="utf-8"
    )
    main_delegate = (core / "app/brave_main_delegate.cc").read_text(
        encoding="utf-8"
    )
    component_delegate = (
        core / "components/brave_component_updater/browser/"
        "brave_component_updater_delegate.cc"
    ).read_text(encoding="utf-8")
    component_installer = (
        core / "components/brave_shields/core/browser/"
        "ad_block_component_installer.cc"
    ).read_text(encoding="utf-8")
    catalog_provider = (
        core / "components/brave_shields/core/browser/"
        "ad_block_filter_list_catalog_provider.cc"
    ).read_text(encoding="utf-8")
    updater_header = (
        core / "components/brave_component_updater/browser/"
        "brave_on_demand_updater.h"
    ).read_text(encoding="utf-8")
    manager = (
        core / "components/brave_shields/core/browser/"
        "ad_block_component_service_manager.cc"
    ).read_text(encoding="utf-8")
    filter_service = (
        core / "components/brave_shields/content/browser/"
        "filter_list_service.cc"
    ).read_text(encoding="utf-8")
    fragment = (
        core / "android/java/org/chromium/chrome/browser/shields/"
        "ContentFilteringFragment.java"
    ).read_text(encoding="utf-8")
    adapter = (
        core / "android/java/org/chromium/chrome/browser/shields/"
        "ContentFilteringAdapter.java"
    ).read_text(encoding="utf-8")

    required = (
        ("manager", "if (component_filters_providers_.empty())", manager),
        ("manager", "SANDIUM_EMPTY_FILTER_CATALOGUE_UPDATE=REQUEST", manager),
        ("updater_header", "SANDIUM_ON_DEMAND_UPDATER_READINESS", updater_header),
        ("main_parts", "SANDIUM_BRAVE_COMPONENT_UPDATES", main_parts),
        ("main_parts", "SANDIUM_COMPONENT_UPDATER_SERVICE_CREATED", main_parts),
        ("main_delegate", "SANDIUM_BRAVE_COMPONENT_UPDATE_OVERRIDE", main_delegate),
        ("main_delegate", "SANDIUM_COMPONENT_UPDATER_EARLY_ENABLE", main_delegate),
        ("main_delegate", "SANDIUM_COMPONENT_UPDATER_ENDPOINT=development", main_delegate),
        ("component_delegate", "SANDIUM_COMPONENT_REGISTRATION", component_delegate),
        ("component_installer", "SANDIUM_ADBLOCK_COMPONENT_REGISTERED", component_installer),
        ("manager", "SANDIUM_FILTER_CATALOG_UPDATE_RESULT", manager),
        ("catalog_provider", "SANDIUM_FILTER_CATALOG_COMPONENT_READY", catalog_provider),
        ("manager", "SANDIUM_FILTER_CATALOG_PARSED", manager),
        ("filter_service", "SANDIUM_FILTER_LIST_UI_COUNT", filter_service),
        ("fragment", "SANDIUM_FILTER_LIST_CATALOGUE_STATE_MACHINE", fragment),
        ("fragment", "SANDIUM_MANUAL_FILTER_LIST_UPDATE", fragment),
        ("fragment", "SANDIUM_FILTER_LIST_HANDLER_CLEANUP", fragment),
        ("adapter", "SANDIUM_FILTER_LIST_ADAPTER_REFRESH", adapter),
    )
    missing = [f"{name}:{marker}" for name, marker, content in required
               if marker not in content]
    if missing:
        raise SystemExit(
            "SANDIUM_ADBLOCK_GATE=FAIL patch verification missing "
            + ", ".join(missing)
        )
    if "SANDIUM_FILTER_CATALOGUE_BOOTSTRAP" in manager:
        raise SystemExit("SANDIUM_ADBLOCK_GATE=FAIL stale forced-update manager patch remains")
    if 'RemoveSwitch(switches::kDisableComponentUpdate)' in main_parts:
        raise SystemExit("SANDIUM_ADBLOCK_GATE=FAIL global component-update policy was modified")
    if 'RemoveSwitch(switches::kDisableComponentUpdate)' in main_delegate:
        raise SystemExit("SANDIUM_ADBLOCK_GATE=FAIL global component-update policy was modified during early startup")
    if 'AppendSwitch("allow-brave-component-update")' not in main_delegate:
        raise SystemExit("SANDIUM_ADBLOCK_GATE=FAIL early Brave-only component-updater override missing")
    if 'global_disable_preserved=' not in main_parts:
        raise SystemExit("SANDIUM_ADBLOCK_GATE=FAIL global updater policy diagnostic missing")
    # Count the actual member invocation, not explanatory comments that
    # may mention the method name.
    if main_parts.count("->RegisterOnDemandUpdater(") != 1:
        raise SystemExit("SANDIUM_ADBLOCK_GATE=FAIL updater registration call is not unique")
    if "&g_browser_process->component_updater()->GetOnDemandUpdater()" in main_parts:
        raise SystemExit("SANDIUM_ADBLOCK_GATE=FAIL stale upstream updater argument remains")
    if 'AppendSwitch(\n      "allow-brave-component-update")' in main_parts:
        raise SystemExit("SANDIUM_ADBLOCK_GATE=FAIL obsolete late-only updater override remains")
    if 'AppendSwitch("allow-brave-component-update")' not in main_delegate:
        raise SystemExit("SANDIUM_ADBLOCK_GATE=FAIL early Android component-updater override missing")
    if "LOG(INFO) << \"SANDIUM_FILTER_CATALOG_PARSED bytes=\"" not in manager:
        raise SystemExit("SANDIUM_ADBLOCK_GATE=FAIL catalogue parse diagnostic missing")
    if len(FRESH_INSTALL_FILTER_UUIDS) != len(set(FRESH_INSTALL_FILTER_UUIDS)):
        raise SystemExit("SANDIUM_ADBLOCK_GATE=FAIL duplicate selected filter UUID")
    print(
        "SANDIUM_ADBLOCK_GATE=PASS "
        "component_updater=enabled_android "
        "global_update_switch=preserved_brave_override=enabled "
        "empty_catalogue_bootstrap_refresh=enabled "
        "native_catalogue=refresh-request-enabled "
        "update_retries=bounded "
        "update_result_codes=logged "
        "adapter_refresh=verified "
        f"curated_lists={len(FRESH_INSTALL_FILTER_UUIDS)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", required=True, type=Path)
    args = parser.parse_args()
    core = args.core.resolve()
    if not core.is_dir():
        raise SystemExit(f"SANDIUM_ADBLOCK_GATE=FAIL core directory missing: {core}")

    try:
        tag = subprocess.run(
            ["git", "-C", str(core), "describe", "--tags", "--exact-match"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(
            f"SANDIUM_ADBLOCK_GATE=FAIL cannot verify Brave Core pin: {exc}"
        )
    if tag != PIN:
        raise SystemExit(
            f"SANDIUM_ADBLOCK_GATE=FAIL expected {PIN}, found {tag or 'untagged'}"
        )
    print(f"SANDIUM_ADBLOCK_SOURCE_PIN=PASS tag={tag}")

    apply_patches(core)
    verify_patches(core)


if __name__ == "__main__":
    main()
