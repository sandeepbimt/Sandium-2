#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).with_name("fix-brave-chromium157-file-size-api.py")
CORE_SHA = "d5f73ccfbb8887db2367b182fa86df82c6b705cf"


def run(root: Path) -> str:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(root)],
        check=True, text=True, capture_output=True,
    ).stdout


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    core = root / "brave"
    source = core / "components/brave_shields/core/browser/ad_block_component_filters_provider.cc"
    source.parent.mkdir(parents=True)
    (core / ".git").mkdir(parents=True)
    # A tiny fake git executable is unnecessary: the production script calls
    # git rev-parse, so provide a wrapper earlier in PATH for this fixture.
    bindir = root / "bin"
    bindir.mkdir()
    git = bindir / "git"
    git.write_text("#!/bin/sh\nprintf '%s\\n' '" + CORE_SHA + "'\n", encoding="utf-8")
    git.chmod(0o755)
    legacy = """#include <memory>
#include "base/files/file_path.h"
namespace {
void ExistingHelper() {}
}
void Load() {
  int64_t list_file_size = 0;
  bool ok = base::GetFileSize(list_file_path, &list_file_size);
}
"""
    source.write_text(legacy, encoding="utf-8")
    import os
    env = dict(os.environ)
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    first = subprocess.run(
        [sys.executable, str(SCRIPT), str(root)],
        check=True, text=True, capture_output=True, env=env,
    ).stdout
    patched = source.read_text(encoding="utf-8")
    assert "SandiumGetFileSizeCompat(list_file_path, &list_file_size)" in patched
    assert "const auto result = base::GetFileSize(file_path);" in patched
    assert "base::GetFileSize(list_file_path, &list_file_size)" not in patched
    second = subprocess.run(
        [sys.executable, str(SCRIPT), str(root)],
        check=True, text=True, capture_output=True, env=env,
    ).stdout
    assert "PATCHED" in first and "PATCHED" in second

print("BRAVE_CHROMIUM157_FILE_SIZE_API_TEST=PASS")
