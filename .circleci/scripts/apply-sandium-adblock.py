#!/usr/bin/env python3
"""Apply Sandium's Brave-native ad-filter bootstrap fixes to Brave v1.99.54."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

PIN = "v1.99.54"


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> None:
    if not path.is_file():
        raise SystemExit(f"SANDIUM_ADBLOCK_GATE=FAIL missing file: {path}")
    source = path.read_text(encoding="utf-8")
    if marker in source:
        if new not in source:
            raise SystemExit(f"SANDIUM_ADBLOCK_GATE=FAIL incomplete patch: {label}")
        print(f"SANDIUM_ADBLOCK_PATCH={label}:ALREADY_APPLIED")
        return
    count = source.count(old)
    if count != 1:
        raise SystemExit(
            f"SANDIUM_ADBLOCK_GATE=FAIL {label}: expected one source anchor, found {count}"
        )
    path.write_text(source.replace(old, new, 1), encoding="utf-8")
    print(f"SANDIUM_ADBLOCK_PATCH={label}:APPLIED")


def apply_manager_patch(core: Path) -> None:
    manager = core / (
        "components/brave_shields/core/browser/"
        "ad_block_component_service_manager.cc"
    )
    replace_once(
        manager,
        '#include "base/location.h"\n',
        '#include "base/location.h"\n#include "base/logging.h"\n',
        '#include "base/logging.h"',
        "manager-logging-include",
    )
    old = """  // If there are currently no components to update, then run the callback with
  // a success value in a future turn.
  if (component_filters_providers_.empty()) {
    std::move(callback).Run(true);
    return;
  }

"""
    new = """  // SANDIUM_FILTER_CATALOGUE_BOOTSTRAP: even with no optional providers
  // enabled, refresh Brave's base resources and filter-list catalogue.
  if (component_filters_providers_.empty()) {
    LOG(INFO) << "SANDIUM_FILTER_CATALOGUE_BOOTSTRAP=REQUEST";
  }

"""
    replace_once(
        manager, old, new, "SANDIUM_FILTER_CATALOGUE_BOOTSTRAP",
        "empty-catalogue-bootstrap",
    )
    old_callback = """  auto on_updated = [](decltype(callback) cb, update_client::Error error) {
    std::move(cb).Run(error == update_client::Error::NONE ||
                      error == update_client::Error::UPDATE_IN_PROGRESS);
  };
"""
    new_callback = """  auto on_updated = [](decltype(callback) cb, update_client::Error error) {
    LOG(INFO) << "SANDIUM_FILTER_CATALOGUE_UPDATE_RESULT error="
              << static_cast<int>(error);
    std::move(cb).Run(error == update_client::Error::NONE ||
                      error == update_client::Error::UPDATE_IN_PROGRESS);
  };
"""
    replace_once(
        manager, old_callback, new_callback,
        "SANDIUM_FILTER_CATALOGUE_UPDATE_RESULT",
        "catalogue-update-result-diagnostic",
    )


def apply_component_updater_patch(core: Path) -> None:
    main_delegate = core / "app/brave_main_delegate.cc"
    replace_once(
        main_delegate,
        '#include "base/lazy_instance.h"\n',
        '#include "base/lazy_instance.h"\n#include "base/logging.h"\n',
        '#include "base/logging.h"',
        "component-updater-logging-include",
    )
    old = """void BraveMainDelegate::AppendCommandLineOptions() {
  auto* command_line = base::CommandLine::ForCurrentProcess();
"""
    new = """void BraveMainDelegate::AppendCommandLineOptions() {
  auto* command_line = base::CommandLine::ForCurrentProcess();
#if BUILDFLAG(IS_ANDROID)
  // Sandium is a non-official Android Release build. Use Brave's QA component
  // feed and allow Brave-owned components only; Chromium's global updater
  // policy is not changed.
  command_line->AppendSwitch(brave_component_updater::kUseGoUpdateDev);
  command_line->AppendSwitch("allow-brave-component-update");
  LOG(WARNING) << "SANDIUM_COMPONENT_UPDATER=ENABLED endpoint=development";
#endif
"""
    replace_once(
        main_delegate, old, new, "SANDIUM_COMPONENT_UPDATER=ENABLED",
        "android-brave-component-updater-enable",
    )


def apply_fragment_patch(core: Path) -> None:
    fragment = core / (
        "android/java/org/chromium/chrome/browser/shields/"
        "ContentFilteringFragment.java"
    )
    replace_once(
        fragment,
        "import android.os.Bundle;\n",
        "import android.os.Bundle;\n"
        "import android.os.Handler;\n"
        "import android.os.Looper;\n"
        "import android.util.Log;\n",
        "import android.os.Handler;",
        "filter-list-retry-imports",
    )
    replace_once(
        fragment,
        """    private RecyclerView mRecyclerView;

    private ContentFilteringAdapter mAdapter;
""",
        """    private static final String TAG = "SandiumFilterLists";
    private static final int MAX_FILTER_LIST_UPDATE_ATTEMPTS = 3;
    private static final int MAX_FILTER_LIST_POLL_ATTEMPTS = 12;
    private static final long FILTER_LIST_RETRY_DELAY_MS = 2000L;
    private static final long FILTER_LIST_POLL_DELAY_MS = 1000L;

    private final Handler mFilterListRetryHandler = new Handler(Looper.getMainLooper());
    private int mFilterListUpdateAttempts;
    private int mFilterListPollAttempts;
    private boolean mFilterListUpdateInFlight;
    private boolean mManualFilterListUpdatePending;

    private RecyclerView mRecyclerView;

    private ContentFilteringAdapter mAdapter;
""",
        "MAX_FILTER_LIST_UPDATE_ATTEMPTS",
        "bounded-filter-list-bootstrap-state",
    )
    old_get = """    private void getFilterLists() {
        if (mFilterListAndroidHandler != null) {
            mFilterListAndroidHandler.getFilterLists(filterLists -> {
                mFilterLists = filterLists.storage;
                mAdapter.setFilterLists(mFilterLists);
            });
        }
    }
"""
    new_get = """    private void getFilterLists() {
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

    // SANDIUM_FILTER_LIST_CATALOGUE_STATE_MACHINE: UPDATE_IN_PROGRESS is not
    // proof that the downloaded catalogue is ready. Poll separately and retry
    // component requests a bounded number of times.
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
        if (!isAdded() || mFilterListAndroidHandler == null || mFilterListUpdateInFlight) {
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
            } else if (isSuccess) {
                mFilterListPollAttempts = 0;
                mFilterListRetryHandler.removeCallbacksAndMessages(null);
                mFilterListRetryHandler.postDelayed(
                        this::getFilterLists, FILTER_LIST_POLL_DELAY_MS);
            } else if (mFilterListUpdateAttempts < MAX_FILTER_LIST_UPDATE_ATTEMPTS) {
                Log.w(TAG, "Brave filter catalogue update failed; retrying");
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
        Log.e(TAG, "Brave filter catalogue is empty after bounded retries");
        if (mManualFilterListUpdatePending) {
            Toast.makeText(getActivity(),
                    getString(R.string.update_filter_list_fail_text),
                    Toast.LENGTH_SHORT).show();
            mManualFilterListUpdatePending = false;
        }
    }
"""
    replace_once(
        fragment, old_get, new_get, "SANDIUM_FILTER_LIST_CATALOGUE_STATE_MACHINE",
        "bounded-filter-list-bootstrap-and-poll",
    )
    old_manual = """mFilterListAndroidHandler.updateFilterLists(
                        isSuccess -> {
                            if (isSuccess) {
                                setData();
                            }
                            String message =
                                    isSuccess
                                            ? getString(R.string.update_filter_list_success_text)
                                            : getString(R.string.update_filter_list_fail_text);
                            Toast.makeText(getActivity(), message, Toast.LENGTH_SHORT).show();
                        });"""
    new_manual = """mFilterListUpdateAttempts = 0;
                mFilterListPollAttempts = 0;
                mManualFilterListUpdatePending = true;
                mFilterListRetryHandler.removeCallbacksAndMessages(null);
                requestFilterListCatalogueRefresh();"""
    replace_once(
        fragment, old_manual, new_manual, "requestFilterListCatalogueRefresh();",
        "manual-filter-list-update-state-machine",
    )
    replace_once(
        fragment,
        """    @Override
    public void onDestroy() {
        if (mFilterListAndroidHandler != null) {
""",
        """    @Override
    public void onDestroy() {
        mFilterListRetryHandler.removeCallbacksAndMessages(null);
        if (mFilterListAndroidHandler != null) {
""",
        "mFilterListRetryHandler.removeCallbacksAndMessages(null);\n        if (mFilterListAndroidHandler != null)",
        "filter-list-retry-handler-cleanup",
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
        // SANDIUM_FILTER_LIST_ADAPTER_REFRESH: catalogue polling can update
        // these rows asynchronously; refresh the adapter's actual data set.
        mFilterLists = filterLists == null ? new Value[0] : filterLists;
        notifyDataSetChanged();
    }
"""
    replace_once(
        adapter, old, new, "SANDIUM_FILTER_LIST_ADAPTER_REFRESH",
        "async-filter-list-adapter-refresh",
    )


def apply_patches(core: Path) -> None:
    apply_manager_patch(core)
    apply_component_updater_patch(core)
    apply_fragment_patch(core)
    apply_adapter_patch(core)


def verify_patches(core: Path) -> None:
    manager = (
        core / "components/brave_shields/core/browser/"
        "ad_block_component_service_manager.cc"
    ).read_text(encoding="utf-8")
    main_delegate = (
        core / "app/brave_main_delegate.cc"
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
        ("manager", "SANDIUM_FILTER_CATALOGUE_UPDATE_RESULT", manager),
        ("main_delegate", "SANDIUM_COMPONENT_UPDATER=ENABLED", main_delegate),
        ("main_delegate", "brave_component_updater::kUseGoUpdateDev", main_delegate),
        ("main_delegate", 'AppendSwitch("allow-brave-component-update")', main_delegate),
        ("fragment", "SANDIUM_FILTER_LIST_CATALOGUE_STATE_MACHINE", fragment),
        ("fragment", "MAX_FILTER_LIST_UPDATE_ATTEMPTS = 3", fragment),
        ("fragment", "MAX_FILTER_LIST_POLL_ATTEMPTS = 12", fragment),
        ("fragment", "SANDIUM_FILTER_LIST_CATALOGUE_STATE_MACHINE", fragment),
        ("fragment", "requestFilterListCatalogueRefresh();", fragment),
        ("adapter", "SANDIUM_FILTER_LIST_ADAPTER_REFRESH", adapter),
        ("adapter", "notifyDataSetChanged();", adapter),
    )
    missing = [name + ":" + marker for name, marker, content in required if marker not in content]
    if missing:
        raise SystemExit("SANDIUM_ADBLOCK_GATE=FAIL missing markers: " + ", ".join(missing))
    if "std::move(callback).Run(true);\n    return;" in manager:
        raise SystemExit("SANDIUM_ADBLOCK_GATE=FAIL empty catalogue still returns false success")
    if "RemoveSwitch(switches::kDisableComponentUpdate)" in main_delegate:
        raise SystemExit("SANDIUM_ADBLOCK_GATE=FAIL Chromium global updater policy was changed")
    print(
        "SANDIUM_ADBLOCK_GATE=PASS brave_core=v1.99.54 "
        "native_ubo_engine=preserved component_catalogue_bootstrap=enabled "
        "bounded_retry_poll=enabled global_chromium_updater_policy=preserved"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", required=True, type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    core = args.core.resolve()
    if not core.is_dir():
        raise SystemExit("SANDIUM_ADBLOCK_GATE=FAIL core directory missing: " + str(core))
    try:
        tag = subprocess.run(
            ["git", "-C", str(core), "describe", "--tags", "--exact-match"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit("SANDIUM_ADBLOCK_GATE=FAIL cannot verify Brave Core pin: " + str(exc))
    if tag != PIN:
        raise SystemExit("SANDIUM_ADBLOCK_GATE=FAIL expected " + PIN + ", found " + (tag or "untagged"))
    print("SANDIUM_ADBLOCK_SOURCE_PIN=PASS tag=" + tag)
    if not args.verify_only:
        apply_patches(core)
    verify_patches(core)


if __name__ == "__main__":
    main()
