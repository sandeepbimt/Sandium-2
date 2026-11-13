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

# Exact retired v4 overlay fragments. Cleanup edits only this feature and
# fails closed on unknown remnants instead of resetting shared modified files.
RETIRED_READER = {'resource_line': '    "java/brave-res/raw/sandium_reader_typography.js",\n',
 'imports': 'import java.io.ByteArrayOutputStream;\n'
            'import java.io.IOException;\n'
            'import java.io.InputStream;\n'
            'import java.nio.charset.StandardCharsets;\n',
 'field_anchor': '    private PlaylistService mPlaylistService;\n',
 'field': '    private PlaylistService mPlaylistService;\n'
          '\n'
          '    // SANDIUM_READER_TYPOGRAPHY_BEGIN\n'
          '    private static volatile String sSandiumReaderTypographyScript;\n'
          '    // SANDIUM_READER_TYPOGRAPHY_END\n',
 'method_anchor': '    public void setTabModelSelector(TabModelSelector selector) {\n',
 'method': '    private void applySandiumReaderTypography(Tab tab) {\n'
           '        if (tab == null || tab.getWebContents() == null || tab.getUrl() == null) '
           'return;\n'
           '        String scheme = tab.getUrl().getScheme();\n'
           '        if (!"http".equals(scheme) && !"https".equals(scheme)) return;\n'
           '        try {\n'
           '            String script = sSandiumReaderTypographyScript;\n'
           '            if (script == null) {\n'
           '                synchronized (BraveToolbarLayoutImpl.class) {\n'
           '                    script = sSandiumReaderTypographyScript;\n'
           '                    if (script == null) {\n'
           '                        try (InputStream input = '
           'getContext().getResources().openRawResource(\n'
           '                                R.raw.sandium_reader_typography)) {\n'
           '                            ByteArrayOutputStream output = new '
           'ByteArrayOutputStream();\n'
           '                            byte[] buffer = new byte[8192];\n'
           '                            int count;\n'
           '                            while ((count = input.read(buffer)) != -1) {\n'
           '                                output.write(buffer, 0, count);\n'
           '                            }\n'
           '                            script = new String(output.toByteArray(), '
           'StandardCharsets.UTF_8);\n'
           '                        }\n'
           '                        sSandiumReaderTypographyScript = script;\n'
           '                    }\n'
           '                }\n'
           '            }\n'
           '            tab.getWebContents().evaluateJavaScript(script, null);\n'
           '        } catch (IOException | RuntimeException error) {\n'
           '            Log.w(TAG, "Unable to apply Sandium reader typography", error);\n'
           '        }\n'
           '    }\n'
           '\n'
           '    public void setTabModelSelector(TabModelSelector selector) {\n',
 'load_anchor': '                    public void onPageLoadFinished(final Tab tab, GURL url) {\n',
 'load_new': '                    public void onPageLoadFinished(final Tab tab, GURL url) {\n'
             '                        applySandiumReaderTypography(tab);\n',
 'shown_anchor': '                    public void onShown(Tab tab, @TabSelectionType int type) {\n',
 'shown_new': '                    public void onShown(Tab tab, @TabSelectionType int type) {\n'
              '                        applySandiumReaderTypography(tab);\n'}

def retire_reader(core: Path, repo_root: Path) -> None:
    toolbar = core / "android/java/org/chromium/chrome/browser/toolbar/top/BraveToolbarLayoutImpl.java"
    build = core / "android/BUILD.gn"
    before_toolbar = toolbar.read_text(encoding="utf-8")
    updated = before_toolbar
    for added, original in (("method", "method_anchor"), ("field", "field_anchor"),
                            ("load_new", "load_anchor"), ("shown_new", "shown_anchor")):
        fragment = RETIRED_READER[added]
        if updated.count(fragment) > 1:
            raise SystemExit("SANDIUM_READER_RETIRE=FAIL duplicate " + added)
        updated = updated.replace(fragment, RETIRED_READER[original])
    # These imports were introduced only as a contiguous typography bundle.
    # Preserve any import still required by another feature in the same file.
    for line in RETIRED_READER["imports"].splitlines(keepends=True):
        name = line.strip().removeprefix("import ").removesuffix(";").split(".")[-1]
        without_import = updated.replace(line, "")
        if not re.search(r"\b" + re.escape(name) + r"\b", without_import):
            updated = without_import
    build_text = build.read_text(encoding="utf-8").replace(RETIRED_READER["resource_line"], "")
    for text in (updated, build_text):
        if any(token in text for token in ("sandium_reader_typography", "SandiumReaderTypography", "SANDIUM_READER_TYPOGRAPHY")):
            raise SystemExit("SANDIUM_READER_RETIRE=FAIL unrecognized reader remnants; no source files written")
    if updated != before_toolbar:
        toolbar.write_text(updated, encoding="utf-8")
    if build_text != build.read_text(encoding="utf-8"):
        build.write_text(build_text, encoding="utf-8")
    resource = core / "android/java/brave-res/raw/sandium_reader_typography.js"
    if resource.exists():
        resource.unlink()
    verify_reader_removed(core, repo_root)
    print("SANDIUM_READER_RETIRE=PASS targeted_cleanup=true")

def apply_phase(core: Path, src: Path, out: Path, phase: str) -> None:
    pin_gate(core, src)
    if phase == "retire-reader":
        retire_reader(core, Path(__file__).resolve().parents[2])
        return
    reader_resource = core / "android/java/brave-res/raw/sandium_reader_typography.js"
    if phase == "prepare":
        brave_count = restore_paths(core, BRAVE_RESTORE_PREFIXES, "brave-core")
        chromium_count = restore_paths(src, CHROMIUM_RESTORE_PREFIXES, "chromium")
        # Remove the retired typography resource even from restored checkpoints.
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
    verify_reader_removed(core, Path(__file__).resolve().parents[2])
    print("SANDIUM_VANILLA_VERIFY=PASS ai_chat=upstream wallet=upstream news=upstream reader_typography=removed")


def verify_reader_removed(core: Path, repo_root: Path) -> None:
    resource = "android/java/brave-res/raw/sandium_reader_typography.js"
    if (core / resource).exists() or (repo_root / resource).exists():
        raise SystemExit("SANDIUM_VANILLA_SOURCE_GATE=FAIL retired typography resource remains")
    for relative in ("android/BUILD.gn",
                     "android/java/org/chromium/chrome/browser/toolbar/top/BraveToolbarLayoutImpl.java"):
        path = core / relative
        if not path.is_file():
            raise SystemExit("SANDIUM_VANILLA_SOURCE_GATE=FAIL missing typography removal verification input: " + relative)
        source = path.read_text(encoding="utf-8")
        if any(token in source for token in (
                "sandium_reader_typography", "SandiumReaderTypography",
                "SANDIUM_READER_TYPOGRAPHY", "quetta-reader-typography")):
            raise SystemExit("SANDIUM_VANILLA_SOURCE_GATE=FAIL retired typography integration remains: " + relative)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", required=True, type=Path)
    parser.add_argument("--src", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--phase", required=True, choices=("prepare", "verify", "retire-reader"))
    args = parser.parse_args()
    apply_phase(args.core.resolve(), args.src.resolve(), args.out.resolve(), args.phase)

if __name__ == "__main__":
    main()
