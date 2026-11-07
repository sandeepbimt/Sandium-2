#!/usr/bin/env python3
"""Preflight the empty Brave Wallet java_cpp_enum action against pinned Brave Core."""
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request

BRAVE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
BASE = f"https://raw.githubusercontent.com/brave/brave-core/{BRAVE_SHA}/"

def fetch(path):
    request = urllib.request.Request(BASE + path, headers={"User-Agent": "Sandium-GitHub-Preflight"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")

script = Path(".circleci/scripts/prepare-brave-source.sh").read_text(encoding="utf-8")
marker = """python3 - "$CORE_DIR/android/BUILD.gn" "$CORE_DIR/browser/notifications/BUILD.gn" "$CORE_DIR/build/android/config.gni" <<'PY'
"""
if script.count(marker) != 1:
    raise SystemExit("BRAVE_WALLET_ENUM_PREFLIGHT=FAIL expected exactly one Wallet enum patch heredoc")
body, sep, _ = script.split(marker, 1)[1].partition("\nPY\n")
if not sep:
    raise SystemExit("BRAVE_WALLET_ENUM_PREFLIGHT=FAIL unterminated Wallet enum patch heredoc")

paths = (
    "android/BUILD.gn",
    "browser/notifications/BUILD.gn",
    "build/android/config.gni",
)
original = {name: fetch(name) for name in paths}

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    files = {}
    for name, source in original.items():
        dest = root / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(source, encoding="utf-8")
        files[name] = dest

    args = [sys.executable, "-c", body] + [str(files[name]) for name in paths]

    def apply():
        result = subprocess.run(args, text=True, capture_output=True)
        if result.returncode:
            raise SystemExit("BRAVE_WALLET_ENUM_PREFLIGHT=FAIL patch execution\n" + result.stdout + result.stderr)
        return result.stdout

    first = apply()
    patched = {name: files[name].read_text(encoding="utf-8") for name in paths}

    android = patched["android/BUILD.gn"]
    notifications = patched["browser/notifications/BUILD.gn"]
    config = patched["build/android/config.gni"]

    assert '# SANDIUM_WALLET_DNS_ENUM_COMPILE_CONTRACT_BEGIN' in android
    assert 'java_cpp_enum("brave_android_java_enums_srcjar")' in android
    assert 'if (enable_brave_wallet)' not in android
    assert 'sources = [ "//brave/components/decentralized_dns/core/constants.h" ]' in android
    assert 'deps += [\n      "//brave/android:brave_android_java_enums_srcjar",' in notifications
    assert 'if (enable_brave_wallet)' not in notifications
    assert '"//brave/android:brave_android_java_enums_srcjar",' in config
    assert '"//brave/components/brave_wallet/common:mojom",' in config
    assert 'if (enable_brave_wallet)' not in config[config.index('brave_chrome_java_srcjar_deps = ['):config.index(']', config.index('brave_chrome_java_srcjar_deps = ['))]

    second = apply()
    assert {name: files[name].read_text(encoding="utf-8") for name in paths} == patched
    assert "SANDIUM_BRAVE_WALLET_ENUM_GATE=ALREADY_PATCHED" in second
    assert first.count("SANDIUM_BRAVE_WALLET_ENUM_GATE=PASS") == 1

print("BRAVE_WALLET_ENUM_PREFLIGHT=PASS pinned Brave source, compile-only target and unconditional Java consumers, idempotent rerun")
