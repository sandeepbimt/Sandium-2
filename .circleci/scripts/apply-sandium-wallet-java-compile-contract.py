#!/usr/bin/env python3
"""Preserve compile-only Wallet Java bindings while the Wallet feature stays disabled."""
from pathlib import Path
import argparse
import re
import subprocess
import sys

BRAVE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
CHROMIUM_SHA = "d331de35ca8ab1358c7a17e4bd41627d55eaef51"
MOJOM_BEGIN = "# SANDIUM_WALLET_MOJOM_COMPILE_CONTRACT_BEGIN"
MOJOM_END = "# SANDIUM_WALLET_MOJOM_COMPILE_CONTRACT_END"
ENUM_BEGIN = "# SANDIUM_WALLET_DNS_ENUM_COMPILE_CONTRACT_BEGIN"
ENUM_END = "# SANDIUM_WALLET_DNS_ENUM_COMPILE_CONTRACT_END"

def patch_wallet_common(path):
    text = path.read_text(encoding="utf-8")
    if MOJOM_BEGIN in text and MOJOM_END in text:
        if text.count(MOJOM_BEGIN) != 1 or text.count(MOJOM_END) != 1 or "assert(enable_brave_wallet)" in text:
            raise RuntimeError("Wallet Mojo compile-contract markers or guard are inconsistent")
        print("SANDIUM_WALLET_MOJOM_COMPILE_CONTRACT=ALREADY_APPLIED")
        return
    assertion = "assert(enable_brave_wallet)\n"
    if text.count(assertion) != 1:
        raise RuntimeError("Wallet common BUILD.gn assert anchor changed")
    match = re.search(r'(?ms)^mojom\("mojom"\) \{\n.*?^\}\s*$', text)
    if not match:
        raise RuntimeError("Wallet common BUILD.gn mojom target anchor changed")
    mojom = match.group(0).rstrip()
    prefix, suffix = text[:match.start()], text[match.end():]
    prefix = prefix.replace(assertion, "if (enable_brave_wallet) {\n", 1)
    updated = (prefix.rstrip() + "\n}\n\n" + MOJOM_BEGIN + "\n" + mojom + "\n" +
               MOJOM_END + "\n\nif (enable_brave_wallet) {\n" + suffix.lstrip() + "\n}\n")
    path.write_text(updated, encoding="utf-8")
    check = path.read_text(encoding="utf-8")
    if "assert(enable_brave_wallet)" in check or check.count('mojom("mojom")') != 1:
        raise RuntimeError("Wallet Mojo compile-contract post-write verification failed")
    print("SANDIUM_WALLET_MOJOM_COMPILE_CONTRACT=APPLIED")

def patch_android_enums(path):
    text = path.read_text(encoding="utf-8")
    new = (ENUM_BEGIN + '\n'
           'java_cpp_enum("brave_android_java_enums_srcjar") {\n'
           '  # Compile-time enum bindings used by shared BraveActivity Java sources.\n'
           '  # This does not enable Wallet or decentralized DNS runtime features.\n'
           '  sources = [ "//brave/components/decentralized_dns/core/constants.h" ]\n'
           '}\n' + ENUM_END)
    if ENUM_BEGIN in text and ENUM_END in text:
        if text.count(ENUM_BEGIN) != 1 or text.count(ENUM_END) != 1 or new not in text:
            raise RuntimeError("Wallet DNS enum compile-contract markers are inconsistent")
        print("SANDIUM_WALLET_DNS_ENUM_COMPILE_CONTRACT=ALREADY_APPLIED")
        return
    upstream = ('java_cpp_enum("brave_android_java_enums_srcjar") {\n'
                '  sources = []\n\n'
                '  if (enable_brave_wallet) {\n'
                '    sources += [ "//brave/components/decentralized_dns/core/constants.h" ]\n'
                '  }\n'
                '}')
    conditional = ('if (enable_brave_wallet) {\n'
                   '  java_cpp_enum("brave_android_java_enums_srcjar") {\n'
                   '    sources = [ "//brave/components/decentralized_dns/core/constants.h" ]\n'
                   '  }\n'
                   '}')
    if text.count(upstream) == 1:
        text = text.replace(upstream, new, 1)
    elif text.count(conditional) == 1:
        text = text.replace(conditional, new, 1)
    else:
        raise RuntimeError("Brave Android enum target anchor changed")
    path.write_text(text, encoding="utf-8")
    print("SANDIUM_WALLET_DNS_ENUM_COMPILE_CONTRACT=APPLIED")

def patch_notifications(path):
    text = path.read_text(encoding="utf-8")
    conditional = ('    deps += [\n'
                   '      "//chrome/browser:browser_process",\n'
                   '      "//chrome/browser:browser_public_dependencies",\n'
                   '    ]\n\n'
                   '    if (enable_brave_wallet) {\n'
                   '      deps += [ "//brave/android:brave_android_java_enums_srcjar" ]\n'
                   '    }')
    unconditional = ('    deps += [\n'
                     '      "//brave/android:brave_android_java_enums_srcjar",\n'
                     '      "//chrome/browser:browser_process",\n'
                     '      "//chrome/browser:browser_public_dependencies",\n'
                     '    ]')
    if unconditional in text and conditional not in text:
        print("SANDIUM_WALLET_NOTIFICATIONS_ENUM_DEP=ALREADY_APPLIED")
        return
    if text.count(conditional) != 1:
        raise RuntimeError("Brave notifications enum dependency anchor changed")
    path.write_text(text.replace(conditional, unconditional, 1), encoding="utf-8")
    print("SANDIUM_WALLET_NOTIFICATIONS_ENUM_DEP=APPLIED")

def patch_srcjar_config(path):
    text = path.read_text(encoding="utf-8")
    new = ('brave_chrome_java_srcjar_deps = [\n'
           '  "//brave/android:brave_android_java_enums_srcjar",\n'
           '  "//brave/components/brave_wallet/common:mojom",\n'
           '  "//brave/android:brave_config_java",\n'
           '  "//brave/android:brave_policy_constants_java_srcjar",\n'
           '  "//brave/components/brave_account/android:brave_account_constants_srcjar",\n'
           '  "//brave/components/web_discovery/browser/android:java_pref_names_srcjar",\n'
           ']')
    if new in text:
        print("SANDIUM_WALLET_JAVA_SRCJAR_DEPS=ALREADY_APPLIED")
        return
    conditional = ('brave_chrome_java_srcjar_deps = [\n'
                   '  "//brave/android:brave_config_java",\n'
                   '  "//brave/android:brave_policy_constants_java_srcjar",\n'
                   '  "//brave/components/brave_account/android:brave_account_constants_srcjar",\n'
                   '  "//brave/components/web_discovery/browser/android:java_pref_names_srcjar",\n'
                   ']\n\n'
                   'if (enable_brave_wallet) {\n'
                   '  brave_chrome_java_srcjar_deps += [ "//brave/android:brave_android_java_enums_srcjar" ]\n'
                   '}')
    upstream = ('brave_chrome_java_srcjar_deps = [\n'
                '  "//brave/android:brave_android_java_enums_srcjar",\n'
                '  "//brave/android:brave_config_java",\n'
                '  "//brave/android:brave_policy_constants_java_srcjar",\n'
                '  "//brave/components/brave_account/android:brave_account_constants_srcjar",\n'
                '  "//brave/components/web_discovery/browser/android:java_pref_names_srcjar",\n'
                ']')
    if text.count(conditional) == 1:
        updated = text.replace(conditional, new, 1)
    elif text.count(upstream) == 1:
        updated = text.replace(upstream, new, 1)
    else:
        raise RuntimeError("Brave Chrome Java srcjar dependency anchor changed")
    path.write_text(updated, encoding="utf-8")
    print("SANDIUM_WALLET_JAVA_SRCJAR_DEPS=APPLIED")

def apply(core, src):
    patch_wallet_common(core / "components/brave_wallet/common/BUILD.gn")
    patch_android_enums(core / "android/BUILD.gn")
    patch_notifications(core / "browser/notifications/BUILD.gn")
    patch_srcjar_config(core / "build/android/config.gni")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--core", required=True, type=Path)
    p.add_argument("--src", required=True, type=Path)
    p.add_argument("--skip-pin-check", action="store_true", help=argparse.SUPPRESS)
    a = p.parse_args()
    core, src = a.core.resolve(), a.src.resolve()
    if not a.skip_pin_check:
        brave = subprocess.check_output(["git", "-C", str(core), "rev-parse", "HEAD"], text=True).strip()
        chromium = subprocess.check_output(["git", "-C", str(src), "rev-parse", "HEAD"], text=True).strip()
        if brave != BRAVE_SHA or chromium != CHROMIUM_SHA:
            raise RuntimeError("pin mismatch: brave=%s chromium=%s" % (brave, chromium))
    apply(core, src)
    print("SANDIUM_WALLET_JAVA_COMPILE_CONTRACT=PASS wallet_feature_flag_unchanged=true")
if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("SANDIUM_WALLET_JAVA_COMPILE_CONTRACT=FAIL " + str(exc), file=sys.stderr)
        raise SystemExit(1)
