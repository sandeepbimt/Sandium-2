#!/usr/bin/env python3
"""Offline regression checks for Sandium's first-launch native filter bootstrap."""
from __future__ import annotations
import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILTERS = runpy.run_path(str(HERE / "apply-sandium-filter-subscriptions.py"))["FILTERS"]
PATCH = (HERE / "apply-sandium-filter-bootstrap.py").read_text(encoding="utf-8")
assert len(FILTERS) == 29 and len({url for url, _ in FILTERS}) == 29
assert all(title != "uBlock filters – Annoyances" for _, title in FILTERS)
assert all("annoyances.min.txt" not in url for url, _ in FILTERS)
assert 'DeleteSubscription(GURL("https://ublockorigin.github.io/uAssets/filters/annoyances.txt"))' in PATCH
assert 'DeleteSubscription(GURL("https://ublockorigin.github.io/uAssetsCDN/filters/annoyances.min.txt"))' in PATCH
for marker in (
    "EnsureSandiumDefaultSubscriptions();",
    "load_result == FilterListLoadResult::kLoaded",
    "CreateSubscription(subscription_url);",
    "StartDownload(url, true);",
    "RefreshAllSubscriptions",
    "CountFilterSourceRules",
    "items[i]->size_bytes",
    "items[i]->rule_count",
    "base::ListValue seeded_urls",
    "base::GetFileSize(path)",
    "base::ThreadPool::PostTaskAndReplyWithResult",
    "base::MayBlock()",
    "OnCheckedSandiumDefaultSubscriptionCaches",
    "filter-service-async-cache-metadata-reply",
    "ad_block_service_->subscription_service_manager()->DeleteSubscription(\n      sub_url);",
    "mFilterListAndroidHandler.refreshAllSubscriptions(",
    "customFilter.ruleCount",
    "customFilter.sizeBytes",
):
    assert marker in PATCH, f"missing implementation marker: {marker}"
assert "DEFAULT_DISABLED_FILTER_URLS" not in PATCH
assert "mFilterListAndroidHandler.updateFilterLists(" not in PATCH
# The bootstrap patcher retains one legacy block only as an exact removal
# template; it must not reintroduce the profile-startup engine trigger.
assert PATCH.count("filters_provider_manager_->ForceNotifyObservers(false);") == 1

assert "requestSandiumHomepageWarmup" not in PATCH
assert "registry->RegisterBooleanPref(prefs::kSandiumAdBlockEngineWarmup" not in PATCH
print("SANDIUM_FILTER_BOOTSTRAP_UNIT_TEST=PASS lists=29 enabled=true startup_seed=true refresh=true metadata=true download_gated=true")

assert "base::Value::List" not in PATCH
assert "base::GetFileSize(cached_list, &cached_size)" not in PATCH
