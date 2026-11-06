#!/usr/bin/env python3
"""Seed the selected uBlock-compatible subscriptions into Brave's native Android UI.

The browser downloads these public ABP/uBO-compatible lists directly through
Brave's existing custom-subscription manager. No Brave component catalogue or
Brave Services key is used for these subscriptions.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

EXPECTED_CORE_TAG = "v1.98.62"
EXPECTED_CORE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"

DEFAULT_DISABLED_FILTER_URL = "https://ublockorigin.github.io/uAssets/filters/annoyances.txt"

FILTERS = (
    ("https://ublockorigin.github.io/uAssets/filters/filters.txt", "uBlock filters – Ads"),
    ("https://ublockorigin.github.io/uAssets/filters/privacy.txt", "uBlock filters – Privacy"),
    ("https://ublockorigin.github.io/uAssets/filters/quick-fixes.txt", "uBlock filters – Quick fixes"),
    ("https://ublockorigin.github.io/uAssets/filters/unbreak.txt", "uBlock filters – Unbreak"),
    ("https://ublockorigin.github.io/uAssets/thirdparties/easylist.txt", "EasyList"),
    ("https://filters.adtidy.org/extension/ublock/filters/2_without_easylist.txt", "AdGuard – Ads"),
    ("https://filters.adtidy.org/extension/ublock/filters/11.txt", "AdGuard – Mobile Ads"),
    ("https://ublockorigin.github.io/uAssets/thirdparties/easyprivacy.txt", "EasyPrivacy"),
    ("https://ublockorigin.github.io/uAssets/filters/privacy-removeparam.txt", "AdGuard/uBO – URL Tracking Protection"),
    ("https://malware-filter.gitlab.io/urlhaus-filter/urlhaus-filter-vivaldi-online.txt", "Online Malicious URL Blocklist"),
    ("https://malware-filter.gitlab.io/phishing-filter/phishing-filter.txt", "Phishing URL Blocklist"),
    ("https://pgl.yoyo.org/adservers/serverlist.php?hostformat=hosts&showintro=1&mimetype=plaintext", "Peter Lowe’s Ad and tracking server list"),
    ("https://someonewhocares.org/hosts/hosts", "Dan Pollock’s hosts file"),
    ("https://ublockorigin.github.io/uAssets/thirdparties/easylist-cookies.txt", "EasyList – Cookie Notices"),
    ("https://filters.adtidy.org/extension/ublock/filters/18.txt", "AdGuard – Cookie Notices"),
    ("https://ublockorigin.github.io/uAssets/filters/annoyances-cookies.txt", "uBlock filters – Cookie Notices"),
    ("https://ublockorigin.github.io/uAssets/thirdparties/easylist-social.txt", "EasyList – Social Widgets"),
    ("https://filters.adtidy.org/extension/ublock/filters/4.txt", "AdGuard – Social Widgets"),
    ("https://secure.fanboy.co.nz/fanboy-antifacebook.txt", "Fanboy – Anti-Facebook"),
    ("https://ublockorigin.github.io/uAssets/thirdparties/easylist-ai.txt", "EasyList – AI Widgets"),
    ("https://ublockorigin.github.io/uAssets/thirdparties/easylist-chat.txt", "EasyList – Chat Widgets"),
    ("https://ublockorigin.github.io/uAssets/thirdparties/easylist-newsletters.txt", "EasyList – Newsletter Notices"),
    ("https://ublockorigin.github.io/uAssets/thirdparties/easylist-notifications.txt", "EasyList – Notifications"),
    ("https://ublockorigin.github.io/uAssets/thirdparties/easylist-annoyances.txt", "EasyList – Other Annoyances"),
    ("https://filters.adtidy.org/extension/ublock/filters/20.txt", "AdGuard – Mobile App Banners"),
    ("https://filters.adtidy.org/extension/ublock/filters/21.txt", "AdGuard – Other Annoyances"),
    ("https://filters.adtidy.org/extension/ublock/filters/19.txt", "AdGuard – Popup Overlays"),
    ("https://filters.adtidy.org/extension/ublock/filters/22.txt", "AdGuard – Widgets"),
    ("https://ublockorigin.github.io/uAssets/filters/annoyances.txt", "uBlock filters – Annoyances"),
    ("https://easylist-downloads.adblockplus.org/indianlist.txt", "🇮🇳in 🇱🇰lk 🇳🇵np: IndianList"),
)

# The earlier Sandium updater/catalogue patch can be present inside a restored
# workspace checkpoint. Restore only its known Brave Core source files to the
# pinned commit before applying the independent URL-subscription integration.
LEGACY_COMPONENT_PATCH_PATHS = (
    "components/brave_component_updater/browser/brave_on_demand_updater.h",
    "components/brave_shields/core/browser/ad_block_component_service_manager.cc",
    "browser/brave_browser_main_parts.cc",
    "app/brave_main_delegate.cc",
    "components/brave_component_updater/browser/brave_component_updater_delegate.cc",
    "components/brave_shields/core/browser/ad_block_component_installer.cc",
    "components/brave_shields/core/browser/ad_block_filter_list_catalog_provider.cc",
    "components/brave_shields/core/browser/ad_block_component_filters_provider.cc",
    "components/brave_shields/content/browser/filter_list_service.cc",
    "android/java/org/chromium/chrome/browser/shields/ContentFilteringFragment.java",
    "android/java/org/chromium/chrome/browser/shields/ContentFilteringAdapter.java",
)


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> None:
    if not path.is_file():
        raise SystemExit(f"SANDIUM_FILTER_SUBSCRIPTIONS=FAIL missing {path}")
    source = path.read_text(encoding="utf-8")
    if marker in source:
        if new not in source:
            raise SystemExit(f"SANDIUM_FILTER_SUBSCRIPTIONS=FAIL incomplete patch {label}")
        print(f"SANDIUM_FILTER_SUBSCRIPTIONS_PATCH={label}:ALREADY_APPLIED")
        return
    count = source.count(old)
    if count != 1:
        raise SystemExit(
            f"SANDIUM_FILTER_SUBSCRIPTIONS=FAIL {label}: expected one anchor, found {count}"
        )
    updated = source.replace(old, new, 1)
    if marker not in updated:
        raise SystemExit(f"SANDIUM_FILTER_SUBSCRIPTIONS=FAIL {label}: marker missing after patch")
    path.write_text(updated, encoding="utf-8")
    print(f"SANDIUM_FILTER_SUBSCRIPTIONS_PATCH={label}:APPLIED")


def verify_pin(core: Path) -> None:
    tag = subprocess.run(
        ["git", "-C", str(core), "describe", "--tags", "--exact-match"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    sha = subprocess.run(
        ["git", "-C", str(core), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if tag != EXPECTED_CORE_TAG or sha != EXPECTED_CORE_SHA:
        raise SystemExit(
            "SANDIUM_FILTER_SUBSCRIPTIONS_PIN=FAIL "
            f"expected={EXPECTED_CORE_TAG}@{EXPECTED_CORE_SHA} actual={tag}@{sha}"
        )
    print(f"SANDIUM_FILTER_SUBSCRIPTIONS_PIN=PASS {tag}@{sha}")


def restore_legacy_component_patches(core: Path) -> None:
    subprocess.run(
        [
            "git", "-C", str(core), "restore", "--source=HEAD",
            "--staged", "--worktree", "--", *LEGACY_COMPONENT_PATCH_PATHS,
        ],
        check=True,
    )
    status = subprocess.run(
        ["git", "-C", str(core), "status", "--porcelain", "--", *LEGACY_COMPONENT_PATCH_PATHS],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if status:
        raise SystemExit(
            "SANDIUM_FILTER_SUBSCRIPTIONS_RESET=FAIL legacy Brave component patches remain: "
            + status
        )
    print(
        "SANDIUM_FILTER_SUBSCRIPTIONS_RESET=PASS "
        "Brave component-catalogue/updater overrides removed from restored source"
    )


def apply_android_sources(core: Path) -> None:
    fragment = core / "android/java/org/chromium/chrome/browser/shields/ContentFilteringFragment.java"
    adapter = core / "android/java/org/chromium/chrome/browser/shields/ContentFilteringAdapter.java"

    replace_once(
        fragment,
        "import android.content.Context;\nimport android.content.Intent;\nimport android.os.Bundle;\n",
        "import android.content.Context;\nimport android.content.Intent;\n"
        "import android.content.SharedPreferences;\nimport android.os.Bundle;\n",
        "import android.content.SharedPreferences;",
        "fragment-shared-preferences-import",
    )
    replace_once(
        fragment,
        "import android.os.Bundle;\n",
        "import android.os.Bundle;\nimport android.util.Log;\n",
        "import android.util.Log;",
        "fragment-logging-import",
    )
    replace_once(
        fragment,
        "import org.chromium.mojo_base.mojom.Value;\n",
        "import org.chromium.mojo_base.mojom.Value;\n"
        "import org.chromium.url.mojom.Url;\n",
        "import org.chromium.url.mojom.Url;",
        "fragment-subscription-url-import",
    )
    replace_once(
        fragment,
        "import java.util.ArrayList;\nimport java.util.Arrays;\n",
        "import java.util.ArrayList;\nimport java.util.Arrays;\n"
        "import java.util.HashSet;\nimport java.util.Set;\n",
        "import java.util.HashSet;",
        "fragment-subscription-set-imports",
    )

    java_entries = "\n".join(
        f'        {{ "{url}", "{title}" }},' for url, title in FILTERS
    )
    constants = (
        '    private static final String FILTER_SUBSCRIPTION_PREFS = '
        '"sandium_filter_subscriptions";\n'
        '    private static final String SEEDED_URLS_PREF = "seeded_urls_v1";\n'
        '    private static final String DEFAULT_DISABLED_FILTER_URL = "' + DEFAULT_DISABLED_FILTER_URL + '";\n'
        '    private static final String DEFAULT_DISABLED_FILTER_PREF = "default_disabled_u_block_annoyances_v1";\n'
        '    private static final String[][] SANDIUM_DEFAULT_FILTERS = {\n'
        + java_entries
        + '\n    };\n\n'
        + '    static String getSandiumFilterDisplayName(String subscriptionUrl) {\n'
        + '        for (String[] filter : SANDIUM_DEFAULT_FILTERS) {\n'
        + '            if (filter[0].equals(subscriptionUrl)) return filter[1];\n'
        + '        }\n'
        + '        return null;\n'
        + '    }\n\n'
    )
    replace_once(
        fragment,
        "                BottomInsetViewProvider {\n    private RecyclerView mRecyclerView;\n",
        "                BottomInsetViewProvider {\n" + constants
        + "    private RecyclerView mRecyclerView;\n",
        "SANDIUM_DEFAULT_FILTERS",
        "fragment-default-list-catalogue",
    )

    replace_once(
        fragment,
        "        getSubscriptionFilters();\n        getFilterLists();\n",
        "        ensureSandiumDefaultSubscriptions();\n        getFilterLists();\n",
        "ensureSandiumDefaultSubscriptions();",
        "fragment-seed-default-subscriptions",
    )

    subscription_method = """    // Seed each selected list once. The persisted URL set deliberately prevents
    // a user-deleted list from silently reappearing on the next visit. New URLs
    // introduced by a later Sandium release are seeded without re-enabling
    // existing subscriptions whose toggle the user has turned off.
    private void ensureSandiumDefaultSubscriptions() {
        if (mFilterListAndroidHandler == null) {
            getSubscriptionFilters();
            return;
        }
        mFilterListAndroidHandler.getSubscriptions(subscriptions -> {
            if (!isAdded() || mFilterListAndroidHandler == null) return;
            Set<String> existingUrls = new HashSet<>();
            if (subscriptions != null) {
                for (SubscriptionInfo subscription : subscriptions) {
                    if (subscription != null && subscription.subscriptionUrl != null
                            && subscription.subscriptionUrl.url != null) {
                        existingUrls.add(subscription.subscriptionUrl.url);
                    }
                }
            }

            SharedPreferences preferences = requireContext().getSharedPreferences(
                    FILTER_SUBSCRIPTION_PREFS, Context.MODE_PRIVATE);
            Set<String> seededUrls = new HashSet<>(
                    preferences.getStringSet(SEEDED_URLS_PREF, new HashSet<>()));
            boolean preferencesChanged = false;
            boolean defaultDisabledFilterMigrated = preferences.getBoolean(
                    DEFAULT_DISABLED_FILTER_PREF, false);
            int createdCount = 0;

            for (String[] filter : SANDIUM_DEFAULT_FILTERS) {
                String url = filter[0];
                if (existingUrls.contains(url)) {
                    // Adopt existing subscriptions without changing user choices,
                    // except for the one-time default-off migration requested for
                    // uBlock filters – Annoyances.
                    preferencesChanged |= seededUrls.add(url);
                    if (DEFAULT_DISABLED_FILTER_URL.equals(url)
                            && !defaultDisabledFilterMigrated) {
                        Url subscriptionUrl = new Url();
                        subscriptionUrl.url = url;
                        mFilterListAndroidHandler.enableSubscription(subscriptionUrl, false);
                        preferences.edit().putBoolean(
                                DEFAULT_DISABLED_FILTER_PREF, true).apply();
                        defaultDisabledFilterMigrated = true;
                    }
                    continue;
                }
                if (seededUrls.add(url)) {
                    Url subscriptionUrl = new Url();
                    subscriptionUrl.url = url;
                    mFilterListAndroidHandler.createSubscription(subscriptionUrl);
                    if (DEFAULT_DISABLED_FILTER_URL.equals(url)
                            && !defaultDisabledFilterMigrated) {
                        // Mojo preserves call order on this handler: create first,
                        // then immediately set this one new subscription disabled.
                        mFilterListAndroidHandler.enableSubscription(subscriptionUrl, false);
                        preferences.edit().putBoolean(
                                DEFAULT_DISABLED_FILTER_PREF, true).apply();
                        defaultDisabledFilterMigrated = true;
                    }
                    existingUrls.add(url);
                    createdCount++;
                    preferencesChanged = true;
                }
            }

            if (preferencesChanged) {
                preferences.edit().putStringSet(
                        SEEDED_URLS_PREF, new HashSet<>(seededUrls)).apply();
            }
            Log.i("SandiumFilterLists", "SANDIUM_FILTER_SUBSCRIPTIONS_SEED total="
                    + SANDIUM_DEFAULT_FILTERS.length + " created=" + createdCount);
            // Mojo preserves message order: this read follows all queued
            // CreateSubscription calls and fills the Android list with the
            // persisted subscriptions and their current update status.
            getSubscriptionFilters();
        });
    }

"""
    replace_once(
        fragment,
        "    private void getSubscriptionFilters() {\n",
        subscription_method + "    private void getSubscriptionFilters() {\n",
        "SANDIUM_FILTER_SUBSCRIPTIONS_SEED",
        "fragment-seed-subscription-method",
    )

    old_filter_lists = """    private void getFilterLists() {
        if (mFilterListAndroidHandler != null) {
            mFilterListAndroidHandler.getFilterLists(filterLists -> {
                mFilterLists = filterLists.storage;
                mAdapter.setFilterLists(mFilterLists);
            });
        }
    }
"""
    new_filter_lists = """    private void getFilterLists() {
        // SANDIUM_FILTER_SUBSCRIPTIONS_ONLY: selected lists are ordinary
        // user-managed URL subscriptions. Do not load Brave's component
        // catalogue or couple the filter screen to Brave's private updater.
        mFilterLists = new Value[0];
        mAdapter.setFilterLists(mFilterLists);
    }
"""
    replace_once(
        fragment, old_filter_lists, new_filter_lists,
        "SANDIUM_FILTER_SUBSCRIPTIONS_ONLY",
        "fragment-disable-brave-component-list-catalogue",
    )

    replace_once(
        fragment,
        "        mUpdateFilterListItem = menu.findItem(R.id.update_filter_list_id);\n",
        "        mUpdateFilterListItem = menu.findItem(R.id.update_filter_list_id);\n"
        "        // The upstream action refreshes Brave component lists, not URL subscriptions.\n"
        "        if (mUpdateFilterListItem != null) mUpdateFilterListItem.setVisible(false);\n",
        "The upstream action refreshes Brave component lists",
        "fragment-hide-brave-catalogue-update-action",
    )

    old_update_action = """        } else if (item.getItemId() == R.id.update_filter_list_id) {
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
"""
    new_update_action = """        } else if (item.getItemId() == R.id.update_filter_list_id) {
            Toast.makeText(
                    getActivity(),
                    "Active Sandium filter subscriptions update automatically in the background.",
                    Toast.LENGTH_LONG).show();
            return true;
"""
    replace_once(
        fragment, old_update_action, new_update_action,
        "Active Sandium filter subscriptions update automatically",
        "fragment-stop-component-catalogue-refresh",
    )
    replace_once(
        fragment,
        "        mUpdateFilterListItem.setVisible(!isEditable);\n",
        "        // Component-catalogue refresh is intentionally hidden; active URL subscriptions auto-update.\n"
        "        if (mUpdateFilterListItem != null) mUpdateFilterListItem.setVisible(false);\n",
        "Component-catalogue refresh is intentionally hidden",
        "fragment-keep-component-update-hidden",
    )

    # Initialize both adapter collections before the first RecyclerView layout.
    replace_once(
        adapter,
        """        mContext = context;
        mBraveContentFileringListener = braveContentFileringListener;
""",
        """        mContext = context;
        mSubscriptionFilterLists = new ArrayList<>();
        mFilterLists = new Value[0];
        mBraveContentFileringListener = braveContentFileringListener;
""",
        "mSubscriptionFilterLists = new ArrayList<>();",
        "adapter-safe-empty-initial-state",
    )

    replace_once(
        adapter,
        """                String url = customFilter.subscriptionUrl.url;
                if (customFilter.title != null && customFilter.title.length() > 0) {
""",
        """                String url = customFilter.subscriptionUrl.url;
                String sandiumTitle =
                        ContentFilteringFragment.getSandiumFilterDisplayName(url);
                if (sandiumTitle != null) {
                    // Display the curated name immediately, even before the
                    // first successful download has supplied list metadata.
                    customFilterListViewHolder.mTitleText.setText(sandiumTitle);
                    customFilterListViewHolder.mTitleText.setVisibility(View.VISIBLE);
                } else if (customFilter.title != null && customFilter.title.length() > 0) {
""",
        "ContentFilteringFragment.getSandiumFilterDisplayName(url)",
        "adapter-friendly-sandium-list-titles",
    )

    replace_once(
        adapter,
        """    public int getItemCount() {
        int count = mSubscriptionFilterLists.size() + FOUR_ITEMS_SPACE;
        if (mFilterLists != null) {
            count += mFilterLists.length;
        }
        return count;
    }
""",
        """    public int getItemCount() {
        int subscriptionCount =
                mSubscriptionFilterLists == null ? 0 : mSubscriptionFilterLists.size();
        int count = subscriptionCount + THREE_ITEMS_SPACE;
        if (mFilterLists != null && mFilterLists.length > 0) {
            // Add the separate Brave catalogue heading only when that catalogue
            // is actually enabled by a different build configuration.
            count += ONE_ITEM_SPACE + mFilterLists.length;
        }
        return count;
    }
""",
        "int count = subscriptionCount + THREE_ITEMS_SPACE;",
        "adapter-hide-empty-brave-catalogue-section",
    )

    replace_once(
        adapter,
        """    public int getItemViewType(int position) {
        if (position == 0 || position == mSubscriptionFilterLists.size() + THREE_ITEMS_SPACE) {
            return TYPE_FILTER_HEADER;
        } else if (position > 0 && position <= mSubscriptionFilterLists.size() + TWO_ITEMS_SPACE) {
            return TYPE_CUSTOM_FILTER_LIST;
        } else {
            return TYPE_FILTER_LIST;
        }
    }
""",
        """    public int getItemViewType(int position) {
        int subscriptionCount =
                mSubscriptionFilterLists == null ? 0 : mSubscriptionFilterLists.size();
        boolean hasBraveCatalogue = mFilterLists != null && mFilterLists.length > 0;
        if (position == 0
                || (hasBraveCatalogue
                        && position == subscriptionCount + THREE_ITEMS_SPACE)) {
            return TYPE_FILTER_HEADER;
        } else if (position > 0 && position <= subscriptionCount + TWO_ITEMS_SPACE) {
            return TYPE_CUSTOM_FILTER_LIST;
        } else {
            return TYPE_FILTER_LIST;
        }
    }
""",
        "boolean hasBraveCatalogue = mFilterLists != null && mFilterLists.length > 0;",
        "adapter-hide-empty-brave-catalogue-viewtype",
    )

    replace_once(
        adapter,
        """    public void setFilterLists(Value filterLists[]) {
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
""",
        """    public void setFilterLists(Value filterLists[]) {
        mFilterLists = filterLists == null ? new Value[0] : filterLists;
        notifyDataSetChanged();
    }
""",
        "mFilterLists = filterLists == null ? new Value[0] : filterLists;",
        "adapter-filter-list-safe-refresh",
    )


def verify_android_sources(core: Path) -> None:
    fragment = (core / "android/java/org/chromium/chrome/browser/shields/ContentFilteringFragment.java").read_text(encoding="utf-8")
    adapter = (core / "android/java/org/chromium/chrome/browser/shields/ContentFilteringAdapter.java").read_text(encoding="utf-8")
    required_fragment_markers = (
        'private static final String[][] SANDIUM_DEFAULT_FILTERS',
        'static String getSandiumFilterDisplayName(String subscriptionUrl)',
        'private void ensureSandiumDefaultSubscriptions()',
        'for (String[] filter : SANDIUM_DEFAULT_FILTERS)',
        'createSubscription(subscriptionUrl)',
    )
    missing_fragment_markers = [
        marker for marker in required_fragment_markers if marker not in fragment
    ]
    if missing_fragment_markers:
        raise SystemExit(
            "SANDIUM_FILTER_SUBSCRIPTIONS_VERIFY=FAIL missing Android filter integration markers: "
            + ", ".join(missing_fragment_markers)
        )
    if fragment.count("createSubscription(subscriptionUrl)") != 1:
        raise SystemExit("SANDIUM_FILTER_SUBSCRIPTIONS_VERIFY=FAIL subscription seeding call missing")
    if "getFilterLists(filterLists" in fragment or "mFilterListAndroidHandler.updateFilterLists(" in fragment:
        raise SystemExit("SANDIUM_FILTER_SUBSCRIPTIONS_VERIFY=FAIL Brave component filter catalogue still used")
    if "getSandiumFilterDisplayName(url)" not in adapter:
        raise SystemExit("SANDIUM_FILTER_SUBSCRIPTIONS_VERIFY=FAIL friendly names are not rendered")
    if len(FILTERS) != 30 or len({url for url, _ in FILTERS}) != 30:
        raise SystemExit("SANDIUM_FILTER_SUBSCRIPTIONS_VERIFY=FAIL expected 30 unique selected list URLs")
    if DEFAULT_DISABLED_FILTER_URL not in {url for url, _ in FILTERS}:
        raise SystemExit("SANDIUM_FILTER_SUBSCRIPTIONS_VERIFY=FAIL default-disabled list is not in catalogue")
    if fragment.count("mFilterListAndroidHandler.enableSubscription(subscriptionUrl, false)") != 2:
        raise SystemExit("SANDIUM_FILTER_SUBSCRIPTIONS_VERIFY=FAIL expected only the one-time default-off migration paths")
    if "DEFAULT_DISABLED_FILTER_PREF" not in fragment or "defaultDisabledFilterMigrated" not in fragment:
        raise SystemExit("SANDIUM_FILTER_SUBSCRIPTIONS_VERIFY=FAIL one-time default-off migration is missing")
    print(
        "SANDIUM_FILTER_SUBSCRIPTIONS_VERIFY=PASS "
        f"lists={len(FILTERS)} auto_update=native_subscription_manager "
        "brave_component_catalogue=not_used titles=visible toggles=preserved"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", required=True, type=Path)
    args = parser.parse_args()
    core = args.core.resolve()
    if not core.is_dir():
        raise SystemExit(f"SANDIUM_FILTER_SUBSCRIPTIONS=FAIL missing core directory {core}")
    verify_pin(core)
    restore_legacy_component_patches(core)
    apply_android_sources(core)
    verify_android_sources(core)


if __name__ == "__main__":
    main()
