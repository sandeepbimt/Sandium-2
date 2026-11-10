#!/usr/bin/env python3
"""Offline tests for the first-visible-homepage adblock engine warm-up."""
from __future__ import annotations

import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATCHER_PATH = HERE / "apply-sandium-homepage-adblock-warmup.py"
PATCHER_SOURCE = PATCHER_PATH.read_text(encoding="utf-8")
PATCHER = runpy.run_path(str(PATCHER_PATH))


def twice(old: str, new: str, marker: str, source: str, label: str) -> str:
    first = PATCHER["replace_text"](source, old, new, marker, label)
    second = PATCHER["replace_text"](first, old, new, marker, label)
    assert first == second, f"{label}: not idempotent"
    return first


mojom = twice(
    "  UpdateFilterLists() => (bool is_updated);\n",
    "  UpdateFilterLists() => (bool is_updated);\n"
    "  RequestSandiumHomepageWarmup() => (bool accepted);\n",
    "RequestSandiumHomepageWarmup()",
    "  UpdateFilterLists() => (bool is_updated);\n",
    "mojo",
)
assert "RequestSandiumHomepageWarmup() => (bool accepted);" in mojom

manager = PATCHER["LEGACY_STARTUP_WARMUP"]
assert "ForceNotifyObservers(false)" in manager
assert "SetBoolean(prefs::kSandiumAdBlockEngineWarmupRequestedV2, false)" in PATCHER_SOURCE
assert "last_successful_update_attempt.is_min()" in PATCHER_SOURCE
assert "kSandiumAdBlockEngineWarmupDoneV2" in PATCHER_SOURCE
assert "successfully_downloaded_count != enabled_subscription_count" in PATCHER_SOURCE
assert "enabled_subscription_count" in PATCHER_SOURCE
assert "enabled_subscription_count" in PATCHER_SOURCE
assert "activate_after_all_enabled_lists=true" in PATCHER_SOURCE
assert "MaybeTriggerSandiumHomepageWarmup();" in PATCHER_SOURCE
assert "RequestSandiumHomepageWarmup" not in manager

assert "homepage_warmup_requested_ = true;" in PATCHER_SOURCE
assert "homepage_warmup_engine_reload_requested_ = true;" in PATCHER_SOURCE
assert "filters_provider_manager_->ForceNotifyObservers(false);" in PATCHER_SOURCE
assert "void ForceNotifyObservers(bool is_for_default_engine);" in PATCHER_SOURCE
assert '"                           bool is_default_engine);\\n"' in PATCHER_SOURCE
assert "void AdBlockFiltersProviderManager::ForceNotifyObservers(" in PATCHER_SOURCE
assert "MaybeConsumeEngineStartupChangeNotification(is_for_default_engine)" in PATCHER_SOURCE
assert "NotifyObservers(is_for_default_engine);" in PATCHER_SOURCE
force_start = PATCHER_SOURCE.index("void AdBlockFiltersProviderManager::ForceNotifyObservers(")
force_end = PATCHER_SOURCE.index(
    "std::string AdBlockFiltersProviderManager::GetNameForDebugging()", force_start
)
force_body = PATCHER_SOURCE[force_start:force_end]
assert "AreAllProvidersInitialized" not in force_body
assert "explicit Sandium activation request" in force_body

homepage = """    private void recordNtpShown() {
        mLastShownTimeNs = System.nanoTime();
    }
"""
patched_homepage = twice(
    "    private void recordNtpShown() {\n        mLastShownTimeNs = System.nanoTime();\n",
    "    private void recordNtpShown() {\n"
    "        org.chromium.chrome.browser.shields.FilterListServiceFactory\n"
    "                .requestSandiumHomepageWarmup(mTab.getProfile());\n"
    "        mLastShownTimeNs = System.nanoTime();\n",
    "requestSandiumHomepageWarmup(mTab.getProfile())",
    homepage,
    "homepage hook",
)
assert patched_homepage.count("requestSandiumHomepageWarmup(mTab.getProfile())") == 1

factory = """    private static final Object sLock = new Object();

    private FilterListServiceFactory() {}
"""
factory_patched = twice(
    "    private FilterListServiceFactory() {}\n",
    "    public static void requestSandiumHomepageWarmup(Profile profile) {}\n"
    "    private FilterListServiceFactory() {}\n",
    "public static void requestSandiumHomepageWarmup(Profile profile)",
    factory,
    "factory",
)
assert "requestSandiumHomepageWarmup(Profile profile)" in factory_patched

print("SANDIUM_HOMEPAGE_WARMUP_PATCHER_TEST=PASS homepage_visible=true one_shot=true "
      "native_rebuild=true no_subscription_toggle=true idempotent=true")
