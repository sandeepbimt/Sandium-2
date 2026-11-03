#!/usr/bin/env python3
"""Apply Sandium's Brave-native + uBlock-compatible filter-list integration."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

PIN = "v1.98.62"

# These UUIDs are entries in Brave's filter-list catalogue. Brave's hidden
# default components already include uBO core, privacy, badware, resource
# abuse, unbreak, quick-fixes, link-shorteners and cookie-notice rules.
# The visible additions below complement those defaults without duplicating
# the same URLs as custom subscriptions.
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


def apply_manager_patch(core: Path) -> None:
    manager = core / (
        "components/brave_shields/core/browser/"
        "ad_block_component_service_manager.cc"
    )
    old = """  // If there are currently no components to update, then run the callback with
  // a success value in a future turn.
  if (component_filters_providers_.empty()) {
    std::move(callback).Run(true);
    return;
  }

  std::vector<std::string> component_ids = {
"""
    new = """  // SANDIUM_FILTER_CATALOGUE_BOOTSTRAP: first-run Android has no regional
  // providers until the catalogue component is installed. Do not report a
  // false success here; always request Brave's default resources and catalogue.
  if (brave_component_updater::BraveOnDemandUpdater::GetInstance()
          ->is_component_update_disabled()) {
    std::move(callback).Run(false);
    return;
  }

  std::vector<std::string> component_ids = {
"""
    replace_once(
        manager,
        old,
        new,
        "SANDIUM_FILTER_CATALOGUE_BOOTSTRAP",
        "catalogue-bootstrap-and-disabled-updater-gate",
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


def apply_patches(core: Path) -> None:
    apply_manager_patch(core)
    apply_fragment_patch(core)
    apply_adapter_patch(core)


def verify_patches(core: Path) -> None:
    manager = (
        core / "components/brave_shields/core/browser/"
        "ad_block_component_service_manager.cc"
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
        ("manager", "SANDIUM_FILTER_CATALOGUE_BOOTSTRAP", manager),
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
    if len(FRESH_INSTALL_FILTER_UUIDS) != len(set(FRESH_INSTALL_FILTER_UUIDS)):
        raise SystemExit("SANDIUM_ADBLOCK_GATE=FAIL duplicate selected filter UUID")
    print(
        "SANDIUM_ADBLOCK_GATE=PASS "
        "native_catalogue=bootstrapped "
        "update_retries=bounded "
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
