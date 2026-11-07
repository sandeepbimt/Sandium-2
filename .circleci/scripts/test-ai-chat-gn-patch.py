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


# The Android mobile-subscription renderer is another unconditional consumer
# of AI Chat common: it injects Leo purchase callbacks. Verify that the second
# source patch removes that dependency when the buildflag is false and guards
# every AI Chat type/symbol at the C++ boundary.
subscription_marker = (
    'python3 - "$CORE_DIR/components/brave_mobile_subscription/renderer/android/BUILD.gn" '
    '"$CORE_DIR/components/brave_mobile_subscription/renderer/android/subscription_render_frame_observer.h" '
    '"$CORE_DIR/components/brave_mobile_subscription/renderer/android/subscription_render_frame_observer.cc" <<\'PY\'\n'
)
if script.count(subscription_marker) != 1:
    raise SystemExit("AI_CHAT_PREFLIGHT=FAIL expected exactly one mobile-subscription patch heredoc")
subscription_tail = script.split(subscription_marker, 1)[1]
subscription_body, subscription_sep, _ = subscription_tail.partition("\nPY\n")
if not subscription_sep:
    raise SystemExit("AI_CHAT_PREFLIGHT=FAIL unterminated mobile-subscription patch heredoc")

subscription_build = fetch("components/brave_mobile_subscription/renderer/android/BUILD.gn")
subscription_header = fetch("components/brave_mobile_subscription/renderer/android/subscription_render_frame_observer.h")
subscription_cc = fetch("components/brave_mobile_subscription/renderer/android/subscription_render_frame_observer.cc")
for anchor in (
    'source_set("android") {',
    'source_set("browser_tests") {',
    '"//brave/components/ai_chat/core/common",',
    '"//brave/components/ai_chat/core/common/mojom",',
):
    if anchor not in subscription_build:
        raise SystemExit("AI_CHAT_PREFLIGHT=FAIL pinned subscription GN anchor missing: " + anchor)
for anchor in (
    '#include "brave/components/ai_chat/core/common/mojom/ai_chat.mojom.h"',
    '#include "brave/components/ai_chat/core/common/mojom/common.mojom.h"',
    'mojo::Remote<ai_chat::mojom::IAPSubscription> ai_chat_subscription_;',
):
    if anchor not in subscription_header:
        raise SystemExit("AI_CHAT_PREFLIGHT=FAIL pinned subscription header anchor missing: " + anchor)
for anchor in (
    '#include "brave/components/ai_chat/core/common/features.h"',
    'ai_chat::features::IsAIChatEnabled()',
    'ai_chat_subscription_->GetPurchaseTokenOrderId',
    'ai_chat_subscription_->SetLinkStatus',
):
    if anchor not in subscription_cc:
        raise SystemExit("AI_CHAT_PREFLIGHT=FAIL pinned subscription C++ anchor missing: " + anchor)

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp) / "components/brave_mobile_subscription/renderer/android"
    root.mkdir(parents=True)
    build_file = root / "BUILD.gn"
    header_file = root / "subscription_render_frame_observer.h"
    cc_file = root / "subscription_render_frame_observer.cc"
    build_file.write_text(subscription_build, encoding="utf-8")
    header_file.write_text(subscription_header, encoding="utf-8")
    cc_file.write_text(subscription_cc, encoding="utf-8")

    def run_subscription_patch():
        result = subprocess.run(
            [sys.executable, "-c", subscription_body,
             str(build_file), str(header_file), str(cc_file)],
            text=True, capture_output=True
        )
        if result.returncode:
            raise SystemExit(
                "AI_CHAT_PREFLIGHT=FAIL mobile-subscription patch failed\n"
                + result.stdout + result.stderr
            )
        return result.stdout

    first_subscription = run_subscription_patch()
    patched_build = build_file.read_text(encoding="utf-8")
    patched_header = header_file.read_text(encoding="utf-8")
    patched_cc = cc_file.read_text(encoding="utf-8")
    assert 'import("//brave/components/ai_chat/core/common/buildflags/buildflags.gni")' in patched_build
    for target in ('source_set("android") {', 'source_set("browser_tests") {'):
        start = patched_build.find(target)
        end = patched_build.find("\n}", start)
        block = patched_build[start:end + 2]
        assert block.count('"//brave/components/ai_chat/core/common/buildflags"') == 1
        assert block.count('if (enable_ai_chat)') == 1
        assert block.count('"//brave/components/ai_chat/core/common"') == 1
        assert block.count('"//brave/components/ai_chat/core/common/mojom"') == 1
        condition = block[block.find('if (enable_ai_chat)'):]
        assert '"//brave/components/ai_chat/core/common"' in condition
        assert '"//brave/components/ai_chat/core/common/mojom"' in condition
    assert '#if BUILDFLAG(ENABLE_AI_CHAT)' in patched_header
    assert '#if BUILDFLAG(ENABLE_AI_CHAT)\n  mojo::Remote<ai_chat::mojom::IAPSubscription>' in patched_header
    assert patched_cc.count('#if BUILDFLAG(ENABLE_AI_CHAT)') == 4
    assert patched_cc.count('#endif  // BUILDFLAG(ENABLE_AI_CHAT)') == 4
    assert 'ai_chat::features::IsAIChatEnabled()' in patched_cc
    assert '#if BUILDFLAG(ENABLE_AI_CHAT)\n#include "brave/components/ai_chat/core/common/features.h"' in patched_cc

    first_snapshot = (patched_build, patched_header, patched_cc)
    second_subscription = run_subscription_patch()
    assert (
        build_file.read_text(encoding="utf-8"),
        header_file.read_text(encoding="utf-8"),
        cc_file.read_text(encoding="utf-8"),
    ) == first_snapshot, "mobile-subscription patch is not idempotent"

print("AI_CHAT_SUBSCRIPTION_PREFLIGHT=PASS pinned source, conditional GN deps, guarded C++/header and idempotent rerun")

print("AI_CHAT_PREFLIGHT=PASS pinned Brave source, GN target/dependency, C++ guards, and idempotent rerun")
