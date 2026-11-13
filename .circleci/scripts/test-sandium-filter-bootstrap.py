#!/usr/bin/env python3
"""Offline regression checks for Sandium's first-launch native filter bootstrap."""
from __future__ import annotations
import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILTERS = runpy.run_path(str(HERE / "apply-sandium-filter-subscriptions.py"))["FILTERS"]
PATCH = (HERE / "apply-sandium-filter-bootstrap.py").read_text(encoding="utf-8")
assert len(FILTERS) == 30 and len({url for url, _ in FILTERS}) == 30
assert FILTERS[-1] == ("https://ublockorigin.github.io/uAssets/filters/annoyances-others.txt", "uBlock filters – Annoyances")
assert all("annoyances.min.txt" not in url for url, _ in FILTERS)
assert 'DeleteSubscription(GURL("https://ublockorigin.github.io/uAssets/filters/annoyances.txt"))' in PATCH
assert 'DeleteSubscription(GURL("https://ublockorigin.github.io/uAssetsCDN/filters/annoyances.min.txt"))' in PATCH
for marker in (
    "EnsureSandiumDefaultSubscriptions();",
    "kSandiumAdBlockEngineWarmupRequested",
    "kSandiumAdBlockEngineWarmupDone",
    "kSandiumAdBlockEngineWarmupRequestedV2",
    "kSandiumAdBlockEngineWarmupDoneV2",
    "local_state_->SetBoolean(prefs::kSandiumAdBlockEngineWarmupDoneV2, true);",
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
assert "filters-provider-manager-broadcast-notify-api" in HOMEPAGE_WARMUP_PATCH
assert "filters-provider-manager-broadcast-notify-implementation" in HOMEPAGE_WARMUP_PATCH
assert "NotifyObservers(is_for_default_engine);" in HOMEPAGE_WARMUP_PATCH
force_start = HOMEPAGE_WARMUP_PATCH.index(
    "void AdBlockFiltersProviderManager::ForceNotifyObservers("
)
force_end = HOMEPAGE_WARMUP_PATCH.index(
    "std::string AdBlockFiltersProviderManager::GetNameForDebugging()", force_start
)
force_body = HOMEPAGE_WARMUP_PATCH[force_start:force_end]
assert "AreAllProvidersInitialized" not in force_body
assert "explicit Sandium activation request" in force_body
print("SANDIUM_FILTER_BOOTSTRAP_UNIT_TEST=PASS lists=30 enabled=true startup_seed=true refresh=true metadata=true homepage_deferred_warmup=true download_gated=true first_filter_bypass=true")

assert "base::Value::List" not in PATCH
assert "base::GetFileSize(cached_list, &cached_size)" not in PATCH

# A new default URL seeds once without reenabling existing disabled entries or
# resurrecting explicitly deleted entries. Preserve these upgrade guards.
assert "A prior user deletion is recorded in seeded_urls and must remain deleted." in PATCH
assert "if (was_seeded) {\n        continue;" in PATCH
assert "if (info->enabled)" in PATCH
assert "migrate_29_list_checkpoint(manager_cc)" in PATCH

# Real #1075-style generated native manager, built from the exact pinned source
# with the previous 29-list bootstrap. Migration must be surgical and idempotent.
import tempfile
import difflib
BOOTSTRAP = runpy.run_path(str(HERE / "apply-sandium-filter-bootstrap.py"))
with tempfile.TemporaryDirectory() as directory:
    manager = Path(directory) / "manager.cc"
    original = (HERE / "fixtures/filter-subscription-manager-29.cc").read_text()
    manager.write_text(original)
    BOOTSTRAP["migrate_29_list_checkpoint"](manager)
    upgraded = manager.read_text()
    BOOTSTRAP["migrate_29_list_checkpoint"](manager)
    assert manager.read_text() == upgraded
    assert upgraded.count('"https://ublockorigin.github.io/uAssets/filters/annoyances-others.txt"') == 1
    assert 'DeleteSubscription(GURL("https://ublockorigin.github.io/uAssets/filters/annoyances.txt"))' not in upgraded
    assert 'DeleteSubscription(GURL("https://ublockorigin.github.io/uAssetsCDN/filters/annoyances.min.txt"))' not in upgraded
    assert "if (was_seeded) {\n        continue;" in upgraded
    assert "if (info->enabled)" in upgraded
    # Native declaration, user deletion handler and all download/update logic
    # are unchanged. Only the catalogue insertion and obsolete purge change.
    changed = [line for line in difflib.ndiff(original.splitlines(), upgraded.splitlines())
               if line.startswith(("+ ", "- "))]
    assert len(changed) == 8, changed
print("SANDIUM_FILTER_CHECKPOINT_MIGRATION=PASS from=29 to=30 idempotent=true user_choices=preserved")

# #1079 regression: execute every manager replacement in the full bootstrap
# against a #1075 manager AFTER the later homepage overlay. Checking only the
# migration helper previously missed the strict method-body rejection.
with tempfile.TemporaryDirectory() as directory:
    core = Path(directory)
    manager = core / "components/brave_shields/content/browser/ad_block_subscription_service_manager.cc"
    manager.parent.mkdir(parents=True)
    manager.write_text((HERE / "fixtures/filter-subscription-manager-29.cc").read_text())
    module = runpy.run_path(str(HERE / "apply-sandium-filter-bootstrap.py"))
    globals_ = module["apply"].__globals__
    original_replace = globals_["replace_once"]
    labels = []
    def manager_replace(path, old, new, marker, label):
        if path == manager:
            labels.append(label)
            original_replace(path, old, new, marker, label)
    globals_["replace_once"] = manager_replace
    module["apply"](core)
    first = manager.read_text()
    module["apply"](core)
    assert manager.read_text() == first
    assert labels.count("manager-first-launch-high-priority-downloads") == 2
    assert "MaybeTriggerSandiumHomepageWarmup();\n\n  // File metadata checks" in first
    assert first.count("void AdBlockSubscriptionServiceManager::MaybeTriggerSandiumHomepageWarmup()") == 1
    # Fail closed on a real unexpected native body change, rather than using a
    # broad marker-only success or blindly resetting the whole manager.
    manager.write_text(first.replace("    if (info->enabled) {", "    if (info->enabled && false) {", 1))
    try:
        module["apply"](core)
    except SystemExit as error:
        assert "incomplete patch manager-first-launch-high-priority-downloads" in str(error)
    else:
        raise AssertionError("unknown manager body drift accepted")
print("SANDIUM_FILTER_COMPOSED_CHECKPOINT=PASS homepage_preserved=true repeat=true drift_rejected=true")
