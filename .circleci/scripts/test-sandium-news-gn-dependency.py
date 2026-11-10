#!/usr/bin/env python3
"""Offline tests for the pinned Brave News Android GN dependency guard."""
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).with_name("apply-sandium-news-gn-dependency.py")
SPEC = importlib.util.spec_from_file_location("sandium_news_gn", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

FIXTURE = """# Copyright
import("//brave/components/brave_ads/buildflags/buildflags.gni")
import("//brave/components/brave_wallet/common/buildflags/buildflags.gni")
import("//build/config/android/rules.gni")

source_set("preferences") {
  sources = [ "brave_pref_service_bridge.cc" ]
  deps = [
    "//base",
    "//brave/components/brave_news/common",
    "//chrome/browser:browser_process",
  ]
}

java_cpp_strings("java_pref_names_srcjar") {
  sources = [ "//brave/components/brave_news/common/pref_names.h" ]
}
"""
once = MODULE.transform(FIXTURE)
twice = MODULE.transform(once)
assert once == twice, "patch must be idempotent"
assert once.count(MODULE.IMPORT) == 1
assert once.count(MODULE.CONDITIONAL_DEP) == 1
assert once.count(MODULE.UNCONDITIONAL_DEP) == 0
assert '"//brave/components/brave_news/common/pref_names.h"' in once
assert "source_set(\\"preferences\\")" in once
print("SANDIUM_NEWS_GN_DEPENDENCY_TEST=PASS conditional=true idempotent=true")
