#!/usr/bin/env python3
"""Regression test for Brave's always-consumed Java enum srcjar with Wallet disabled."""
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request

BRAVE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
CHROMIUM_SHA = "d331de35ca8ab1358c7a17e4bd41627d55eaef51"

def fetch(repo, sha, path):
    url = f"https://raw.githubusercontent.com/{repo}/{sha}/{path}"
    request = urllib.request.Request(url, headers={"User-Agent": "Sandium-GitHub-Preflight"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")

script = Path(".circleci/scripts/prepare-brave-source.sh").read_text(encoding="utf-8")
marker = "python3 - \"$CORE_DIR/android/BUILD.gn\" \"$CORE_DIR/android/sandium_empty_java_enum_input.h\" <<'PY'\n"
if script.count(marker) != 1:
    raise SystemExit("JAVA_ENUM_PREFLIGHT=FAIL expected exactly one enum-input patch heredoc")
tail = script.split(marker, 1)[1]
body, sep, _ = tail.partition("\nPY\n")
if not sep:
    raise SystemExit("JAVA_ENUM_PREFLIGHT=FAIL unterminated enum-input patch heredoc")

build_gn = fetch("brave/brave-core", BRAVE_SHA, "android/BUILD.gn")
rules_gni = fetch("chromium/chromium", CHROMIUM_SHA, "build/config/android/rules.gni")
generator = fetch("chromium/chromium", CHROMIUM_SHA, "build/android/gyp/java_cpp_enum.py")
if 'java_cpp_enum("brave_android_java_enums_srcjar") {' not in build_gn:
    raise SystemExit("JAVA_ENUM_PREFLIGHT=FAIL pinned Brave enum target missing")
if 'if (enable_brave_wallet)' not in build_gn or '"//brave/components/decentralized_dns/core/constants.h"' not in build_gn:
    raise SystemExit("JAVA_ENUM_PREFLIGHT=FAIL pinned Wallet enum source condition changed")
if 'args = [ "--srcjar=$_rebased_srcjar_path" ] + _rebased_sources' not in rules_gni:
    raise SystemExit("JAVA_ENUM_PREFLIGHT=FAIL Chromium java_cpp_enum no longer forwards sources as input paths")
if "parser.add_argument(\n        'input_paths', nargs='+'," not in generator:
    raise SystemExit("JAVA_ENUM_PREFLIGHT=FAIL pinned generator input_paths contract changed")

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp) / "brave"
    android = root / "android"
    android.mkdir(parents=True)
    build_file = android / "BUILD.gn"
    empty_header = android / "sandium_empty_java_enum_input.h"
    build_file.write_text(build_gn, encoding="utf-8")

    def apply_patch():
        result = subprocess.run(
            [sys.executable, "-c", body, str(build_file), str(empty_header)],
            text=True, capture_output=True,
        )
        if result.returncode:
            raise SystemExit("JAVA_ENUM_PREFLIGHT=FAIL patch execution failed\n" + result.stdout + result.stderr)
        return result.stdout

    first = apply_patch()
    patched = build_file.read_text(encoding="utf-8")
    header = empty_header.read_text(encoding="utf-8")
    target_start = patched.index('java_cpp_enum("brave_android_java_enums_srcjar") {')
    target_end = patched.index('\n}\n\njava_cpp_template("brave_config_java") {', target_start)
    target = patched[target_start:target_end + 2]
    fallback = 'sources += [ "//brave/android/sandium_empty_java_enum_input.h" ]'
    wallet = 'sources += [ "//brave/components/decentralized_dns/core/constants.h" ]'
    if target.count(fallback) != 1 or target.count(wallet) != 1 or target.count("} else {") != 1 or "}\\n  } else {" in target:
        raise SystemExit("JAVA_ENUM_PREFLIGHT=FAIL expected exactly one disabled-Wallet fallback and original Wallet source")
    if "GENERATED_JAVA_ENUM_PACKAGE" in header or not header.endswith("\n"):
        raise SystemExit("JAVA_ENUM_PREFLIGHT=FAIL fallback header is not a newline-terminated no-enum header")
    if "SANDIUM_BRAVE_ENUM_INPUT_GATE=PASS" not in first:
        raise SystemExit("JAVA_ENUM_PREFLIGHT=FAIL runtime patch gate did not report PASS")

    second = apply_patch()
    if build_file.read_text(encoding="utf-8") != patched:
        raise SystemExit("JAVA_ENUM_PREFLIGHT=FAIL second patch run changed BUILD.gn")
    if "SANDIUM_BRAVE_ENUM_INPUT_GATE=ALREADY_PATCHED" not in second:
        raise SystemExit("JAVA_ENUM_PREFLIGHT=FAIL patch is not idempotent")

print("JAVA_ENUM_PREFLIGHT=PASS pinned Brave target has a real non-empty input when Wallet is disabled; Chromium forwards it to required input_paths; patch is idempotent")
