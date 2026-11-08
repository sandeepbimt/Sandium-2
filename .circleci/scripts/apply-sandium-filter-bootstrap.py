#!/usr/bin/env python3
"""Apply Sandium's native first-launch filter bootstrap, refresh action and cache metadata."""
from __future__ import annotations

import argparse
import runpy
import subprocess
from pathlib import Path

EXPECTED_CORE_TAG = "v1.98.62"
EXPECTED_CORE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
FILTER_SCRIPT = Path(__file__).with_name("apply-sandium-filter-subscriptions.py")
FILTERS = runpy.run_path(str(FILTER_SCRIPT))["FILTERS"]


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> None:
    if not path.is_file():
        raise SystemExit(f"SANDIUM_FILTER_BOOTSTRAP=FAIL missing {path}")
    source = path.read_text(encoding="utf-8")
    if marker in source:
        if new not in source:
            raise SystemExit(f"SANDIUM_FILTER_BOOTSTRAP=FAIL incomplete patch {label}")
        print(f"SANDIUM_FILTER_BOOTSTRAP_PATCH={label}:ALREADY_APPLIED")
        return
    count = source.count(old)
    if count != 1:
        raise SystemExit(f"SANDIUM_FILTER_BOOTSTRAP=FAIL {label}: expected one anchor, found {count}")
    updated = source.replace(old, new, 1)
    if marker not in updated:
        raise SystemExit(f"SANDIUM_FILTER_BOOTSTRAP=FAIL {label}: marker missing")
    path.write_text(updated, encoding="utf-8")
    print(f"SANDIUM_FILTER_BOOTSTRAP_PATCH={label}:APPLIED")


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
            f"SANDIUM_FILTER_BOOTSTRAP_PIN=FAIL expected={EXPECTED_CORE_TAG}@{EXPECTED_CORE_SHA} "
            f"actual={tag}@{sha}"
        )
    print(f"SANDIUM_FILTER_BOOTSTRAP_PIN=PASS {tag}@{sha}")


def apply(core: Path) -> None:
    manager_h = core / "components/brave_shields/content/browser/ad_block_subscription_service_manager.h"
    manager_cc = core / "components/brave_shields/content/browser/ad_block_subscription_service_manager.cc"
    service_h = core / "components/brave_shields/content/browser/filter_list_service.h"
    service_cc = core / "components/brave_shields/content/browser/filter_list_service.cc"
    mojom = core / "components/brave_shields/core/common/filter_list.mojom"
    prefs_h = core / "components/brave_shields/core/common/pref_names.h"
    adblock_service = core / "components/brave_shields/content/browser/ad_block_service.cc"
    adapter = core / "android/java/org/chromium/chrome/browser/shields/ContentFilteringAdapter.java"
    fragment = core / "android/java/org/chromium/chrome/browser/shields/ContentFilteringFragment.java"
    menu = core / "android/java/brave-res/menu/menu_custom_filter_list.xml"

    # Startup seed runs when the profile's ad-block service manager is initialized.
    replace_once(
        manager_h,
        "  void StartDownload(const GURL& sub_url, bool from_ui);\n",
        "  void StartDownload(const GURL& sub_url, bool from_ui);\n"
        "  void EnsureSandiumDefaultSubscriptions();\n",
        "void EnsureSandiumDefaultSubscriptions();",
        "manager-startup-seed-declaration",
    )

    cpp_entries = "\n".join(f'    "{url}",' for url, _ in FILTERS)
    url_catalogue = (
        "constexpr const char* kSandiumDefaultFilterUrls[] = {\n"
        + cpp_entries
        + "\n};\n\n"
        "constexpr const char* kSandiumPreviouslyDisabledFilterUrls[] = {\n"
        "    \"https://filters.adtidy.org/extension/ublock/filters/20.txt\",\n"
        "    \"https://filters.adtidy.org/extension/ublock/filters/21.txt\",\n"
        "    \"https://filters.adtidy.org/extension/ublock/filters/19.txt\",\n"
        "    \"https://filters.adtidy.org/extension/ublock/filters/22.txt\",\n"
        "    \"https://ublockorigin.github.io/uAssets/filters/annoyances.txt\",\n"
        "};\n\n"
    )
    replace_once(
        manager_cc,
        """void AdBlockSubscriptionServiceManager::DeleteSubscription(
    const GURL& sub_url) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  auto it = subscription_filters_providers_.find(sub_url);""",
        """void AdBlockSubscriptionServiceManager::DeleteSubscription(
    const GURL& sub_url) {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  if (local_state_) {
    base::ListValue seeded_urls =
        local_state_->GetList(prefs::kSandiumDefaultFilterListsSeeded).Clone();
    bool already_seeded = false;
    for (const base::Value& seeded_url : seeded_urls) {
      if (seeded_url.is_string() && seeded_url.GetString() == sub_url.spec()) {
        already_seeded = true;
        break;
      }
    }
    if (!already_seeded) {
      seeded_urls.Append(sub_url.spec());
      local_state_->SetList(
          prefs::kSandiumDefaultFilterListsSeeded, std::move(seeded_urls));
    }
  }
  auto it = subscription_filters_providers_.find(sub_url);""",
        "local_state_->GetList(prefs::kSandiumDefaultFilterListsSeeded).Clone()",
        "manager-record-user-deleted-subscriptions",
    )
    replace_once(
        manager_cc,
        "namespace {\n\nconstexpr uint16_t kSubscriptionMaxExpiresHours = 14 * 24;\n",
        "namespace {\n\n" + url_catalogue
        + "constexpr uint16_t kSubscriptionMaxExpiresHours = 14 * 24;\n",
        "kSandiumDefaultFilterUrls",
        "manager-default-url-catalogue",
    )
    replace_once(
        manager_cc,
        "  LoadSubscriptionServices();\n\n  subscription_update_timer_->Schedule(\n",
        "  LoadSubscriptionServices();\n"
        "  EnsureSandiumDefaultSubscriptions();\n\n"
        "  subscription_update_timer_->Schedule(\n",
        "EnsureSandiumDefaultSubscriptions();",
        "manager-seed-at-profile-startup",
    )
    migration_method = """void AdBlockSubscriptionServiceManager::EnsureSandiumDefaultSubscriptions() {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  if (!local_state_) {
    return;
  }

  const bool migrate_previous_defaults =
      !local_state_->GetBoolean(prefs::kSandiumDefaultFilterListsMigrated);
  base::ListValue seeded_urls =
      local_state_->GetList(prefs::kSandiumDefaultFilterListsSeeded).Clone();
  bool seeded_urls_changed = false;

  for (const char* url : kSandiumDefaultFilterUrls) {
    const GURL subscription_url(url);
    bool was_seeded = false;
    for (const base::Value& seeded_url : seeded_urls) {
      if (seeded_url.is_string() && seeded_url.GetString() == url) {
        was_seeded = true;
        break;
      }
    }

    auto info = GetInfo(subscription_url);
    if (!info) {
      // A prior user deletion is recorded in seeded_urls and must remain deleted.
      if (was_seeded) {
        continue;
      }
      CreateSubscription(subscription_url);
      seeded_urls.Append(url);
      seeded_urls_changed = true;
      continue;
    }

    if (!was_seeded) {
      seeded_urls.Append(url);
      seeded_urls_changed = true;
    }

    if (migrate_previous_defaults) {
      for (const char* previously_disabled :
           kSandiumPreviouslyDisabledFilterUrls) {
        if (subscription_url.spec() == previously_disabled && !info->enabled) {
          EnableSubscription(subscription_url, true);
          break;
        }
      }
    }

    const base::FilePath cached_list =
        GetSubscriptionPath(subscription_url).Append(kCustomSubscriptionListText);
    const std::optional<int64_t> cached_size = base::GetFileSize(cached_list);
    if (info->enabled && (!cached_size || *cached_size <= 0)) {
      StartDownload(subscription_url, true);
    }
  }

  if (seeded_urls_changed) {
    local_state_->SetList(
        prefs::kSandiumDefaultFilterListsSeeded, std::move(seeded_urls));
  }
  if (migrate_previous_defaults) {
    local_state_->SetBoolean(prefs::kSandiumDefaultFilterListsMigrated, true);
  }
}

"""
    replace_once(
        manager_cc,
        "// Updates preferences to reflect a new state for the specified filter list\n",
        migration_method + "// Updates preferences to reflect a new state for the specified filter list\n",
        "EnsureSandiumDefaultSubscriptions() {",
        "manager-first-launch-high-priority-downloads",
    )

    replace_once(
        prefs_h,
        "inline constexpr char kAdBlockListSubscriptions[] =\n"
        "    \"brave.ad_block.list_subscriptions\";\n",
        "inline constexpr char kAdBlockListSubscriptions[] =\n"
        "    \"brave.ad_block.list_subscriptions\";\n"
        "inline constexpr char kSandiumDefaultFilterListsMigrated[] =\n"
        "    \"sandium.ad_block.default_filter_lists_migrated\";\n"
        "inline constexpr char kSandiumDefaultFilterListsSeeded[] =\n"
        "    \"sandium.ad_block.default_filter_lists_seeded\";\n",
        "kSandiumDefaultFilterListsSeeded",
        "register-default-state-pref-name",
    )
    replace_once(
        adblock_service,
        "  registry->RegisterDictionaryPref(prefs::kAdBlockListSubscriptions);\n",
        "  registry->RegisterDictionaryPref(prefs::kAdBlockListSubscriptions);\n"
        "  registry->RegisterBooleanPref(prefs::kSandiumDefaultFilterListsMigrated, false);\n"
        "  registry->RegisterListPref(prefs::kSandiumDefaultFilterListsSeeded);\n",
        "kSandiumDefaultFilterListsSeeded",
        "register-default-state-pref",
    )

    # Native Mojo refresh API; do not call Brave's component-catalogue updater.
    replace_once(
        mojom,
        "  uint16 expires;\n",
        "  uint16 expires;\n"
        "  uint32 rule_count;\n"
        "  uint64 size_bytes;\n",
        "uint32 rule_count;",
        "mojom-cache-rule-and-size-metadata",
    )
    replace_once(
        mojom,
        "  DeleteSubscription(url.mojom.Url sub_url);\n",
        "  DeleteSubscription(url.mojom.Url sub_url);\n"
        "  RefreshAllSubscriptions() => (uint32 requested_count);\n",
        "RefreshAllSubscriptions()",
        "mojom-refresh-all-enabled-subscriptions",
    )
    replace_once(
        service_h,
        "  void DeleteSubscription(const GURL& sub_url) override;\n",
        "  void DeleteSubscription(const GURL& sub_url) override;\n"
        "  void RefreshAllSubscriptions(RefreshAllSubscriptionsCallback callback) override;\n",
        "void RefreshAllSubscriptions(",
        "filter-service-header-refresh-api",
    )

    replace_once(
        service_cc,
        "#include <utility>\n",
        "#include <sstream>\n"
        "#include <string>\n"
        "#include <utility>\n"
        "\n#include \"base/files/file_util.h\"\n"
        "#include \"net/base/filename_util.h\"\n",
        "#include <sstream>",
        "filter-service-metadata-includes",
    )
    helper = """namespace {

uint32_t CountFilterSourceRules(const std::string& contents) {
  std::istringstream input(contents);
  std::string line;
  uint32_t count = 0;
  while (std::getline(input, line)) {
    const size_t first = line.find_first_not_of(" \\t\\r");
    if (first == std::string::npos || line[first] == '!' || line[first] == '[') {
      continue;
    }
    // A leading single '#' is a hosts-file comment; '##' is a valid
    // universal cosmetic filter and remains counted as a rule entry.
    if (line[first] == '#' &&
        (first + 1 >= line.size() || line[first + 1] != '#')) {
      continue;
    }
    ++count;
  }
  return count;
}

}  // namespace

"""
    replace_once(
        service_cc,
        "namespace brave_shields {\n\nFilterListService::FilterListService",
        "namespace brave_shields {\n\n" + helper + "FilterListService::FilterListService",
        "CountFilterSourceRules",
        "filter-service-count-source-rules",
    )
    replace_once(
        service_cc,
        "    info->expires = subscription.expires;\n    items.push_back(std::move(info));",
        """    info->expires = subscription.expires;
    base::FilePath cached_list_path;
    std::string cached_list_contents;
    if (net::FileURLToFilePath(
            ad_block_service_->subscription_service_manager()->GetListTextFileUrl(
                subscription.subscription_url),
            &cached_list_path) &&
        base::ReadFileToString(cached_list_path, &cached_list_contents)) {
      info->size_bytes = static_cast<uint64_t>(cached_list_contents.size());
      info->rule_count = CountFilterSourceRules(cached_list_contents);
    }
    items.push_back(std::move(info));""",
        "info->rule_count = CountFilterSourceRules",
        "filter-service-expose-cache-metadata",
    )
    replace_once(
        service_cc,
        """void FilterListService::DeleteSubscription(const GURL& sub_url) {
  ad_block_service_->subscription_service_manager()->DeleteSubscription(
      sub_url);
}

void FilterListService::GetCustomFilters""",
        """void FilterListService::DeleteSubscription(const GURL& sub_url) {
  ad_block_service_->subscription_service_manager()->DeleteSubscription(sub_url);
}

void FilterListService::RefreshAllSubscriptions(
    RefreshAllSubscriptionsCallback callback) {
  auto* manager = ad_block_service_->subscription_service_manager();
  uint32_t requested_count = 0;
  for (const auto& subscription : manager->GetSubscriptions()) {
    if (!subscription.enabled) {
      continue;
    }
    manager->RefreshSubscription(subscription.subscription_url, true);
    ++requested_count;
  }
  std::move(callback).Run(requested_count);
}

void FilterListService::GetCustomFilters""",
        "void FilterListService::RefreshAllSubscriptions(",
        "filter-service-refresh-active-lists",
    )

    # The Content Filters page action now refreshes URL subscriptions.
    replace_once(
        fragment,
        "            // SANDIUM_FILTER_REFRESH_PLACEHOLDER\n",
        """            if (mFilterListAndroidHandler != null) {
                mFilterListAndroidHandler.refreshAllSubscriptions(count -> {
                    if (!isAdded()) return;
                    getSubscriptionFilters();
                    String message =
                            "Refresh requested for " + count + " enabled filter lists";
                    Toast.makeText(getActivity(), message, Toast.LENGTH_SHORT).show();
                });
            }
""",
        "mFilterListAndroidHandler.refreshAllSubscriptions(",
        "fragment-refresh-enabled-filter-sources",
    )
    replace_once(
        menu,
        'android:title="@string/update"',
        'android:title="Refresh filters"',
        'android:title="Refresh filters"',
        "menu-refresh-filters-title",
    )

    replace_once(
        adapter,
        "import java.util.Map;\n",
        "import java.util.Locale;\nimport java.util.Map;\n",
        "import java.util.Locale;",
        "adapter-locale-import",
    )
    replace_once(
        adapter,
        "                customFilterListViewHolder.mUrlText.setText(url);\n",
        """                String updateStatus =
                        customFilterListViewHolder.mLastUpdateText.getText().toString();
                String cacheSummary = String.format(
                        Locale.getDefault(),
                        "%,d rules · %.2f MB · %s",
                        customFilter.ruleCount,
                        customFilter.sizeBytes / (1024.0 * 1024.0),
                        updateStatus);
                customFilterListViewHolder.mLastUpdateText.setText(cacheSummary);
                customFilterListViewHolder.mLastUpdateText.setVisibility(View.VISIBLE);
                customFilterListViewHolder.mUrlText.setText(url);
""",
        "customFilter.ruleCount",
        "adapter-show-update-rule-count-size",
    )


def verify(core: Path) -> None:
    manager = (core / "components/brave_shields/content/browser/ad_block_subscription_service_manager.cc").read_text(encoding="utf-8")
    service = (core / "components/brave_shields/content/browser/filter_list_service.cc").read_text(encoding="utf-8")
    fragment = (core / "android/java/org/chromium/chrome/browser/shields/ContentFilteringFragment.java").read_text(encoding="utf-8")
    adapter = (core / "android/java/org/chromium/chrome/browser/shields/ContentFilteringAdapter.java").read_text(encoding="utf-8")
    mojom = (core / "components/brave_shields/core/common/filter_list.mojom").read_text(encoding="utf-8")
    corpus = manager + service + fragment + adapter + mojom
    required = (
        "EnsureSandiumDefaultSubscriptions();",
        "CreateSubscription(subscription_url);",
        "StartDownload(subscription_url, true);",
        "RefreshAllSubscriptions",
        "CountFilterSourceRules",
        "info->size_bytes",
        "info->rule_count",
        "refreshAllSubscriptions(",
        "customFilter.ruleCount",
        "customFilter.sizeBytes",
    )
    missing = [marker for marker in required if marker not in corpus]
    if missing:
        raise SystemExit("SANDIUM_FILTER_BOOTSTRAP_VERIFY=FAIL missing markers: " + ", ".join(missing))
    if len(FILTERS) != 30 or len({url for url, _ in FILTERS}) != 30:
        raise SystemExit("SANDIUM_FILTER_BOOTSTRAP_VERIFY=FAIL expected 30 unique subscriptions")
    if "updateFilterLists(" in fragment or "SANDIUM_FILTER_REFRESH_PLACEHOLDER" in fragment:
        raise SystemExit("SANDIUM_FILTER_BOOTSTRAP_VERIFY=FAIL wrong or incomplete refresh action")
    print("SANDIUM_FILTER_BOOTSTRAP_VERIFY=PASS startup_seed=true refresh=native_subscriptions "
          "lists=30 default_enabled=true cache_metadata=source_entries+bytes")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", required=True, type=Path)
    args = parser.parse_args()
    core = args.core.resolve()
    if not core.is_dir():
        raise SystemExit(f"SANDIUM_FILTER_BOOTSTRAP=FAIL missing core directory {core}")
    verify_pin(core)
    apply(core)
    verify(core)


if __name__ == "__main__":
    main()
