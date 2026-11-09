#!/usr/bin/env python3
"""Trigger Sandium's one-time native adblock rebuild when the homepage is shown."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

EXPECTED_CORE_TAG = "v1.98.62"
EXPECTED_CORE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
EXPECTED_CHROMIUM_SHA = "d331de35ca8ab1358c7a17e4bd41627d55eaef51"

LEGACY_STARTUP_WARMUP = """  // DAT-cache startup suppression is optimized for a warm, already-built
  // engine. Sandium registers its default URL subscriptions after the native
  // service starts, so explicitly request one complete additional-engine
  // rebuild until that first successful load is confirmed.
  if (!local_state_->GetBoolean(prefs::kSandiumAdBlockEngineWarmupDone)) {
    local_state_->SetBoolean(prefs::kSandiumAdBlockEngineWarmupRequested, true);
    filters_provider_manager_->ForceNotifyObservers(false);
  }

"""


def replace_text(source: str, old: str, new: str, marker: str, label: str) -> str:
    if marker in source:
        if new not in source:
            raise RuntimeError(f"{label}: marker exists but replacement differs")
        return source
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one source anchor, found {count}")
    updated = source.replace(old, new, 1)
    if marker not in updated:
        raise RuntimeError(f"{label}: replacement marker missing")
    return updated


def patch_file(path: Path, old: str, new: str, marker: str, label: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"{label}: missing pinned source file {path}")
    before = path.read_text(encoding="utf-8")
    after = replace_text(before, old, new, marker, label)
    if after != before:
        path.write_text(after, encoding="utf-8")
    if path.read_text(encoding="utf-8") != after:
        raise RuntimeError(f"{label}: write verification failed")
    print(f"SANDIUM_HOMEPAGE_WARMUP_PATCH={label}:PASS")


def remove_legacy_startup_warmup(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    if LEGACY_STARTUP_WARMUP in source:
        source = source.replace(LEGACY_STARTUP_WARMUP, "", 1)
        path.write_text(source, encoding="utf-8")
        print("SANDIUM_HOMEPAGE_WARMUP_PATCH=remove-profile-startup-trigger:PASS")
    elif ("AdBlockSubscriptionServiceManager::MaybeTriggerSandiumHomepageWarmup()" in source
          or "ForceNotifyObservers(false)" not in source):
        print("SANDIUM_HOMEPAGE_WARMUP_PATCH=remove-profile-startup-trigger:ALREADY_ABSENT")
    else:
        raise RuntimeError("unexpected ForceNotifyObservers call remains in subscription manager")


def verify_pin(core: Path, src: Path) -> None:
    tag = subprocess.run(
        ["git", "-C", str(core), "describe", "--tags", "--exact-match"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    core_sha = subprocess.run(
        ["git", "-C", str(core), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    chromium_sha = subprocess.run(
        ["git", "-C", str(src), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if tag != EXPECTED_CORE_TAG or core_sha != EXPECTED_CORE_SHA:
        raise RuntimeError(
            f"Brave pin mismatch expected={EXPECTED_CORE_TAG}@{EXPECTED_CORE_SHA} "
            f"actual={tag}@{core_sha}"
        )
    if chromium_sha != EXPECTED_CHROMIUM_SHA:
        raise RuntimeError(
            f"Chromium pin mismatch expected={EXPECTED_CHROMIUM_SHA} actual={chromium_sha}"
        )
    print(f"SANDIUM_HOMEPAGE_WARMUP_PIN=PASS brave={tag}@{core_sha} chromium={chromium_sha}")


def apply(core: Path, src: Path) -> None:
    manager_cc = core / "components/brave_shields/content/browser/ad_block_subscription_service_manager.cc"
    remove_legacy_startup_warmup(manager_cc)
    manager_h = core / "components/brave_shields/content/browser/ad_block_subscription_service_manager.h"
    patch_file(
        manager_h,
        "  void CreateSubscription(const GURL& sub_url);\n",
        "  void CreateSubscription(const GURL& sub_url);\n"
        "  bool RequestSandiumHomepageWarmup();\n"
        "  void MaybeTriggerSandiumHomepageWarmup();\n",
        "bool RequestSandiumHomepageWarmup();",
        "subscription-manager-homepage-warmup-api",
    )
    patch_file(
        manager_h,
        "  raw_ptr<AdBlockListP3A> list_p3a_;\n",
        "  raw_ptr<AdBlockListP3A> list_p3a_;\n"
        "  bool homepage_warmup_requested_ = false;\n"
        "  bool homepage_warmup_engine_reload_requested_ = false;\n",
        "homepage_warmup_engine_reload_requested_ = false;",
        "subscription-manager-homepage-warmup-state",
    )
    patch_file(
        manager_cc,
        "      list_p3a_(list_p3a) {\n"
        "  std::move(download_manager_getter)\n",
        "      list_p3a_(list_p3a) {\n"
        "  // Clear a stale request left by an older build. The first visible\n"
        "  // homepage in this process will set it again after the UI is ready.\n"
        "  if (local_state_ &&\n"
        "      !local_state_->GetBoolean(prefs::kSandiumAdBlockEngineWarmupDone)) {\n"
        "    local_state_->SetBoolean(prefs::kSandiumAdBlockEngineWarmupRequested, false);\n"
        "  }\n"
        "  std::move(download_manager_getter)\n",
        "SetBoolean(prefs::kSandiumAdBlockEngineWarmupRequested, false)",
        "reset-stale-homepage-warmup-on-process-start",
    )
    patch_file(
        manager_cc,
        "void AdBlockSubscriptionServiceManager::CreateSubscription(\n"
        "    const GURL& sub_url) {\n",
        "bool AdBlockSubscriptionServiceManager::RequestSandiumHomepageWarmup() {\n"
        "  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);\n"
        "  if (!local_state_) {\n"
        "    return false;\n"
        "  }\n"
        "  if (local_state_->GetBoolean(prefs::kSandiumAdBlockEngineWarmupDone)) {\n"
        "    return true;\n"
        "  }\n"
        "  homepage_warmup_requested_ = true;\n"
        "  MaybeTriggerSandiumHomepageWarmup();\n"
        "  return true;\n"
        "}\n\n"
        "void AdBlockSubscriptionServiceManager::MaybeTriggerSandiumHomepageWarmup() {\n"
        "  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);\n"
        "  if (!local_state_ ||\n"
        "      !homepage_warmup_requested_ ||\n"
        "      local_state_->GetBoolean(prefs::kSandiumAdBlockEngineWarmupDone) ||\n"
        "      homepage_warmup_engine_reload_requested_ ||\n"
        "      subscription_filters_providers_.empty()) {\n"
        "    return;\n"
        "  }\n"
        "  // Wait until every enabled subscription has completed at least one\n"
        "  // successful download. A provider object alone is not readiness: Brave's\n"
        "  // base provider reports initialized even when its cached file is empty.\n"
        "  for (const auto& entry : subscription_filters_providers_) {\n"
        "    const auto info = GetInfo(entry.first);\n"
        "    if (!info || !info->enabled ||\n"
        "        info->last_successful_update_attempt.is_null() ||\n"
        "        info->last_successful_update_attempt.is_min()) {\n"
        "      return;\n"
        "    }\n"
        "  }\n"
        "  homepage_warmup_engine_reload_requested_ = true;\n"
        "  // Set the success gate only when the final downloaded subscription set\n"
        "  // is ready and the explicit rebuild is actually being dispatched.\n"
        "  local_state_->SetBoolean(prefs::kSandiumAdBlockEngineWarmupRequested, true);\n"
        "  filters_provider_manager_->ForceNotifyObservers(false);\n"
        "}\n\n"
        "void AdBlockSubscriptionServiceManager::CreateSubscription(\n"
        "    const GURL& sub_url) {\n",
        "MaybeTriggerSandiumHomepageWarmup();",
        "subscription-manager-wait-for-enabled-downloads",
    )

    patch_file(
        manager_cc,
        "  if (migrate_previous_defaults) {\n"
        "    local_state_->SetBoolean(prefs::kSandiumDefaultFilterListsMigrated, true);\n"
        "  }\n\n"
        "  // File metadata checks can block on filesystem access. Run them away from\n",
        "  if (migrate_previous_defaults) {\n"
        "    local_state_->SetBoolean(prefs::kSandiumDefaultFilterListsMigrated, true);\n"
        "  }\n"
        "  MaybeTriggerSandiumHomepageWarmup();\n\n"
        "  // File metadata checks can block on filesystem access. Run them away from\n",
        "MaybeTriggerSandiumHomepageWarmup();\n\n  // File metadata checks",
        "subscription-manager-check-warmup-after-seeding",
    )

    patch_file(
        manager_cc,
        "  UpdateSubscriptionPrefs(sub_url, *info);\n"
        "}\n\n"
        "void AdBlockSubscriptionServiceManager::DeleteSubscription(",
        "  UpdateSubscriptionPrefs(sub_url, *info);\n"
        "  MaybeTriggerSandiumHomepageWarmup();\n"
        "}\n\n"
        "void AdBlockSubscriptionServiceManager::DeleteSubscription(",
        "UpdateSubscriptionPrefs(sub_url, *info);\n  MaybeTriggerSandiumHomepageWarmup();",
        "subscription-manager-check-warmup-after-toggle",
    )

    patch_file(
        manager_cc,
        "  ClearSubscriptionPrefs(sub_url);\n",
        "  ClearSubscriptionPrefs(sub_url);\n"
        "  MaybeTriggerSandiumHomepageWarmup();\n",
        "ClearSubscriptionPrefs(sub_url);\n  MaybeTriggerSandiumHomepageWarmup();",
        "subscription-manager-check-warmup-after-delete",
    )

    patch_file(
        manager_cc,
        "  if (subscription_filters_provider) {\n"
        "    subscription_filters_provider->OnListAvailable();\n"
        "  }\n\n"
        "  NotifyObserversOfServiceEvent();\n",
        "  if (subscription_filters_provider) {\n"
        "    subscription_filters_provider->OnListAvailable();\n"
        "  }\n"
        "  MaybeTriggerSandiumHomepageWarmup();\n\n"
        "  NotifyObserversOfServiceEvent();\n",
        "MaybeTriggerSandiumHomepageWarmup();\n\n  NotifyObserversOfServiceEvent();",
        "subscription-manager-check-warmup-after-download",
    )

    mojom = core / "components/brave_shields/core/common/filter_list.mojom"
    patch_file(
        mojom,
        "  UpdateFilterLists() => (bool is_updated);\n",
        "  UpdateFilterLists() => (bool is_updated);\n"
        "  RequestSandiumHomepageWarmup() => (bool accepted);\n",
        "RequestSandiumHomepageWarmup()",
        "mojo-homepage-warmup-method",
    )

    service_h = core / "components/brave_shields/content/browser/filter_list_service.h"
    patch_file(
        service_h,
        "  void UpdateFilterLists(UpdateFilterListsCallback callback) override;\n",
        "  void UpdateFilterLists(UpdateFilterListsCallback callback) override;\n"
        "  void RequestSandiumHomepageWarmup(\n"
        "      RequestSandiumHomepageWarmupCallback callback) override;\n",
        "void RequestSandiumHomepageWarmup(",
        "filter-list-service-homepage-method",
    )

    service_cc = core / "components/brave_shields/content/browser/filter_list_service.cc"
    patch_file(
        service_cc,
        "void FilterListService::UpdateFilterLists(UpdateFilterListsCallback callback) {\n"
        "  ad_block_service_->component_service_manager()->UpdateFilterLists(\n"
        "      std::move(callback));\n"
        "}\n",
        "void FilterListService::UpdateFilterLists(UpdateFilterListsCallback callback) {\n"
        "  ad_block_service_->component_service_manager()->UpdateFilterLists(\n"
        "      std::move(callback));\n"
        "}\n\n"
        "void FilterListService::RequestSandiumHomepageWarmup(\n"
        "    RequestSandiumHomepageWarmupCallback callback) {\n"
        "  std::move(callback).Run(\n"
        "      ad_block_service_->RequestSandiumHomepageWarmup());\n"
        "}\n",
        "FilterListService::RequestSandiumHomepageWarmup(",
        "filter-list-service-homepage-implementation",
    )

    adblock_h = core / "components/brave_shields/content/browser/ad_block_service.h"
    patch_file(
        adblock_h,
        "  void AddObserver(Observer* observer);\n",
        "  void AddObserver(Observer* observer);\n"
        "  // Request the one-time additional-engine rebuild when Sandium's\n"
        "  // homepage is first shown. Returns false if the request cannot be queued.\n"
        "  bool RequestSandiumHomepageWarmup();\n",
        "bool RequestSandiumHomepageWarmup();",
        "adblock-service-homepage-api",
    )
    adblock_cc = core / "components/brave_shields/content/browser/ad_block_service.cc"
    patch_file(
        adblock_cc,
        "AdBlockService::~AdBlockService() = default;\n",
        "AdBlockService::~AdBlockService() = default;\n\n"
        "bool AdBlockService::RequestSandiumHomepageWarmup() {\n"
        "  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);\n"
        "  if (!subscription_service_manager_) {\n"
        "    return false;\n"
        "  }\n"
        "  return subscription_service_manager_->RequestSandiumHomepageWarmup();\n"
        "}\n",
        "bool AdBlockService::RequestSandiumHomepageWarmup()",
        "adblock-service-homepage-implementation",
    )

    factory = core / "android/java/org/chromium/chrome/browser/shields/FilterListServiceFactory.java"
    patch_file(
        factory,
        "    private static final Object sLock = new Object();\n",
        "    private static final Object sLock = new Object();\n"
        "    private static boolean sHomepageWarmupRequestPending;\n"
        "    private static boolean sHomepageWarmupAccepted;\n"
        "    private static @Nullable FilterListAndroidHandler sHomepageWarmupHandler;\n",
        "sHomepageWarmupRequestPending",
        "homepage-factory-request-state",
    )
    patch_file(
        factory,
        "    private FilterListServiceFactory() {}\n",
        "    public static void requestSandiumHomepageWarmup(Profile profile) {\n"
        "        synchronized (sLock) {\n"
        "            if (sHomepageWarmupAccepted || sHomepageWarmupRequestPending) return;\n"
        "            sHomepageWarmupRequestPending = true;\n"
        "        }\n"
        "\n"
        "        @Nullable FilterListAndroidHandler handler =\n"
        "                getInstance().getFilterListAndroidHandler(\n"
        "                        profile,\n"
        "                        () -> {\n"
        "                            synchronized (sLock) {\n"
        "                                sHomepageWarmupRequestPending = false;\n"
        "                                sHomepageWarmupHandler = null;\n"
        "                            }\n"
        "                        });\n"
        "        if (handler == null) {\n"
        "            synchronized (sLock) {\n"
        "                sHomepageWarmupRequestPending = false;\n"
        "            }\n"
        "            return;\n"
        "        }\n"
        "\n"
        "        synchronized (sLock) {\n"
        "            sHomepageWarmupHandler = handler;\n"
        "        }\n"
        "        handler.requestSandiumHomepageWarmup(accepted -> {\n"
        "            synchronized (sLock) {\n"
        "                sHomepageWarmupRequestPending = false;\n"
        "                sHomepageWarmupAccepted = accepted;\n"
        "                if (!accepted) sHomepageWarmupHandler = null;\n"
        "            }\n"
        "        });\n"
        "    }\n"
        "\n"
        "    private FilterListServiceFactory() {}\n",
        "public static void requestSandiumHomepageWarmup(Profile profile)",
        "homepage-factory-trigger-method",
    )

    ntp = src / "chrome/android/java/src/org/chromium/chrome/browser/ntp/NewTabPage.java"
    patch_file(
        ntp,
        "    private void recordNtpShown() {\n"
        "        mLastShownTimeNs = System.nanoTime();\n",
        "    private void recordNtpShown() {\n"
        "        org.chromium.chrome.browser.shields.FilterListServiceFactory\n"
        "                .requestSandiumHomepageWarmup(mTab.getProfile());\n"
        "        mLastShownTimeNs = System.nanoTime();\n",
        "requestSandiumHomepageWarmup(mTab.getProfile())",
        "new-tab-page-visible-trigger",
    )


def verify(core: Path, src: Path) -> None:
    manager = (core / "components/brave_shields/content/browser/ad_block_subscription_service_manager.cc").read_text(encoding="utf-8")
    mojom = (core / "components/brave_shields/core/common/filter_list.mojom").read_text(encoding="utf-8")
    service = (core / "components/brave_shields/content/browser/filter_list_service.cc").read_text(encoding="utf-8")
    adblock = (core / "components/brave_shields/content/browser/ad_block_service.cc").read_text(encoding="utf-8")
    factory = (core / "android/java/org/chromium/chrome/browser/shields/FilterListServiceFactory.java").read_text(encoding="utf-8")
    ntp = (src / "chrome/android/java/src/org/chromium/chrome/browser/ntp/NewTabPage.java").read_text(encoding="utf-8")
    ensure_start = manager.find("void AdBlockSubscriptionServiceManager::EnsureSandiumDefaultSubscriptions()")
    ensure_end = manager.find("void AdBlockSubscriptionServiceManager::OnCheckedSandiumDefaultSubscriptionCaches", ensure_start)
    ensure_body = manager[ensure_start:ensure_end]
    if "ForceNotifyObservers(false)" in ensure_body:
        raise RuntimeError("profile-startup warm-up still exists; expected homepage-only trigger")
    required = (
        "RequestSandiumHomepageWarmup() => (bool accepted);",
        "RequestSandiumHomepageWarmupCallback callback",
        "ad_block_service_->RequestSandiumHomepageWarmup()",
        "subscription_service_manager_->RequestSandiumHomepageWarmup()",
        "MaybeTriggerSandiumHomepageWarmup()",
        "kSandiumAdBlockEngineWarmupRequested",
        "SetBoolean(prefs::kSandiumAdBlockEngineWarmupRequested, false)",
        "last_successful_update_attempt.is_min()",
        "homepage_warmup_requested_",
        "homepage_warmup_engine_reload_requested_",
        "kSandiumAdBlockEngineWarmupDone",
        "load_result == FilterListLoadResult::kLoaded",
        "sHomepageWarmupAccepted",
        "requestSandiumHomepageWarmup(mTab.getProfile())",
    )
    corpus = manager + mojom + service + adblock + factory + ntp
    missing = [item for item in required if item not in corpus]
    if missing:
        raise RuntimeError("homepage warm-up verification missing: " + ", ".join(missing))
    print("SANDIUM_HOMEPAGE_WARMUP_VERIFY=PASS trigger=visible_ntp one_shot=true "
          "native_engine_rebuild=true wait_for_all_enabled_downloads=true success_gated=true "
          "subscription_preferences_unchanged=true")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--src", type=Path, required=True)
    args = parser.parse_args()
    verify_pin(args.core, args.src)
    apply(args.core, args.src)
    verify(args.core, args.src)


if __name__ == "__main__":
    main()
