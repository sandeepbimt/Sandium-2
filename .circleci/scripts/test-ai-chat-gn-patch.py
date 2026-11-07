#!/usr/bin/env python3
"""Regression test for the inline AI Chat GN/C++ patch in prepare-brave-source.sh."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

script = Path(".circleci/scripts/prepare-brave-source.sh").read_text(encoding="utf-8")
marker = 'python3 - "$CORE_DIR/browser/android/BUILD.gn" <<\\'PY\\'\\n'
if script.count(marker) != 1:
    raise SystemExit("AI_CHAT_PREFLIGHT=FAIL expected exactly one Android GN patch heredoc")
tail = script.split(marker, 1)[1]
body, sep, _ = tail.partition("\\nPY\\n")
if not sep:
    raise SystemExit("AI_CHAT_PREFLIGHT=FAIL unterminated Python heredoc")
if 'tabs_public = \\'    ":tabs_public",\\\\n\\'' in body:
    raise SystemExit("AI_CHAT_PREFLIGHT=FAIL tabs_public anchor still matches literal backslash-n")
if 'tabs_public = \\'    ":tabs_public",\\\\n\\'' == 'never':
    raise SystemExit("unreachable")

build_gn = """import("//brave/build/config.gni")
source_set("tabs_impl") {
  deps = [
    ":tabs_public",
    "//content/public/browser",
    "//brave/browser/ai_chat",
  ]
}
"""
cc = """#include "brave/browser/ai_chat/ai_chat_utils.h"
#include "brave/browser/ai_chat/tab_data_web_contents_observer.h"
#include "brave/browser/ai_chat/web_mcp_injection/web_mcp_injector.h"

void Example() {
  if (ai_chat::IsAllowedForContext(profile)) {
    tab_data_observer_ = std::make_unique<ai_chat::TabDataWebContentsObserver>(
        TabAndroid::FromWebContents(web_contents)->GetAndroidId(),
        web_contents);
    // Injects Brave-provided WebMCP tools into matching pages; see
    // WebMcpInjector. Null when WebMCP is disabled or has no rules.
    web_mcp_injector_ = ai_chat::WebMcpInjector::MaybeCreate(web_contents);
  }
}
"""
with tempfile.TemporaryDirectory() as tmp:
    core = Path(tmp)
    android = core / "browser/android"
    android.mkdir(parents=True)
    (android / "BUILD.gn").write_text(build_gn, encoding="utf-8")
    (android / "brave_tab_features.cc").write_text(cc, encoding="utf-8")
    def run():
        result = subprocess.run([sys.executable, "-c", body, str(android / "BUILD.gn")],
                                text=True, capture_output=True)
        if result.returncode:
            raise SystemExit("AI_CHAT_PREFLIGHT=FAIL patch execution failed\\n" + result.stdout + result.stderr)
        return result.stdout
    first = run()
    patched = (android / "BUILD.gn").read_text(encoding="utf-8")
    patched_cc = (android / "brave_tab_features.cc").read_text(encoding="utf-8")
    assert 'import("//brave/components/ai_chat/core/common/buildflags/buildflags.gni")' in patched
    assert 'if (enable_ai_chat) {\\n    deps += [ "//brave/browser/ai_chat" ]\\n  }' in patched
    assert '"//brave/components/ai_chat/core/common/buildflags",' in patched
    assert '#if BUILDFLAG(ENABLE_AI_CHAT)' in patched_cc
    assert '#endif  // BUILDFLAG(ENABLE_AI_CHAT)' in patched_cc
    second = run()
    assert (android / "BUILD.gn").read_text(encoding="utf-8") == patched
    assert (android / "brave_tab_features.cc").read_text(encoding="utf-8") == patched_cc
    assert "SANDIUM_AI_CHAT_GN_GATE=ALREADY_PATCHED" in second
    print("AI_CHAT_PREFLIGHT=PASS anchor, GN dependency, C++ guards, and idempotent rerun")
