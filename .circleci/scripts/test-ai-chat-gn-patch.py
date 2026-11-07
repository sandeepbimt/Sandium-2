#!/usr/bin/env python3
"""Test the AI Chat patch against the exact pinned Brave Core source files."""
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
marker = "python3 - \"$CORE_DIR/browser/android/BUILD.gn\" <<'PY'\n"
if script.count(marker) != 1:
    raise SystemExit("AI_CHAT_PREFLIGHT=FAIL expected exactly one Android GN patch heredoc")
tail = script.split(marker, 1)[1]
body, sep, _ = tail.partition("\nPY\n")
if not sep:
    raise SystemExit("AI_CHAT_PREFLIGHT=FAIL unterminated Python heredoc")
if r'''tabs_public = '    ":tabs_public",\\n' '''.strip() in body:
    raise SystemExit("AI_CHAT_PREFLIGHT=FAIL tabs_public anchor contains a double-escaped newline")

build_gn = fetch("browser/android/BUILD.gn")
cc = fetch("browser/android/brave_tab_features.cc")
buildflags = fetch("components/ai_chat/core/common/buildflags/BUILD.gn")
if 'source_set("tabs_impl") {' not in build_gn:
    raise SystemExit("AI_CHAT_PREFLIGHT=FAIL pinned Brave tabs_impl target missing")
if '"//brave/browser/ai_chat",' not in build_gn:
    raise SystemExit("AI_CHAT_PREFLIGHT=FAIL pinned Brave unconditional AI Chat dependency missing")
if '":tabs_public",' not in build_gn or '"//content/public/browser",' not in build_gn:
    raise SystemExit("AI_CHAT_PREFLIGHT=FAIL pinned Brave dependency anchors changed")
if 'buildflag_header("buildflags")' not in buildflags:
    raise SystemExit("AI_CHAT_PREFLIGHT=FAIL pinned AI Chat buildflags target missing")
for include in (
    '#include "brave/browser/ai_chat/ai_chat_utils.h"',
    '#include "brave/browser/ai_chat/tab_data_web_contents_observer.h"',
    '#include "brave/browser/ai_chat/web_mcp_injection/web_mcp_injector.h"',
):
    if include not in cc:
        raise SystemExit("AI_CHAT_PREFLIGHT=FAIL pinned Brave C++ include anchor missing: " + include)

with tempfile.TemporaryDirectory() as tmp:
    android = Path(tmp) / "browser/android"
    android.mkdir(parents=True)
    build_file = android / "BUILD.gn"
    cc_file = android / "brave_tab_features.cc"
    build_file.write_text(build_gn, encoding="utf-8")
    cc_file.write_text(cc, encoding="utf-8")

    def run_patch():
        result = subprocess.run([sys.executable, "-c", body, str(build_file)],
                                text=True, capture_output=True)
        if result.returncode:
            raise SystemExit("AI_CHAT_PREFLIGHT=FAIL patch execution failed\n" + result.stdout + result.stderr)
        return result.stdout

    first = run_patch()
    patched = build_file.read_text(encoding="utf-8")
    patched_cc = cc_file.read_text(encoding="utf-8")
    assert 'import("//brave/components/ai_chat/core/common/buildflags/buildflags.gni")' in patched
    assert 'if (enable_ai_chat) {\n    deps += [ "//brave/browser/ai_chat" ]\n  }' in patched
    assert '"//brave/components/ai_chat/core/common/buildflags",' in patched
    assert '#if BUILDFLAG(ENABLE_AI_CHAT)' in patched_cc
    assert '#endif  // BUILDFLAG(ENABLE_AI_CHAT)' in patched_cc
    assert patched_cc.count('#if BUILDFLAG(ENABLE_AI_CHAT)') == 2

    second = run_patch()
    assert build_file.read_text(encoding="utf-8") == patched
    assert cc_file.read_text(encoding="utf-8") == patched_cc
    assert "SANDIUM_AI_CHAT_GN_GATE=ALREADY_PATCHED" in second
    assert "SANDIUM_AI_CHAT_CPP_GATE=ALREADY_PATCHED includes" in second
    assert "SANDIUM_AI_CHAT_CPP_GATE=ALREADY_PATCHED calls" in second

print("AI_CHAT_PREFLIGHT=PASS pinned Brave source, GN target/dependency, C++ guards, and idempotent rerun")
