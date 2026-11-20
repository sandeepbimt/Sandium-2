#!/usr/bin/env python3
"""Plan/apply the opt-in-ready RawS document loader link on the exact Chromium pin."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
PIN = json.loads((ROOT / "pins.json").read_text())["chromium"]
CLIENT = "chrome/browser/chrome_content_browser_client.cc"
BUILD = "chrome/browser/BUILD.gn"
CONFIG = '#include "build/build_config.h"\n'
FACTORY_INCLUDE = """#if BUILDFLAG(IS_ANDROID)
#include "components/sandium_adblock/document_subresource_factory.h"
#endif
"""
FACTORY_SITE = """  if (type == URLLoaderFactoryType::kDocumentSubResource) {
    contextual_tasks::ContextualTasksSubresourceProxyingURLLoaderFactory::
        MaybeProxyRequest(browser_context, isolation_info, factory_builder);
    glic::GlicSubresourceProxyingURLLoaderFactory::MaybeProxyRequest(
        frame, factory_builder);
  }
"""
FACTORY_LINK = FACTORY_SITE.replace(
    "    contextual_tasks::ContextualTasksSubresourceProxyingURLLoaderFactory::",
    """#if BUILDFLAG(IS_ANDROID)
    if (frame) {
      sandium::adblock_native::MaybeAppendDocumentSubresourceFactory(
          factory_builder, request_initiator);
    }
#endif
    contextual_tasks::ContextualTasksSubresourceProxyingURLLoaderFactory::""",
)
CORE = 'source_set("core") {\n'
CORE_CLIENT = '    "chrome_content_browser_client.cc",'
CORE_DEP = """  if (is_android) {
    deps += [
      ":resources",
      "//components/sandium_adblock:document_subresource_factory",
    ]
  }
"""


def replace_once(original: str, old: str, new: str) -> str:
    if original.count(new) == 1 and old not in original.replace(new, "", 1):
        return original
    if original.count(old) != 1 or new in original:
        raise ValueError(f"Ambiguous Chromium insertion: {old[:72]!r}")
    return original.replace(old, new, 1)


def link_client(source: str) -> str:
    return replace_once(replace_once(source, CONFIG, CONFIG + FACTORY_INCLUDE),
                        FACTORY_SITE, FACTORY_LINK)


def link_build(source: str) -> str:
    if source.count(CORE) != 1:
        raise ValueError("Unexpected Chrome GN core target")
    i = source.index(CORE)
    end = source.index("\n}", i) + 1
    core = source[i:end]
    if core.count(CORE_CLIENT) != 1 or "\n  deps = " not in core:
        raise ValueError("Chrome GN core target no longer owns browser client")
    if CORE_DEP in core:
        if not core.endswith(CORE_DEP) or source.count(CORE_DEP) != 1:
            raise ValueError("Ambiguous Chrome GN engine dependency")
        return source
    if "sandium_adblock:" in source:
        raise ValueError("Unknown preexisting Chrome GN engine dependency")
    return source[:end] + CORE_DEP + source[end:]


def git(src: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(src), *args])


def plan(src: Path) -> dict[str, str]:
    if (Path(git(src, "rev-parse", "--show-toplevel").decode().strip()).resolve()
            != src.resolve() or git(src, "rev-parse", "HEAD").decode().strip() != PIN):
        raise ValueError("Wrong Chromium checkout or pin")
    native = src / "components/sandium_adblock"
    for name in ("BUILD.gn", "request_matcher.cc", "subresource_decision.cc",
                 "document_subresource_factory.h", "document_subresource_factory.cc"):
        expected = (ROOT / "native" / name).read_bytes()
        if (native / name).is_symlink() or (native / name).read_bytes() != expected:
            raise ValueError(f"Missing or divergent installed engine source: {name}")
    result = {}
    for relative, link in ((CLIENT, link_client), (BUILD, link_build)):
        base = git(src, "show", f"{PIN}:{relative}").decode()
        linked = link(base)
        path = src / relative
        if path.is_symlink() or path.read_bytes() not in (base.encode(), linked.encode()):
            raise ValueError(f"Divergent preimage: {relative}")
        result[relative] = linked
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("src", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    changes = plan(args.src)
    if args.apply:
        for relative, data in changes.items():
            path = args.src / relative
            if path.read_bytes() != data.encode():
                path.write_bytes(data.encode())
    print("RawS pinned loader graph plan verified; production startup still requires approved rules input.")


if __name__ == "__main__":
    main()
