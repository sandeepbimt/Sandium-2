#!/usr/bin/env python3
"""Offline regression tests for the native first-launch Adblock activation hook."""
from __future__ import annotations

import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATCHER = HERE / "apply-sandium-adblock-first-launch.py"
PATCH = runpy.run_path(str(PATCHER))


def apply_twice(source: str) -> str:
    first = PATCH["transform_manager_cc"](source)
    second = PATCH["transform_manager_cc"](first)
    assert second == first, "native startup activation patch is not idempotent"
    return first


fixture = (
    "  download_manager_->CancelAllPendingDownloads();\n"
    "  LoadSubscriptionServices();\n"
    "  EnsureSandiumDefaultSubscriptions();\n\n"
    "  subscription_update_timer_->Schedule(\n"
)
patched = apply_twice(fixture)

seed = patched.index("EnsureSandiumDefaultSubscriptions();")
force = patched.index("ForceNotifyObservers(/*is_default_engine=*/false);")
timer = patched.index("subscription_update_timer_->Schedule(")
assert seed < force < timer, "activation must run after provider seeding and before update scheduling"
assert patched.count("SANDIUM_FIRST_LAUNCH_ADBLOCK_ACTIVATION_BEGIN") == 1
assert patched.count("SANDIUM_FIRST_LAUNCH_ADBLOCK_ACTIVATION_END") == 1
assert "kSandiumAdBlockEngineWarmupDone" in patched
assert "kSandiumAdBlockEngineWarmupRequested" in patched
assert "EnableSubscription(" not in patched
assert "UpdateSubscriptionPrefs(" not in patched
replacement = PATCH["STARTUP_REPLACEMENT"]
assert "RequestSandiumHomepageWarmup" not in replacement
assert "recordNtpShown" not in replacement
assert "mTab.getProfile()" not in replacement

print(
    "SANDIUM_ADBLOCK_FIRST_LAUNCH_UNIT_TEST=PASS idempotent=true "
    "native_startup=true provider_seed_order=true additional_engine=true "
    "subscription_state_unchanged=true no_homepage_or_mojo=true"
)
