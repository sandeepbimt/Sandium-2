#!/usr/bin/env python3
"""Regression tests for the Wallet-disabled Java compile contract."""
import importlib.util
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).with_name("apply-sandium-wallet-java-compile-contract.py")
spec = importlib.util.spec_from_file_location("wallet_contract", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

COMMON = '''import("//brave/components/brave_wallet/common/buildflags/buildflags.gni")
assert(enable_brave_wallet)
preprocess_folder = "preprocessed"
preprocess_mojo_manifest = "preprocessed_mojo_manifest.json"
source_set("common") {
  sources = [ "common.cc" ]
}
preprocess_if_expr("preprocess_mojo") {
  deps = [ "//brave/components/brave_wallet/common:mojom_js" ]
}
mojom("mojom") {
  generate_java = true
  sources = [
    "brave_wallet.mojom",
    "ledger_bridge.mojom",
    "meld_integration.mojom",
  ]
  public_deps = [
    "//mojo/public/mojom/base",
    "//url/mojom:url_mojom_gurl",
    "//url/mojom:url_mojom_origin",
  ]
}
source_set("unit_tests") {
  sources = [ "unit_test.cc" ]
}
'''
ANDROID = '''if (enable_brave_wallet) {
  java_cpp_enum("brave_android_java_enums_srcjar") {
    sources = [ "//brave/components/decentralized_dns/core/constants.h" ]
  }
}
'''
NOTIFICATIONS = '''    deps += [
      "//chrome/browser:browser_process",
      "//chrome/browser:browser_public_dependencies",
    ]

    if (enable_brave_wallet) {
      deps += [ "//brave/android:brave_android_java_enums_srcjar" ]
    }
'''
CONFIG = '''brave_chrome_java_srcjar_deps = [
  "//brave/android:brave_config_java",
  "//brave/android:brave_policy_constants_java_srcjar",
  "//brave/components/brave_account/android:brave_account_constants_srcjar",
  "//brave/components/web_discovery/browser/android:java_pref_names_srcjar",
]

if (enable_brave_wallet) {
  brave_chrome_java_srcjar_deps += [ "//brave/android:brave_android_java_enums_srcjar" ]
}
'''

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    core, src = root / "brave", root / "src"
    (core / "components/brave_wallet/common").mkdir(parents=True)
    (core / "android").mkdir()
    (core / "browser/notifications").mkdir(parents=True)
    (core / "build/android").mkdir(parents=True)
    (src / "chrome/android").mkdir(parents=True)
    (core / "components/brave_wallet/common/BUILD.gn").write_text(COMMON)
    (core / "android/BUILD.gn").write_text(ANDROID)
    (core / "browser/notifications/BUILD.gn").write_text(NOTIFICATIONS)
    (core / "build/android/config.gni").write_text(CONFIG)
    module.apply(core, src)
    first = [p.read_text() for p in (
        core / "components/brave_wallet/common/BUILD.gn",
        core / "android/BUILD.gn",
        core / "browser/notifications/BUILD.gn",
        core / "build/android/config.gni")]
    module.apply(core, src)
    second = [p.read_text() for p in (
        core / "components/brave_wallet/common/BUILD.gn",
        core / "android/BUILD.gn",
        core / "browser/notifications/BUILD.gn",
        core / "build/android/config.gni")]
    assert first == second, "Wallet compile contract must be idempotent"
    common, android, notifications, config = second
    assert 'if (enable_brave_wallet) {' in common
    assert 'assert(enable_brave_wallet)' not in common
    assert common.count('mojom("mojom")') == 1
    assert module.MOJOM_BEGIN in common and module.MOJOM_END in common
    assert module.ENUM_BEGIN in android and 'if (enable_brave_wallet)' not in android
    assert 'brave_android_java_enums_srcjar' in notifications
    assert 'if (enable_brave_wallet)' not in notifications
    assert '"//brave/components/brave_wallet/common:mojom"' in config
    assert 'if (enable_brave_wallet)' not in config
print("SANDIUM_WALLET_JAVA_COMPILE_CONTRACT_TEST=PASS idempotent=true feature_flag_preserved=true")
