#!/usr/bin/env python3
"""Apply Sandium's Brave v1.98.62 filter-list bootstrap and uBO migration."""
from __future__ import annotations
import argparse
import subprocess
from pathlib import Path

PIN = "v1.98.62"

def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> None:
    if not path.is_file():
        raise SystemExit(f"SANDIUM_ADBLOCK_GATE=FAIL missing {path}")
    source = path.read_text(encoding="utf-8")
    if marker in source:
        if new not in source:
            raise SystemExit(f"SANDIUM_ADBLOCK_GATE=FAIL {label}: incomplete existing patch")
        print(f"SANDIUM_ADBLOCK_PATCH={label}:ALREADY_APPLIED")
        return
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"SANDIUM_ADBLOCK_GATE=FAIL {label}: expected one anchor, found {count}")
    updated = source.replace(old, new, 1)
    if marker not in updated or new not in updated:
        raise SystemExit(f"SANDIUM_ADBLOCK_GATE=FAIL {label}: post-write verification failed")
    path.write_text(updated, encoding="utf-8")
    print(f"SANDIUM_ADBLOCK_PATCH={label}:APPLIED")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", required=True, type=Path)
    core = parser.parse_args().core.resolve()
    if not core.is_dir():
        raise SystemExit(f"SANDIUM_ADBLOCK_GATE=FAIL core directory missing: {core}")
    try:
        tag = subprocess.run(
            ["git", "-C", str(core), "describe", "--tags", "--exact-match"],
            check=True, capture_output=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"SANDIUM_ADBLOCK_GATE=FAIL cannot verify Brave Core pin: {exc}")
    if tag != PIN:
        raise SystemExit(f"SANDIUM_ADBLOCK_GATE=FAIL expected {PIN}, found {tag or 'untagged'}")
    print(f"SANDIUM_ADBLOCK_SOURCE_PIN=PASS tag={tag}")

    manager = core / "components/brave_shields/core/browser/ad_block_component_service_manager.cc"
    old_manager = '''  // If there are currently no components to update, then run the callback with
  // a success value in a future turn.
  if (component_filters_providers_.empty()) {
    std::move(callback).Run(true);
    return;
  }

  std::vector<std::string> component_ids = {
'''
    new_manager = '''  // Always request the default resources and filter-list catalogue, even when
  // no regional providers are active yet. Returning success here would make an
  // empty first-run catalogue impossible to bootstrap from the Android UPDATE
  // action.
  std::vector<std::string> component_ids = {
'''
    replace_once(manager, old_manager, new_manager,
                 "empty first-run catalogue impossible to bootstrap",
                 "catalogue-update-bootstrap")

    fragment = core / "android/java/org/chromium/chrome/browser/shields/ContentFilteringFragment.java"
    replace_once(fragment,
'''import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
''',
'''import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
''',
                 "import android.os.Handler;", "filter-list-retry-imports")
    replace_once(fragment,
'''import java.util.ArrayList;
import java.util.Arrays;
''',
'''import org.chromium.url.mojom.Url;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;
''',
                 "import java.util.HashSet;", "filter-list-migration-imports")

    replace_once(fragment,
'''public class ContentFilteringFragment extends BravePreferenceFragment
        implements FragmentSettingsNavigation,
                BraveContentFilteringListener,
                BottomInsetViewProvider {
    private RecyclerView mRecyclerView;
''',
'''public class ContentFilteringFragment extends BravePreferenceFragment
        implements FragmentSettingsNavigation,
                BraveContentFilteringListener,
                BottomInsetViewProvider {
    private static final String FILTER_LIST_MIGRATION_PREFS = "sandium_filter_list_migration";
    private static final String FILTER_LIST_MIGRATION_KEY = "ubo_selected_lists_seeded_v1";
    private static final int MAX_FILTER_LIST_LOAD_ATTEMPTS = 20;
    private static final long FILTER_LIST_RETRY_DELAY_MS = 1000L;

    // Native Brave components cover the selected uBO AI, social, tracking-URL,
    // and Indian regional lists. Brave's default components cover uBO core
    // Ads/Privacy/Quick-fixes/Unbreak, EasyList, EasyPrivacy, URLhaus and the
    // default cookie-notice rules.
    private static final String[] SELECTED_UBO_BRAVE_FILTER_UUIDS = {
        "6b91e355-1421-4c03-9a30-911b4d0fb277", // AI suggestions / EasyList AI widgets.
        "7911A1CB-304E-4CDB-ABB3-E2A94A37E4DD", // Fanboy / EasyList social widgets.
        "E2FA7D98-0BD5-493E-8AF4-950604ADE9CB", // AdGuard URL tracking protection.
        "4C07DB6B-6377-4347-836D-68702CF1494A"  // IndianList.
    };

    // Selected uBO lists not already provided by Brave's default components
    // or corresponding native list switches. Use Brave's normal subscription
    // manager so lists are persisted, downloaded, toggleable and deletable.
    private static final String[] SELECTED_UBO_EXTRA_FILTER_URLS = {
        "https://filters.adtidy.org/extension/ublock/filters/2_without_easylist.txt", // AdGuard Ads.
        "https://filters.adtidy.org/extension/ublock/filters/11.txt", // AdGuard Mobile Ads.
        "https://malware-filter.gitlab.io/phishing-filter/phishing-filter.txt", // Phishing.
        "https://someonewhocares.org/hosts/hosts", // Dan Pollock hosts.
        "https://pgl.yoyo.org/adservers/serverlist.php?hostformat=hosts&showintro=1&mimetype=plaintext", // Peter Lowe.
        "https://filters.adtidy.org/extension/ublock/filters/18.txt", // AdGuard Cookie Notices.
        "https://filters.adtidy.org/extension/ublock/filters/4.txt", // AdGuard Social Widgets.
        "https://secure.fanboy.co.nz/fanboy-antifacebook.txt", // Fanboy Anti-Facebook.
        "https://ublockorigin.github.io/uAssets/thirdparties/easylist-annoyances.txt", // Other Annoyances.
        "https://ublockorigin.github.io/uAssets/thirdparties/easylist-chat.txt", // Chat Widgets.
        "https://ublockorigin.github.io/uAssets/thirdparties/easylist-newsletters.txt", // Newsletter Notices.
        "https://ublockorigin.github.io/uAssets/thirdparties/easylist-notifications.txt" // Notifications.
    };

    private final Handler mFilterListRetryHandler = new Handler(Looper.getMainLooper());
    private int mFilterListLoadAttempts;
    private boolean mFilterListRefreshRequested;
    private boolean mSelectedUBlockListsMigrationStarted;

    private RecyclerView mRecyclerView;
''',
                 "FILTER_LIST_MIGRATION_KEY", "selected-ubo-list-catalogue")

    replace_once(fragment,
'''    private void getSubscriptionFilters() {
        if (mFilterListAndroidHandler != null) {
            mFilterListAndroidHandler.getSubscriptions(
                    subscriptions -> {
                        mSubscriptionFilterLists = new ArrayList<>(Arrays.asList(subscriptions));
                        mAdapter.setSubscriptionFilterLists(mSubscriptionFilterLists);
                        mIsGetSubscriptionsLoaded = true;
                        if (mIsMenuLoaded) {
                            checkForEmptySubscriptionFilters(true);
                        }
                    });
        }
    }
''',
'''    private void getSubscriptionFilters() {
        if (mFilterListAndroidHandler != null) {
            mFilterListAndroidHandler.getSubscriptions(
                    subscriptions -> {
                        if (!isAdded() || mAdapter == null) return;
                        mSubscriptionFilterLists = new ArrayList<>(Arrays.asList(subscriptions));
                        mAdapter.setSubscriptionFilterLists(mSubscriptionFilterLists);
                        mIsGetSubscriptionsLoaded = true;
                        if (mIsMenuLoaded) {
                            checkForEmptySubscriptionFilters(true);
                        }
                        seedSelectedUBlockListsOnce();
                    });
        }
    }
''',
                 "seedSelectedUBlockListsOnce();", "subscription-list-refresh")

    replace_once(fragment,
'''    private void getFilterLists() {
        if (mFilterListAndroidHandler != null) {
            mFilterListAndroidHandler.getFilterLists(filterLists -> {
                mFilterLists = filterLists.storage;
                mAdapter.setFilterLists(mFilterLists);
            });
        }
    }
''',
'''    private void getFilterLists() {
        if (mFilterListAndroidHandler == null) return;
        mFilterListAndroidHandler.getFilterLists(filterLists -> {
            if (!isAdded() || mAdapter == null) return;
            mFilterLists = filterLists.storage;
            mAdapter.setFilterLists(mFilterLists);
            if (mFilterLists == null || mFilterLists.length == 0) {
                requestFilterListCatalogueRefresh();
                return;
            }
            mFilterListLoadAttempts = 0;
            seedSelectedUBlockListsOnce();
        });
    }

    private void requestFilterListCatalogueRefresh() {
        if (mFilterListRefreshRequested || mFilterListAndroidHandler == null) {
            scheduleFilterListRetry();
            return;
        }
        mFilterListRefreshRequested = true;
        // The native UPDATE action now requests Brave's catalogue even when no
        // regional providers have been created yet.
        mFilterListAndroidHandler.updateFilterLists(isSuccess -> {
            if (!isAdded()) return;
            if (!isSuccess) {
                Toast.makeText(getActivity(), getString(R.string.update_filter_list_fail_text),
                        Toast.LENGTH_SHORT).show();
            }
            scheduleFilterListRetry();
        });
    }

    private void scheduleFilterListRetry() {
        if (!isAdded() || mFilterListLoadAttempts >= MAX_FILTER_LIST_LOAD_ATTEMPTS) {
            if (isAdded()) {
                Toast.makeText(getActivity(), getString(R.string.update_filter_list_fail_text),
                        Toast.LENGTH_SHORT).show();
            }
            return;
        }
        mFilterListLoadAttempts++;
        mFilterListRetryHandler.removeCallbacksAndMessages(null);
        mFilterListRetryHandler.postDelayed(this::getFilterLists, FILTER_LIST_RETRY_DELAY_MS);
    }

    private void seedSelectedUBlockListsOnce() {
        if (mSelectedUBlockListsMigrationStarted
                || !mIsGetSubscriptionsLoaded
                || mSubscriptionFilterLists == null
                || mFilterLists == null
                || mFilterLists.length == 0
                || mFilterListAndroidHandler == null
                || !isAdded()) {
            return;
        }

        SharedPreferences preferences = requireContext().getSharedPreferences(
                FILTER_LIST_MIGRATION_PREFS, Context.MODE_PRIVATE);
        if (preferences.getBoolean(FILTER_LIST_MIGRATION_KEY, false)) return;
        mSelectedUBlockListsMigrationStarted = true;

        // Turn on the matching Brave-native components for selected uBO lists.
        for (String uuid : SELECTED_UBO_BRAVE_FILTER_UUIDS) {
            mFilterListAndroidHandler.enableFilter(uuid, true);
        }

        // Import only selected uBO lists not covered by Brave. Avoid duplicate
        // subscriptions and re-enable an existing matching subscription once.
        Set<String> existingUrls = new HashSet<>();
        for (SubscriptionInfo subscription : mSubscriptionFilterLists) {
            existingUrls.add(subscription.subscriptionUrl.url);
        }
        for (String url : SELECTED_UBO_EXTRA_FILTER_URLS) {
            if (existingUrls.contains(url)) {
                for (SubscriptionInfo subscription : mSubscriptionFilterLists) {
                    if (url.equals(subscription.subscriptionUrl.url) && !subscription.enabled) {
                        mFilterListAndroidHandler.enableSubscription(
                                subscription.subscriptionUrl, true);
                        subscription.enabled = true;
                    }
                }
                continue;
            }
            Url filterUrl = new Url();
            filterUrl.url = url;
            mFilterListAndroidHandler.createSubscription(filterUrl);
        }

        preferences.edit().putBoolean(FILTER_LIST_MIGRATION_KEY, true).apply();
        mFilterListRetryHandler.postDelayed(this::getSubscriptionFilters, 2000L);
    }
''',
                 "private void seedSelectedUBlockListsOnce()", "catalogue-retry-and-ubo-import")

    replace_once(fragment,
'''        } else if (item.getItemId() == R.id.update_filter_list_id) {
            if (mFilterListAndroidHandler != null) {
''',
'''        } else if (item.getItemId() == R.id.update_filter_list_id) {
            if (mFilterListAndroidHandler != null) {
                // SANDIUM_MANUAL_FILTER_LIST_UPDATE: avoid a duplicate auto-refresh.
                mFilterListRefreshRequested = true;
                mFilterListLoadAttempts = 0;
''',
                 "SANDIUM_MANUAL_FILTER_LIST_UPDATE", "manual-filter-list-update-retry")

    replace_once(fragment,
'''    @Override
    public void onDestroy() {
        if (mFilterListAndroidHandler != null) {
''',
'''    @Override
    public void onDestroy() {
        // SANDIUM_FILTER_LIST_HANDLER_CLEANUP: prevent delayed callbacks after teardown.
        mFilterListRetryHandler.removeCallbacksAndMessages(null);
        if (mFilterListAndroidHandler != null) {
''',
                 "SANDIUM_FILTER_LIST_HANDLER_CLEANUP", "filter-list-handler-cleanup")

    print("SANDIUM_ADBLOCK_PATCH_GATE=PASS catalogue_bootstrap=enabled android_retry=bounded selected_ubo_lists=migrated")

if __name__ == "__main__":
    main()
