#!/usr/bin/env python3
"""Preflight the disabled AI Chat/Brave News Chromium feature-list overlay."""
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
marker = "python3 - \"$CORE_DIR/chromium_src/chrome/browser/flags/android/chrome_feature_list.cc\" <<'PY'\n"
if script.count(marker) != 1:
    raise SystemExit("CHROMIUM_FEATURE_LIST_PREFLIGHT=FAIL expected exactly one overlay patch heredoc")
body, separator, _ = script.split(marker, 1)[1].partition("\nPY\n")
if not separator:
    raise SystemExit("CHROMIUM_FEATURE_LIST_PREFLIGHT=FAIL unterminated overlay patch heredoc")

overlay = fetch("chromium_src/chrome/browser/flags/android/chrome_feature_list.cc")
for anchor in (
    '#include "brave/components/ai_chat/core/common/features.h"',
    '#include "brave/components/brave_news/common/features.h"',
    "#define BRAVE_AI_CHAT_FLAGS",
    "&ai_chat::features::kAIChat",
):
    if anchor not in overlay:
        raise SystemExit("CHROMIUM_FEATURE_LIST_PREFLIGHT=FAIL pinned overlay anchor missing: " + anchor)

with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "chrome_feature_list.cc"
    path.write_text(overlay, encoding="utf-8")

    def apply():
        result = subprocess.run([sys.executable, "-c", body, str(path)],
                                text=True, capture_output=True)
        if result.returncode:
            raise SystemExit("CHROMIUM_FEATURE_LIST_PREFLIGHT=FAIL patch execution\n"
                             + result.stdout + result.stderr)
        return result.stdout

    first_output = apply()
    patched = path.read_text(encoding="utf-8")
    expected = (
        '#if BUILDFLAG(ENABLE_AI_CHAT)\n'
        '#include "brave/components/ai_chat/core/common/features.h"\n'
        '#endif  // BUILDFLAG(ENABLE_AI_CHAT)'
    )
    assert expected in patched
    expected = (
        '#if BUILDFLAG(ENABLE_BRAVE_NEWS)\n'
        '#include "brave/components/brave_news/common/features.h"\n'
        '#endif  // BUILDFLAG(ENABLE_BRAVE_NEWS)'
    )
    assert expected in patched
    assert '#else  // BUILDFLAG(ENABLE_AI_CHAT)\n#define BRAVE_AI_CHAT_FLAGS\n#endif' in patched
    assert patched.count('#include "brave/components/ai_chat/core/common/buildflags/buildflags.h"') == 1
    assert patched.count('#include "brave/components/brave_news/common/buildflags/buildflags.h"') == 1
    second_output = apply()
    assert path.read_text(encoding="utf-8") == patched, "overlay patch is not idempotent"
    assert "SANDIUM_CHROMIUM_FEATURE_LIST_GATE=PASS" in first_output
    assert "SANDIUM_CHROMIUM_FEATURE_LIST_GATE=PASS" in second_output

print("CHROMIUM_FEATURE_LIST_PREFLIGHT=PASS pinned Brave overlay, both disabled buildflag guards, and idempotent rerun")
