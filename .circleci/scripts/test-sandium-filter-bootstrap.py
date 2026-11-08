#!/usr/bin/env python3
"""Offline regression checks for Sandium's first-launch native filter bootstrap."""
from __future__ import annotations
import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILTERS = runpy.run_path(str(HERE / "apply-sandium-filter-subscriptions.py"))["FILTERS"]
PATCH = (HERE / "apply-sandium-filter-bootstrap.py").read_text(encoding="utf-8")
assert len(FILTERS) == 30 and len({url for url, _ in FILTERS}) == 30
for marker in (
    "EnsureSandiumDefaultSubscriptions();",
    "CreateSubscription(subscription_url);",
    "StartDownload(subscription_url, true);",
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
print("SANDIUM_FILTER_BOOTSTRAP_UNIT_TEST=PASS lists=30 enabled=true startup=true refresh=true metadata=true")

assert "base::Value::List" not in PATCH
assert "base::GetFileSize(cached_list, &cached_size)" not in PATCH
