#!/usr/bin/env python3
"""Activate Brave's native additional adblock engine during Sandium startup.

This deliberately replays the provider notification reached by the normal
filter-enable path. It does not toggle a subscription, change its preference,
refresh the source catalogue, or add a UI/Mojo hook.
"""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

EXPECTED_CORE_TAG = "v1.98.62"
EXPECTED_CORE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
EXPECTED_CHROMIUM_SHA = "d331de35ca8ab1358c7a17e4bd41627d55eaef51"

STARTUP_ANCHOR = (
    "  LoadSubscriptionServices();\n"
    "  EnsureSandiumDefaultSubscriptions();\n\n"
    "  subscription_update_timer_->Schedule(\n"
)

STARTUP_REPLACEMENT = (
    "  LoadSubscriptionServices();\n"
    "  EnsureSandiumDefaultSubscriptions();\n\n"
    "  // SANDIUM_FIRST_LAUNCH_ADBLOCK_ACTIVATION_BEGIN\n"
    "  // Re-announce the additional-engine provider set after Sandium has\n"
    "  // registered its default subscriptions. Brave's DAT-cache startup\n"
    "  // optimization can consume the first provider notification; this\n"
    "  // explicit notification activates the same native reload path used by\n"
    "  // re-enabling a filter. Later download notifications load new list data.\n"
    "  // No subscription enabled-state preference is modified here.\n"
    "  if (local_state_ &&\n"
    "      !local_state_->GetBoolean(prefs::kSandiumAdBlockEngineWarmupDone)) {\n"
    "    local_state_->SetBoolean(prefs::kSandiumAdBlockEngineWarmupRequested, true);\n"
    "    filters_provider_manager_->ForceNotifyObservers(/*is_default_engine=*/false);\n"
    "  }\n"
    "  // SANDIUM_FIRST_LAUNCH_ADBLOCK_ACTIVATION_END\n\n"
    "  subscription_update_timer_->Schedule(\n"
)


def replace_once(source: str, old: str, new: str, marker: str, label: str) -> str:
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


def transform_manager_cc(source: str) -> str:
    return replace_once(
        source,
        STARTUP_ANCHOR,
        STARTUP_REPLACEMENT,
        "SANDIUM_FIRST_LAUNCH_ADBLOCK_ACTIVATION_BEGIN",
        "native startup adblock activation",
    )


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
    print(
        f"SANDIUM_ADBLOCK_FIRST_LAUNCH_PIN=PASS brave={tag}@{core_sha} "
        f"chromium={chromium_sha}"
    )


def apply(core: Path) -> None:
    manager_cc = core / "components/brave_shields/content/browser/ad_block_subscription_service_manager.cc"
    source = manager_cc.read_text(encoding="utf-8")
    updated = transform_manager_cc(source)
    if updated != source:
        manager_cc.write_text(updated, encoding="utf-8")
        print("SANDIUM_ADBLOCK_FIRST_LAUNCH_PATCH=APPLIED")
    else:
        print("SANDIUM_ADBLOCK_FIRST_LAUNCH_PATCH=ALREADY_CURRENT")


def verify(core: Path) -> None:
    manager_cc = (
        core / "components/brave_shields/content/browser/ad_block_subscription_service_manager.cc"
    ).read_text(encoding="utf-8")
    manager_header = (
        core / "components/brave_shields/core/browser/ad_block_filters_provider_manager.h"
    ).read_text(encoding="utf-8")
    manager_impl = (
        core / "components/brave_shields/core/browser/ad_block_filters_provider_manager.cc"
    ).read_text(encoding="utf-8")
    adblock_service = (
        core / "components/brave_shields/content/browser/ad_block_service.cc"
    ).read_text(encoding="utf-8")
    prefs_header = (core / "components/brave_shields/core/common/pref_names.h").read_text(
        encoding="utf-8"
    )

    start = manager_cc.find("void AdBlockSubscriptionServiceManager::OnGetDownloadManager(")
    end = manager_cc.find("void AdBlockSubscriptionServiceManager::OnListMetadata(", start)
    if start < 0 or end < 0:
        raise RuntimeError("SANDIUM_ADBLOCK_FIRST_LAUNCH_VERIFY=FAIL startup handler not found")
    startup_body = manager_cc[start:end]

    checks = {
        "one startup activation marker": manager_cc.count(
            "SANDIUM_FIRST_LAUNCH_ADBLOCK_ACTIVATION_BEGIN"
        ) == 1,
        "provider seeding precedes activation": startup_body.find(
            "EnsureSandiumDefaultSubscriptions();"
        ) < startup_body.find("ForceNotifyObservers(/*is_default_engine=*/false);"),
        "activation precedes update timer": startup_body.find(
            "ForceNotifyObservers(/*is_default_engine=*/false);"
        ) < startup_body.find("subscription_update_timer_->Schedule("),
        "one-time completion guard": "kSandiumAdBlockEngineWarmupDone" in startup_body,
        "request recorded before native reload": startup_body.find(
            "kSandiumAdBlockEngineWarmupRequested"
        ) < startup_body.find("ForceNotifyObservers(/*is_default_engine=*/false);"),
        "additional engine only": "ForceNotifyObservers(/*is_default_engine=*/false);" in startup_body,
        "provider manager explicit reload API":
            "void ForceNotifyObservers(bool is_default_engine);" in manager_header,
        "provider manager bypasses startup suppression":
            "suppress_startup_notification = false;" in manager_impl,
        "successful native load marks warmup complete":
            "load_result == FilterListLoadResult::kLoaded" in adblock_service
            and "kSandiumAdBlockEngineWarmupDone" in adblock_service,
        "startup warmup prefs registered":
            "kSandiumAdBlockEngineWarmupRequested" in prefs_header
            and "kSandiumAdBlockEngineWarmupDone" in prefs_header,
        "no homepage or Mojo callback":
            "RequestSandiumHomepageWarmup" not in manager_cc
            and "MaybeTriggerSandiumHomepageWarmup" not in manager_cc,
    }
    failures = [name for name, passed in checks.items() if not passed]
    if failures:
        raise RuntimeError(
            "SANDIUM_ADBLOCK_FIRST_LAUNCH_VERIFY=FAIL " + ", ".join(failures)
        )
    print(
        "SANDIUM_ADBLOCK_FIRST_LAUNCH_VERIFY=PASS native_startup=true "
        "additional_engine=true dat_suppression_bypassed=true "
        "preferences_preserved=true download_updates_retained=true homepage_hook=false"
    )


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(
            "usage: apply-sandium-adblock-first-launch.py <brave-core-dir> <chromium-src-dir>"
        )
    core = Path(sys.argv[1]).resolve()
    src = Path(sys.argv[2]).resolve()
    if not core.is_dir() or not src.is_dir():
        raise SystemExit("SANDIUM_ADBLOCK_FIRST_LAUNCH=FAIL missing Brave Core or Chromium source")
    verify_pin(core, src)
    apply(core)
    verify(core)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"SANDIUM_ADBLOCK_FIRST_LAUNCH=FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
