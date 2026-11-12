#!/usr/bin/env python3
"""Restore/verify pinned vanilla Brave components before Sandium's approved overlays.

The 26 GiB continuation checkpoint can contain tracked edits from older Sandium
feature-disable experiments. This gate returns those paths to the pinned Brave
HEAD, clears only explicit AI Chat/Wallet/News GN overrides, and verifies that
the approved welcome/filter/transition overlays have not modified those paths.
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

EXPECTED_CORE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
EXPECTED_CHROMIUM_SHA = "d331de35ca8ab1358c7a17e4bd41627d55eaef51"

# Paths touched by previous Sandium feature-disable, News/Wallet dependency,
# Reader Typography, and Morphe overlays. Reset them before regenerating GN.
BRAVE_RESTORE_PREFIXES = (
    "components/ai_chat",
    "browser/ai_chat",
    "components/brave_wallet",
    "browser/brave_wallet",
    "components/brave_news",
    "browser/brave_news",
    "components/p3a/p3a_service.cc",
    "browser/brave_local_state_prefs.cc",
    "browser/brave_stats/brave_stats_updater.cc",
    "components/web_discovery/buildflags/buildflags.gni",
    "browser/android/BUILD.gn",
    "browser/android/brave_tab_features.cc",
    "browser/android/brave_tab_features.h",
    "components/playlist/core/browser/utils.cc",
    "browser/playlist/playlist_service_factory.cc",
    "android/android_browser_tests.gni",
    "android/java/brave-res/xml/brave_main_preferences.xml",
    "android/BUILD.gn",
    "android/java/org/chromium/chrome/browser/toolbar/top/BraveToolbarLayoutImpl.java",
    "browser/android/preferences/BUILD.gn",
    "build/android/config.gni",
    "browser/notifications/BUILD.gn",
    "browser/ui/android/theme/java/src/org/chromium/chrome/browser/theme/BraveDynamicColors.java",
)
CHROMIUM_RESTORE_PREFIXES = (
    "chrome/browser/partnercustomizations/java/src/org/chromium/chrome/browser/partnercustomizations/PartnerBrowserCustomizations.java",
)

# android/BUILD.gn is deliberately restored but later receives the approved
# transition icon resource entries. It is checked separately below.
# Final integrity check is deliberately limited to upstream feature
# implementations and their Android linkage. Approved Sandium UI, branding,
# privacy, transition and first-run overlays legitimately modify other files.
BRAVE_VERIFY_PREFIXES = (
    "components/ai_chat",
    "browser/ai_chat",
    "components/brave_wallet",
    "browser/brave_wallet",
    "components/brave_vpn",
    "browser/brave_vpn",
    "components/brave_news",
    "browser/brave_news",
    "components/brave_rewards",
    "browser/brave_rewards",
    "browser/android/BUILD.gn",
    "browser/android/brave_tab_features.cc",
    "browser/android/brave_tab_features.h",
)
GN_OVERRIDE_KEYS = ("enable_ai_chat", "enable_brave_wallet", "enable_brave_news")
GN_OVERRIDE_RE = re.compile(r"^\s*(enable_ai_chat|enable_brave_wallet|enable_brave_news)\s*=.*(?:\n|$)")

def run_git(repo: Path, *args: str, capture: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    return result.stdout if capture else ""

def pin_gate(core: Path, src: Path) -> None:
    core_sha = run_git(core, "rev-parse", "HEAD").strip()
    src_sha = run_git(src, "rev-parse", "HEAD").strip()
    if core_sha != EXPECTED_CORE_SHA or src_sha != EXPECTED_CHROMIUM_SHA:
        raise SystemExit(
            "SANDIUM_VANILLA_PIN_GATE=FAIL "
            f"brave={core_sha} chromium={src_sha}"
        )
    print(f"SANDIUM_VANILLA_PIN_GATE=PASS brave={core_sha} chromium={src_sha}")

def matches_prefix(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path == prefix or path.startswith(prefix.rstrip("/") + "/")
               for prefix in prefixes)

def tracked_matching(repo: Path, prefixes: tuple[str, ...]) -> list[str]:
    tracked = run_git(repo, "ls-files", "-z").split("\0")
    return sorted(path for path in tracked if path and matches_prefix(path, prefixes))

def untracked_matching(repo: Path, prefixes: tuple[str, ...]) -> list[str]:
    untracked = run_git(repo, "ls-files", "--others", "--exclude-standard", "-z").split("\0")
    return sorted(path for path in untracked if path and matches_prefix(path, prefixes))

def restore_paths(repo: Path, prefixes: tuple[str, ...], label: str) -> int:
    paths = tracked_matching(repo, prefixes)
    if paths:
        run_git(repo, "restore", "--source=HEAD", "--staged", "--worktree", "--", *paths)

    # Continuation checkpoints can retain files created by older overlays even
    # when those paths are no longer present in the current index. If HEAD owns
    # the path, restore the pinned upstream file rather than leaving a stale
    # untracked replacement in the source tree.
    untracked = untracked_matching(repo, prefixes)
    restored_untracked = []
    for path in untracked:
        exists_in_head = subprocess.run(
            ["git", "-C", str(repo), "cat-file", "-e", f"HEAD:{path}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
        if exists_in_head:
            run_git(repo, "restore", "--source=HEAD", "--worktree", "--", path)
            restored_untracked.append(path)
        else:
            raise SystemExit(
                f"SANDIUM_VANILLA_RESTORE=FAIL {label} unexpected_untracked={path}; "
                "refusing to delete a path not owned by pinned HEAD"
            )

    remaining = run_git(repo, "diff", "--name-only", "HEAD", "--", *paths).splitlines()
    still_untracked = untracked_matching(repo, prefixes)
    if remaining or still_untracked:
        raise SystemExit(
            f"SANDIUM_VANILLA_RESTORE=FAIL {label} remaining={remaining[:20]} "
            f"untracked={still_untracked[:20]}"
        )
    print(
        f"SANDIUM_VANILLA_RESTORE=PASS tree={label} tracked_paths={len(paths)} "
        f"recovered_untracked={len(restored_untracked)}"
    )
    return len(paths) + len(restored_untracked)

def strip_gn_overrides_text(source: str) -> str:
    return "".join(line for line in source.splitlines(keepends=True)
                   if not GN_OVERRIDE_RE.match(line))

def has_gn_overrides(source: str) -> list[str]:
    return [line.strip() for line in source.splitlines()
            if GN_OVERRIDE_RE.match(line)]

def clean_gn_args(out: Path) -> None:
    for name in ("args.gn", "args_generated.gni"):
        path = out / name
        if not path.is_file():
            continue
        before = path.read_text(encoding="utf-8")
        after = strip_gn_overrides_text(before)
        if after != before:
            path.write_text(after, encoding="utf-8")
        remaining = has_gn_overrides(path.read_text(encoding="utf-8"))
        if remaining:
            raise SystemExit(
                f"SANDIUM_VANILLA_GN_GATE=FAIL {name} retains feature overrides: {remaining}"
            )
    print("SANDIUM_VANILLA_GN_GATE=PASS explicit AI_CHAT/WALLET/NEWS overrides absent")

def verify_repo_clean(repo: Path, prefixes: tuple[str, ...], label: str) -> None:
    tracked = tracked_matching(repo, prefixes)
    changed = run_git(repo, "diff", "--name-only", "HEAD", "--", *tracked).splitlines() if tracked else []
    untracked = untracked_matching(repo, prefixes)
    if changed or untracked:
        raise SystemExit(
            f"SANDIUM_VANILLA_SOURCE_GATE=FAIL tree={label} "
            f"modified={changed[:20]} untracked={untracked[:20]}"
        )
    print(f"SANDIUM_VANILLA_SOURCE_GATE=PASS tree={label} paths={len(tracked)}")

def apply_phase(core: Path, src: Path, out: Path, phase: str) -> None:
    pin_gate(core, src)
    reader_resource = core / "android/java/brave-res/raw/sandium_reader_typography.js"
    if phase == "prepare":
        brave_count = restore_paths(core, BRAVE_RESTORE_PREFIXES, "brave-core")
        chromium_count = restore_paths(src, CHROMIUM_RESTORE_PREFIXES, "chromium")
        # Clear any checkpoint copy; the approved Full Mode overlay will restore the repository-supplied v4 resource.
        if reader_resource.exists():
            reader_resource.unlink()
            print("SANDIUM_VANILLA_RESTORE=PASS retired_reader_resource_removed")
        clean_gn_args(out)
        verify_repo_clean(core, BRAVE_VERIFY_PREFIXES, "brave-core")
        verify_repo_clean(src, CHROMIUM_RESTORE_PREFIXES, "chromium")
        print(f"SANDIUM_VANILLA_PREPARE=PASS brave_restored={brave_count} chromium_restored={chromium_count}")
        return

    verify_repo_clean(core, BRAVE_VERIFY_PREFIXES, "brave-core")
    # The Android source-preparation/build tooling can rewrite Chromium's
    # PartnerBrowserCustomizations.java after the initial checkpoint restore.
    # No Sandium overlay owns this file; restore this exact pinned upstream
    # file immediately before the final integrity check rather than accepting
    # or silently allowlisting a modified Chromium source file.
    restore_paths(src, CHROMIUM_RESTORE_PREFIXES, "chromium-final-upstream")
    verify_repo_clean(src, CHROMIUM_RESTORE_PREFIXES, "chromium")
    clean_gn_args(out)
    # Universal Reader Typography is an approved #850 feature, not a retired
    # experiment. Require the exact repository-supplied v4 resource, its GN
    # registration, and the toolbar injection that consumes it.
    repo_root = Path(__file__).resolve().parents[2]
    supplied_resource = repo_root / "android/java/brave-res/raw/sandium_reader_typography.js"
    android_build = core / "android/BUILD.gn"
    toolbar = core / "android/java/org/chromium/chrome/browser/toolbar/top/BraveToolbarLayoutImpl.java"
    if not supplied_resource.is_file() or not reader_resource.is_file():
        raise SystemExit("SANDIUM_VANILLA_SOURCE_GATE=FAIL approved Universal Reader Typography resource missing")
    if reader_resource.read_bytes() != supplied_resource.read_bytes():
        raise SystemExit("SANDIUM_VANILLA_SOURCE_GATE=FAIL Reader Typography resource differs from repository v4 source")
    if not android_build.is_file() or '"java/brave-res/raw/sandium_reader_typography.js"' not in android_build.read_text(encoding="utf-8"):
        raise SystemExit("SANDIUM_VANILLA_SOURCE_GATE=FAIL Reader Typography raw resource is not registered")
    if not toolbar.is_file():
        raise SystemExit("SANDIUM_VANILLA_SOURCE_GATE=FAIL Reader Typography toolbar integration is missing")
    toolbar_text = toolbar.read_text(encoding="utf-8")
    required_reader_hooks = (
        "private void applySandiumReaderTypography(Tab tab)",
        "R.raw.sandium_reader_typography",
        "applySandiumReaderTypography(tab);",
    )
    missing_reader_hooks = [item for item in required_reader_hooks if item not in toolbar_text]
    if missing_reader_hooks:
        raise SystemExit("SANDIUM_VANILLA_SOURCE_GATE=FAIL Reader Typography integration incomplete: " + repr(missing_reader_hooks))
    print("SANDIUM_VANILLA_VERIFY=PASS ai_chat=upstream wallet=upstream news=upstream reader_typography=approved_v4")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", required=True, type=Path)
    parser.add_argument("--src", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--phase", required=True, choices=("prepare", "verify"))
    args = parser.parse_args()
    apply_phase(args.core.resolve(), args.src.resolve(), args.out.resolve(), args.phase)

if __name__ == "__main__":
    main()
