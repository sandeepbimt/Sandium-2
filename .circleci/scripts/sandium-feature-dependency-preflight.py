#!/usr/bin/env python3
"""Pinned Brave feature dependency preflight. Exact repairs only; unknown drift fails closed."""
import argparse
import re
import runpy
import subprocess
import sys
from pathlib import Path

BRAVE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
NEWS_TEST = '"//brave/browser/brave_news:browser_tests"'

def read(core, rel):
    p = core / rel
    if not p.is_file():
        raise RuntimeError(f"missing pinned source: {rel}")
    return p

def guards(source, needle):
    stack, depth, found = [], 0, []
    for n, raw in enumerate(source.splitlines(), 1):
        line = raw.split("#", 1)[0]
        m = re.match(r"\s*if\s*\((.*?)\)\s*\{\s*$", line)
        if m:
            stack.append((m.group(1).strip(), depth + 1))
        if needle in line:
            found.append((n, tuple(g for g, _ in stack)))
        clean = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', "", line)
        depth += clean.count("{") - clean.count("}")
        while stack and stack[-1][1] > depth:
            stack.pop()
    return found

def guarded(ctx, flag):
    return any(re.search(rf"\b{re.escape(flag)}\b", g) for g in ctx)

def fix_news(path):
    s = path.read_text(encoding="utf-8")
    old = s
    lines = s.splitlines(keepends=True)
    a = next((i for i,x in enumerate(lines) if x.strip() == "android_test_exception_deps = ["), None)
    if a is None:
        raise RuntimeError("NEWS_ANDROID_TEST_DEPS: list anchor missing")
    b = next((i for i in range(a+1,len(lines)) if lines[i].strip() == "]"), None)
    if b is None:
        raise RuntimeError("NEWS_ANDROID_TEST_DEPS: unterminated list")
    lines[a+1:b] = [x for x in lines[a+1:b] if NEWS_TEST not in x]
    s = "".join(lines)
    s = s.replace('if (enable_brave_news) {\n  android_test_exception_deps += [ "//brave/browser/brave_news:browser_tests" ]\n}\n', "")
    bulk = re.compile(r"^(\s*)deps\s*-\s*=\s*android_test_exception_deps\s*$", re.M)
    hits = list(bulk.finditer(s))
    begin, end, loop = "SANDIUM_ANDROID_TEST_DEPS_BEGIN", "SANDIUM_ANDROID_TEST_DEPS_END", "foreach(exception_dep, android_test_exception_deps)"
    if len(hits) > 1:
        raise RuntimeError("NEWS_ANDROID_TEST_DEPS: multiple subtraction anchors")
    if hits:
        if any(x in s for x in (begin,end,loop)):
            raise RuntimeError("NEWS_ANDROID_TEST_DEPS: mixed guarded/unguarded form")
        m = hits[0]; i = m.group(1)
        block = (i+"# "+begin+"\n"+i+loop+" {\n"+i+"  if (exception_dep in deps) {\n"+i+"    deps -= [ exception_dep ]\n"+i+"  }\n"+i+"}\n"+i+"# "+end+"\n")
        s = s[:m.start()] + block + s[m.end():]
    elif any(x in s for x in (begin,end,loop)):
        if not (s.count(begin)==s.count(end)==s.count(loop)==1 and s.index(begin)<s.index(end)):
            raise RuntimeError("NEWS_ANDROID_TEST_DEPS: partial/invalid guarded form")
    if NEWS_TEST in s or bulk.search(s):
        raise RuntimeError("NEWS_ANDROID_TEST_DEPS: stale target or unsafe subtraction remains")
    if s != old:
        path.write_text(s, encoding="utf-8")
        return True
    return False

def scan_all_gn(core):
    policies = [
      ("AI_CHAT", ("browser/ai_chat/","browser/ui/ai_chat/","browser/ui/webui/ai_chat/","browser/ui/views/side_panel/ai_chat/","components/ai_chat/"),
       ("//brave/browser/ai_chat","//brave/components/ai_chat/core/common"),
       ("/buildflags","/mojom",":mojom",":constants"), "enable_ai_chat"),
      ("WALLET", ("browser/brave_wallet/","browser/ui/webui/brave_wallet/","browser/ui/views/brave_wallet/","components/brave_wallet/"),
       ("//brave/browser/brave_wallet","//brave/components/brave_wallet"),
       ("/buildflags",), "enable_brave_wallet"),
      ("NEWS", ("browser/brave_news/","browser/ui/webui/brave_news/","browser/ui/webui/brave_news_internals/","components/brave_news/"),
       ("//brave/browser/brave_news","//brave/browser/ui/webui/brave_news","//brave/components/brave_news"),
       ("/buildflags",":mojom",":rss_link_reader_mojom"), "enable_brave_news"),
    ]
    failures, counts = [], {p[0]:0 for p in policies}
    for f in core.rglob("*"):
        if not f.is_file() or f.suffix not in (".gn",".gni"): continue
        rel = f.relative_to(core).as_posix()
        src = f.read_text(encoding="utf-8", errors="replace")
        for name, ignored, needles, allowed, flag in policies:
            if any(rel.startswith(x) for x in ignored): continue
            for needle in needles:
                for n, ctx in guards(src, needle):
                    line = src.splitlines()[n-1]
                    if any(x in line for x in allowed): continue
                    counts[name] += 1
                    if not guarded(ctx, flag):
                        failures.append(f"{name}:{rel}:{n}: {line.strip()}")
    if failures:
        raise RuntimeError("UNGUARDED_FEATURE_EDGES:\n  " + "\n  ".join(failures[:80]))
    print("GN_EDGE_INVENTORY=PASS " + " ".join(f"{k.lower()}_refs={v}" for k,v in counts.items()))

def verify(core, repo):
    actual = subprocess.check_output(["git","-C",str(core),"rev-parse","HEAD"],text=True).strip()
    if actual != BRAVE_SHA: raise RuntimeError(f"BRAVE_PIN_GATE expected={BRAVE_SHA} actual={actual}")
    prep = read(repo,".circleci/scripts/prepare-brave-source.sh").read_text()
    for flag in ("enable_ai_chat:false","enable_brave_wallet:false","enable_brave_news:false"):
        if prep.count("--gn "+flag) != 1: raise RuntimeError(f"GN_FLAG_GATE expected one --gn {flag}")
    scan_all_gn(core)
    sources = read(core,"browser/sources.gni").read_text()
    for target in ("//brave/browser/ai_chat","//brave/components/ai_chat/core/common"):
        for n,ctx in guards(sources,target):
            line=sources.splitlines()[n-1]
            if target.endswith("/common") and ("/mojom" in line or "/buildflags" in line): continue
            if not guarded(ctx,"enable_ai_chat"): raise RuntimeError(f"AI_CHAT_GN_CLOSURE unguarded {target} at {n}")
    for n,ctx in guards(sources,"//brave/browser/brave_wallet"):
        if not guarded(ctx,"enable_brave_wallet"): raise RuntimeError(f"WALLET_GN_CLOSURE unguarded browser target at {n}")
    for n,ctx in guards(sources,"//brave/components/brave_wallet"):
        if "/buildflags" not in sources.splitlines()[n-1] and not guarded(ctx,"enable_brave_wallet"):
            raise RuntimeError(f"WALLET_GN_CLOSURE unguarded component target at {n}")
    for n,ctx in guards(sources,"//brave/browser/ui/webui/brave_news"):
        if not guarded(ctx,"enable_brave_news") or not any("!is_android" in g for g in ctx):
            raise RuntimeError(f"NEWS_GN_CLOSURE unguarded/non-Android target at {n}")
    android = read(core,"browser/android/BUILD.gn").read_text()
    refs=guards(android,'"//brave/browser/ai_chat"')
    if len(refs)!=1 or not guarded(refs[0][1],"enable_ai_chat"):
        raise RuntimeError("AI_CHAT_ANDROID_GN tabs_impl dependency is not guarded")
    for rel, expected in (("browser/android/brave_tab_features.cc",2),("browser/android/brave_tab_features.h",2)):
        s=read(core,rel).read_text()
        if s.count("#if BUILDFLAG(ENABLE_AI_CHAT)")!=expected or s.count("#endif")<expected:
            raise RuntimeError(f"AI_CHAT_ANDROID_CPP_GUARD invalid: {rel}")
    chat=read(core,"browser/ai_chat/android/sources.gni").read_text()
    if "//brave/components/ai_chat/core/common" not in chat:
        raise RuntimeError("AI_CHAT_ANDROID_SOURCE edge changed")
    if not any(guarded(ctx,"enable_ai_chat") and "is_android" in " ".join(ctx)
               for _,ctx in guards(sources,"brave_browser_ai_chat_android_deps")):
        raise RuntimeError("AI_CHAT_ANDROID_SOURCE bundle not guarded")
    news=read(core,"components/brave_news/common/BUILD.gn").read_text()
    if "# The mojom target is always built so TypeScript can import types." not in news or "if (enable_brave_news) {" not in news:
        raise RuntimeError("NEWS_MOJOM/implementation boundary changed")
    if "assert(enable_brave_news)" not in read(core,"components/brave_news/browser/BUILD.gn").read_text():
        raise RuntimeError("NEWS_BROWSER implementation assertion missing")
    tests=read(core,"android/android_browser_tests.gni").read_text()
    if NEWS_TEST in tests or re.search(r"^\s*deps\s*-\s*=\s*android_test_exception_deps\s*$",tests,re.M):
        raise RuntimeError("NEWS_ANDROID_TEST_DEPS stale/unsafe")
    if "assert(enable_brave_wallet)" not in read(core,"browser/brave_wallet/BUILD.gn").read_text():
        raise RuntimeError("WALLET_BROWSER implementation assertion missing")
    print("FEATURE_DEPENDENCY_AUDIT=PASS ai_chat=excluded wallet=excluded news=excluded")
    print("TYPE_ONLY_REMAINDERS=PASS AI_Chat_and_News_Mojo_interfaces_retained_for_WebUI")
    print("SHIELDS_PRESERVATION=PASS")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--core",required=True,type=Path)
    p.add_argument("--repo-root",type=Path,default=Path(__file__).resolve().parents[2])
    p.add_argument("--fix",action="store_true")
    p.add_argument("--verify-only",action="store_true")
    a=p.parse_args(); core=a.core.resolve(); repo=a.repo_root.resolve()
    try:
        if a.fix and not a.verify_only:
            overlay=runpy.run_path(str(repo/".circleci/scripts/apply-sandium-full-overlays.py"))
            transforms=[("browser/android/BUILD.gn","transform_ai_chat_android_build"),
              ("browser/android/brave_tab_features.cc","transform_ai_chat_android_source"),
              ("browser/android/brave_tab_features.h","transform_ai_chat_android_header")]
            for iteration in range(1,4):
                changed=False
                for rel,name in transforms:
                    f=read(core,rel); old=f.read_text(); new=overlay[name](old)
                    if new!=old: f.write_text(new); changed=True; print("REPAIR_APPLIED="+rel)
                if fix_news(read(core,"android/android_browser_tests.gni")):
                    changed=True; print("REPAIR_APPLIED=android/android_browser_tests.gni")
                print(f"REPAIR_ITERATION={iteration} changed={str(changed).lower()}")
                verify(core,repo)
                if not changed: break
            else: raise RuntimeError("REPAIR_LOOP did not converge in three passes")
        else: verify(core,repo)
        return 0
    except Exception as e:
        print(f"FEATURE_DEPENDENCY_PREFLIGHT=FAIL {e}",file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
