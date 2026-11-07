#!/usr/bin/env python3
"""Idempotently repair the pinned Brave Android AI Chat-off ownership guards."""
from pathlib import Path
import sys

def replace_once(text, old, new, label):
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit("SANDIUM_SHE_REPAIR=FAIL %s anchor_count=%d" % (label, count))
    return text.replace(old, new, 1)

def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: repair-ai-chat-android.py <brave-core-dir>")
    core = Path(sys.argv[1])
    hp, cp, gp = (core / "browser/android/brave_tab_features.h",
                  core / "browser/android/brave_tab_features.cc",
                  core / "browser/android/BUILD.gn")
    for p in (hp, cp, gp):
        if not p.is_file():
            raise SystemExit("SANDIUM_SHE_REPAIR=FAIL missing source " + str(p))
    h, c, g = (hp.read_text(encoding="utf-8"), cp.read_text(encoding="utf-8"), gp.read_text(encoding="utf-8"))
    h = replace_once(h, "#include <memory>\n",
        '#include <memory>\n\n#include "brave/components/ai_chat/core/common/buildflags/buildflags.h"\n', "header buildflags")
    decl = ("namespace ai_chat {\nclass TabDataWebContentsObserver;\nclass WebMcpInjector;\n}  // namespace ai_chat")
    h = replace_once(h, decl, "#if BUILDFLAG(ENABLE_AI_CHAT)\n" + decl + "\n#endif  // BUILDFLAG(ENABLE_AI_CHAT)", "forward declarations")
    members = ("  std::unique_ptr<ai_chat::TabDataWebContentsObserver> tab_data_observer_;\n"
               "  std::unique_ptr<ai_chat::WebMcpInjector> web_mcp_injector_;\n")
    h = replace_once(h, members, "#if BUILDFLAG(ENABLE_AI_CHAT)\n" + members + "#endif  // BUILDFLAG(ENABLE_AI_CHAT)\n", "unique_ptr members")
    c = replace_once(c, '#include "base/feature_list.h"\n',
        '#include "base/feature_list.h"\n#include "brave/components/ai_chat/core/common/buildflags/buildflags.h"\n', "cc buildflags")
    includes = ('#include "brave/browser/ai_chat/ai_chat_utils.h"\n'
                '#include "brave/browser/ai_chat/tab_data_web_contents_observer.h"\n'
                '#include "brave/browser/ai_chat/web_mcp_injection/web_mcp_injector.h"\n')
    c = replace_once(c, includes, "#if BUILDFLAG(ENABLE_AI_CHAT)\n" + includes + "#endif  // BUILDFLAG(ENABLE_AI_CHAT)\n", "AI Chat includes")
    block = ("  if (ai_chat::IsAllowedForContext(profile)) {\n"
             "    tab_data_observer_ = std::make_unique<ai_chat::TabDataWebContentsObserver>(\n"
             "        TabAndroid::FromWebContents(web_contents)->GetAndroidId(),\n"
             "        web_contents);\n"
             "    // Injects Brave-provided WebMCP tools into matching pages; see\n"
             "    // WebMcpInjector. Null when WebMCP is disabled or has no rules.\n"
             "    web_mcp_injector_ = ai_chat::WebMcpInjector::MaybeCreate(web_contents);\n"
             "  }\n")
    c = replace_once(c, block, "#if BUILDFLAG(ENABLE_AI_CHAT)\n" + block + "#endif  // BUILDFLAG(ENABLE_AI_CHAT)\n", "tab initialization")
    g = replace_once(g, 'import("//brave/components/brave_ads/buildflags/buildflags.gni")\n',
        'import("//brave/components/brave_ads/buildflags/buildflags.gni")\nimport("//brave/components/ai_chat/core/common/buildflags/buildflags.gni")\n', "GN buildflags import")
    old_public = '  public_deps = [ "//chrome/browser/android:tabs_public" ]'
    new_public = ('  public_deps = [\n'
                  '    "//brave/components/ai_chat/core/common/buildflags",\n'
                  '    "//chrome/browser/android:tabs_public",\n'
                  '  ]')
    g = replace_once(g, old_public, new_public, "public dependency")
    old_dep = '    "//brave/browser/ai_chat",\n'
    if old_dep in g:
        if g.count(old_dep) != 1:
            raise SystemExit("SANDIUM_SHE_REPAIR=FAIL unexpected AI Chat GN dep count")
        g = g.replace(old_dep, "", 1)
    conditional = ('  if (enable_ai_chat) {\n'
                   '    deps += [ "//brave/browser/ai_chat" ]\n'
                   '  }\n')
    if conditional not in g:
        tail = '    "//content/public/browser",\n  ]\n}\n'
        g = replace_once(g, tail, '    "//content/public/browser",\n  ]\n' + conditional + '}\n', "conditional GN dependency")
    assert '#if BUILDFLAG(ENABLE_AI_CHAT)\nnamespace ai_chat {' in h
    assert '#if BUILDFLAG(ENABLE_AI_CHAT)\n  std::unique_ptr<ai_chat::TabDataWebContentsObserver>' in h
    assert '#if BUILDFLAG(ENABLE_AI_CHAT)\n#include "brave/browser/ai_chat/ai_chat_utils.h"' in c
    assert '#if BUILDFLAG(ENABLE_AI_CHAT)\n  if (ai_chat::IsAllowedForContext(profile)) {' in c
    assert conditional in g and g.count('"//brave/browser/ai_chat"') == 1
    hp.write_text(h, encoding="utf-8")
    cp.write_text(c, encoding="utf-8")
    gp.write_text(g, encoding="utf-8")
    print("SANDIUM_SHE_REPAIR=PASS rule=AI_CHAT_ANDROID_GUARDS")

if __name__ == "__main__":
    main()
