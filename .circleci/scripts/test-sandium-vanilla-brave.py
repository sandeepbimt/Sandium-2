#!/usr/bin/env python3
"""Offline regression tests for the pinned vanilla-Brave source/args gate."""
from pathlib import Path
import runpy

HERE = Path(__file__).resolve().parent
MODULE = runpy.run_path(str(HERE / "verify-sandium-vanilla-brave.py"))

sample = """# Keep unrelated custom build settings.
is_official_build = false
enable_ai_chat = false
enable_brave_wallet = false
enable_brave_news = false
target_cpu = "arm64"
"""
clean = MODULE["strip_gn_overrides_text"](sample)
assert "enable_ai_chat =" not in clean
assert "enable_brave_wallet =" not in clean
assert "enable_brave_news =" not in clean
assert 'target_cpu = "arm64"' in clean
assert "is_official_build = false" in clean
assert MODULE["strip_gn_overrides_text"](clean) == clean
assert MODULE["has_gn_overrides"](sample) == [
    "enable_ai_chat = false",
    "enable_brave_wallet = false",
    "enable_brave_news = false",
]
assert MODULE["has_gn_overrides"](clean) == []

for path in (
    "components/ai_chat",
    "browser/ai_chat",
    "components/brave_wallet",
    "browser/brave_wallet",
    "components/brave_news",
    "browser/brave_news",
    "browser/android/BUILD.gn",
    "browser/android/brave_tab_features.cc",
    "browser/android/brave_tab_features.h",
    "browser/android/preferences/BUILD.gn",
    "build/android/config.gni",
    "browser/notifications/BUILD.gn",
):
    assert path in MODULE["BRAVE_RESTORE_PREFIXES"], path

assert "android/BUILD.gn" in MODULE["BRAVE_RESTORE_PREFIXES"]
assert "android/BUILD.gn" not in MODULE["BRAVE_VERIFY_PREFIXES"]
assert "chrome/browser/partnercustomizations/java/src/org/chromium/chrome/browser/partnercustomizations/PartnerBrowserCustomizations.java" in MODULE["CHROMIUM_RESTORE_PREFIXES"]

print("SANDIUM_VANILLA_BRAVE_TEST=PASS restored_components=AI_CHAT,WALLET,NEWS gn_overrides=absent unrelated_args=preserved")
