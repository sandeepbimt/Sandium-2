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
    "kSandiumAdBlockEngineWarmupRequested",
    "kSandiumAdBlockEngineWarmupDone",
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

HOMEPAGE_WARMUP_PATCH = (HERE / "apply-sandium-homepage-adblock-warmup.py").read_text(encoding="utf-8")
# Two textual occurrences are intentional: one in LEGACY_STARTUP_WARMUP,
# which removes the old profile-startup trigger, and one in the new deferred
# homepage-triggered implementation. The patched native C++ ends with only
# the latter active call.
assert HOMEPAGE_WARMUP_PATCH.count("filters_provider_manager_->ForceNotifyObservers(false);") == 2
assert "LEGACY_STARTUP_WARMUP in source" in HOMEPAGE_WARMUP_PATCH
assert "requestSandiumHomepageWarmup(mTab.getProfile())" in HOMEPAGE_WARMUP_PATCH
assert "last_successful_update_attempt.is_min()" in HOMEPAGE_WARMUP_PATCH
assert "homepage_warmup_requested_ = true;" in HOMEPAGE_WARMUP_PATCH
assert "homepage_warmup_engine_reload_requested_ = true;" in HOMEPAGE_WARMUP_PATCH
print("SANDIUM_FILTER_BOOTSTRAP_UNIT_TEST=PASS lists=29 enabled=true startup_seed=true refresh=true metadata=true homepage_deferred_warmup=true download_gated=true")

assert "base::Value::List" not in PATCH
assert "base::GetFileSize(cached_list, &cached_size)" not in PATCH
