#!/usr/bin/env python3
"""Guard Brave News Android preference dependency when Brave News is disabled."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

BRAVE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
CHROMIUM_SHA = "d331de35ca8ab1358c7a17e4bd41627d55eaef51"
BUILD_FILE = Path("browser/android/preferences/BUILD.gn")
FLAGS_FILE = Path("components/brave_news/common/buildflags/buildflags.gni")
WALLET_FLAGS_FILE = Path("components/brave_wallet/common/buildflags/buildflags.gni")
JAVA_CONFIG_FILE = Path("build/android/config.gni")
NOTIFICATIONS_FILE = Path("browser/notifications/BUILD.gn")
ENUM_TARGET = '"//brave/android:brave_android_java_enums_srcjar"'
ENUM_DEP = ENUM_TARGET + ','
WALLET_CONDITIONAL_CONFIG = """if (enable_brave_wallet) {\n  brave_chrome_java_srcjar_deps += [ "//brave/android:brave_android_java_enums_srcjar" ]\n}"""
WALLET_CONDITIONAL_NOTIFICATIONS = """    if (enable_brave_wallet) {\n      deps += [ "//brave/android:brave_android_java_enums_srcjar" ]\n    }"""
IMPORT = 'import("//brave/components/brave_news/common/buildflags/buildflags.gni")'
UNCONDITIONAL_DEP = '"//brave/components/brave_news/common",'
CONDITIONAL_DEP = """  if (enable_brave_news) {
    deps += [ "//brave/components/brave_news/common" ]
  }"""

def transform(source: str) -> str:
    if IMPORT not in source:
        # Keep the existing imports and insert after the last import at file scope.
        lines = source.splitlines(keepends=True)
        import_indexes = [i for i, line in enumerate(lines) if line.startswith("import(")]
        if not import_indexes:
            raise RuntimeError("SANDIUM_NEWS_GN: no top-level import anchor")
        lines.insert(import_indexes[-1] + 1, IMPORT + "\n")
        source = "".join(lines)
    if source.count(IMPORT) != 1:
        raise RuntimeError("SANDIUM_NEWS_GN: expected exactly one Brave News buildflags import")

    if CONDITIONAL_DEP in source and UNCONDITIONAL_DEP not in source:
        return source

    if source.count(UNCONDITIONAL_DEP) != 1:
        raise RuntimeError(
            "SANDIUM_NEWS_GN: expected exactly one unconditional Brave News preference dependency"
        )
    source = source.replace(UNCONDITIONAL_DEP, "", 1)

    marker = "\n}\n\njava_cpp_strings(\"java_pref_names_srcjar\")"
    if source.count(marker) != 1:
        raise RuntimeError("SANDIUM_NEWS_GN: preferences source_set end anchor changed")
    source = source.replace(marker, "\n" + CONDITIONAL_DEP + marker, 1)

    if UNCONDITIONAL_DEP in source or source.count(CONDITIONAL_DEP) != 1:
        raise RuntimeError("SANDIUM_NEWS_GN: conditional dependency verification failed")
    return source

def transform_wallet_config(source: str) -> str:
    """Do not schedule the empty wallet enum srcjar when Brave Wallet is disabled."""
    if WALLET_CONDITIONAL_CONFIG in source and source.count(ENUM_TARGET) == 1:
        return source
    if source.count(ENUM_DEP) != 1:
        raise RuntimeError("SANDIUM_WALLET_GN: expected one unconditional enum srcjar dependency in config.gni")
    source = source.replace(ENUM_DEP + "\n", "", 1)
    marker = "\n]\n\nbrave_chrome_app_java_resources_deps = ["
    if source.count(marker) != 1:
        raise RuntimeError("SANDIUM_WALLET_GN: config.gni srcjar dependency list anchor changed")
    source = source.replace(
        marker,
        "\n]\n\n" + WALLET_CONDITIONAL_CONFIG + "\n\nbrave_chrome_app_java_resources_deps = [",
        1,
    )
    if source.count(ENUM_TARGET) != 1 or source.count(WALLET_CONDITIONAL_CONFIG) != 1:
        raise RuntimeError("SANDIUM_WALLET_GN: config.gni conditional dependency verification failed")
    return source


def transform_wallet_notifications(source: str) -> str:
    """Keep the enum srcjar out of Android notifications when Wallet is disabled."""
    if WALLET_CONDITIONAL_NOTIFICATIONS in source and source.count(ENUM_TARGET) == 1:
        return source
    if source.count(ENUM_DEP) != 1:
        raise RuntimeError("SANDIUM_WALLET_GN: expected one unconditional enum srcjar dependency in notifications")
    source = source.replace(ENUM_DEP + "\n", "", 1)
    marker = '      "//chrome/browser:browser_public_dependencies",\n    ]'
    if source.count(marker) != 1:
        raise RuntimeError("SANDIUM_WALLET_GN: notifications Android deps anchor changed")
    source = source.replace(
        marker,
        marker + "\n" + WALLET_CONDITIONAL_NOTIFICATIONS,
        1,
    )
    if source.count(ENUM_TARGET) != 1 or source.count(WALLET_CONDITIONAL_NOTIFICATIONS) != 1:
        raise RuntimeError("SANDIUM_WALLET_GN: notifications conditional dependency verification failed")
    return source


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", required=True, type=Path)
    parser.add_argument("--src", required=True, type=Path)
    args = parser.parse_args()
    core, src = args.core.resolve(), args.src.resolve()

    brave_sha = subprocess.check_output(
        ["git", "-C", str(core), "rev-parse", "HEAD"], text=True
    ).strip()
    chromium_sha = subprocess.check_output(
        ["git", "-C", str(src), "rev-parse", "HEAD"], text=True
    ).strip()
    if brave_sha != BRAVE_SHA or chromium_sha != CHROMIUM_SHA:
        raise SystemExit(
            "SANDIUM_NEWS_GN_PIN_GATE=FAIL "
            f"brave={brave_sha} chromium={chromium_sha}"
        )

    flags = core / FLAGS_FILE
    if not flags.is_file() or "enable_brave_news = !is_brave_origin_branded" not in flags.read_text(encoding="utf-8"):
        raise SystemExit("SANDIUM_NEWS_GN=FAIL pinned Brave News flag declaration changed")

    path = core / BUILD_FILE
    if not path.is_file():
        raise SystemExit(f"SANDIUM_NEWS_GN=FAIL missing {path}")
    before = path.read_text(encoding="utf-8")
    after = transform(before)
    if after != before:
        path.write_text(after, encoding="utf-8")
    if path.read_text(encoding="utf-8") != after:
        raise SystemExit("SANDIUM_NEWS_GN=FAIL post-write verification failed")

    wallet_flags = core / WALLET_FLAGS_FILE
    expected_wallet_flag = "enable_brave_wallet = !is_brave_origin_branded"
    if not wallet_flags.is_file() or expected_wallet_flag not in wallet_flags.read_text(encoding="utf-8"):
        raise SystemExit("SANDIUM_WALLET_GN=FAIL pinned Brave Wallet flag declaration changed")

    for relative_path, transformer, label in (
        (JAVA_CONFIG_FILE, transform_wallet_config, "java-config"),
        (NOTIFICATIONS_FILE, transform_wallet_notifications, "notifications"),
    ):
        target = core / relative_path
        if not target.is_file():
            raise SystemExit(f"SANDIUM_WALLET_GN=FAIL missing {target}")
        original = target.read_text(encoding="utf-8")
        patched = transformer(original)
        if patched != original:
            target.write_text(patched, encoding="utf-8")
        if target.read_text(encoding="utf-8") != patched:
            raise SystemExit(f"SANDIUM_WALLET_GN=FAIL {label} post-write verification failed")

    print(f"SANDIUM_NEWS_GN_PIN_GATE=PASS brave={brave_sha} chromium={chromium_sha}")
    print("SANDIUM_NEWS_ANDROID_PREFERENCES_DEP=CONDITIONAL enable_brave_news")
    print("SANDIUM_NEWS_GN=PASS")
    print("SANDIUM_WALLET_ENUM_DEPENDENCIES=CONDITIONAL enable_brave_wallet")
    print("SANDIUM_WALLET_GN=PASS")

if __name__ == "__main__":
    main()
