#!/usr/bin/env python3
"""Preflight the pinned Brave Android AI Chat-off compilation guards."""
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request

BRAVE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
BASE = f"https://raw.githubusercontent.com/brave/brave-core/{BRAVE_SHA}/"
FILES = {
    "brave_tab_features.h": "browser/android/brave_tab_features.h",
    "brave_tab_features.cc": "browser/android/brave_tab_features.cc",
    "BUILD.gn": "browser/android/BUILD.gn",
}

def fetch(path):
    request = urllib.request.Request(BASE + path, headers={"User-Agent": "Sandium-GitHub-Preflight"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")

script = Path(".circleci/scripts/prepare-brave-source.sh").read_text(encoding="utf-8")
marker = 'python3 - "$CORE_DIR/browser/android/brave_tab_features.h" "$CORE_DIR/browser/android/brave_tab_features.cc" "$CORE_DIR/browser/android/BUILD.gn" <<\'PY\'\n'
if script.count(marker) != 1:
    raise SystemExit("AI_CHAT_ANDROID_PREFLIGHT=FAIL expected exactly one Android gate heredoc")
body, separator, _ = script.split(marker, 1)[1].partition("\nPY\n")
if not separator:
    raise SystemExit("AI_CHAT_ANDROID_PREFLIGHT=FAIL unterminated Android gate heredoc")

with tempfile.TemporaryDirectory() as tmp:
    core = Path(tmp)
    android = core / "browser" / "android"
    android.mkdir(parents=True)
    for local, remote in FILES.items():
        (android / local).write_text(fetch(remote), encoding="utf-8")

    def apply():
        result = subprocess.run(
            [sys.executable, "-c", body,
             str(android / "brave_tab_features.h"),
             str(android / "brave_tab_features.cc"),
             str(android / "BUILD.gn")],
            text=True, capture_output=True
        )
        if result.returncode:
            raise SystemExit("AI_CHAT_ANDROID_PREFLIGHT=FAIL patch execution\n"
                             + result.stdout + result.stderr)
        return result.stdout

    first = apply()
    header = (android / "brave_tab_features.h").read_text(encoding="utf-8")
    cc = (android / "brave_tab_features.cc").read_text(encoding="utf-8")
    build = (android / "BUILD.gn").read_text(encoding="utf-8")

    assert '#if BUILDFLAG(ENABLE_AI_CHAT)\nnamespace ai_chat {' in header
    assert '#if BUILDFLAG(ENABLE_AI_CHAT)\n  std::unique_ptr<ai_chat::TabDataWebContentsObserver>' in header
    assert '#if BUILDFLAG(ENABLE_AI_CHAT)\n#include "brave/browser/ai_chat/ai_chat_utils.h"' in cc
    assert '#if BUILDFLAG(ENABLE_AI_CHAT)\n  if (ai_chat::IsAllowedForContext(profile)) {' in cc
    assert 'import("//brave/components/ai_chat/core/common/buildflags/buildflags.gni")' in build
    assert 'if (enable_ai_chat) {\n    deps += [ "//brave/browser/ai_chat" ]\n  }' in build
    assert build.count('"//brave/browser/ai_chat"') == 1

    snapshot = (header, cc, build)
    second = apply()
    assert snapshot == (
        (android / "brave_tab_features.h").read_text(encoding="utf-8"),
        (android / "brave_tab_features.cc").read_text(encoding="utf-8"),
        (android / "BUILD.gn").read_text(encoding="utf-8"),
    ), "AI Chat Android patch is not idempotent"
    assert "SANDIUM_AI_CHAT_ANDROID_GATE=PASS" in first
    assert "SANDIUM_AI_CHAT_ANDROID_GATE=PASS" in second

print("AI_CHAT_ANDROID_PREFLIGHT=PASS pinned Brave v1.98.62 Android header, implementation and GN guards; idempotent rerun")
