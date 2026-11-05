#!/usr/bin/env python3
"""Apply a narrow Chromium 157 GetFileSize API compatibility shim to Brave Core.

The shim preserves the legacy bool/out-parameter contract while delegating to
Chromium's current optional-returning base::GetFileSize(FilePath) API.
It is idempotent and only touches the one known Brave Shields call site.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HELPER_NAME = "SandiumGetFileSizeCompat"
LEGACY_CALL = re.compile(
    r"base::GetFileSize\\s*\\(\\s*list_file_path\\s*,\\s*&list_file_size\\s*\\)"
)
HELPER = """bool SandiumGetFileSizeCompat(const base::FilePath& file_path,
                              int64_t* file_size) {
  const auto result = base::GetFileSize(file_path);
  if (!result.has_value()) {
    return false;
  }
  *file_size = *result;
  return true;
}

"""


def fail(message: str) -> None:
    raise SystemExit("BRAVE_CHROMIUM157_FILE_SIZE_API=FAIL " + message)


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: fix-brave-chromium157-file-size-api.py <chromium-src>")
    src = Path(sys.argv[1]).resolve()
    core = src / "brave"
    path = core / "components/brave_shields/core/browser/ad_block_component_filters_provider.cc"
    if not path.is_file():
        fail(f"source file missing: {path}")

    core_sha = subprocess.run(
        ["git", "-C", str(core), "rev-parse", "HEAD"],
        check=True, text=True, capture_output=True,
    ).stdout.strip()
    if core_sha != "d5f73ccfbb8887db2367b182fa86df82c6b705cf":
        fail(f"unexpected Brave Core SHA {core_sha}; expected v1.99.55 pin")

    original = path.read_text(encoding="utf-8")
    original_sha = hashlib.sha256(original.encode()).hexdigest()
    matches = list(LEGACY_CALL.finditer(original))
    helper_present = HELPER_NAME in original

    if len(matches) > 1:
        fail(f"expected at most one legacy call, found {len(matches)}")

    if len(matches) == 1:
        if helper_present:
            updated = LEGACY_CALL.sub(
                f"{HELPER_NAME}(list_file_path, &list_file_size)", original
            )
        else:
            if original.count("namespace {") != 1:
                fail("expected exactly one anonymous namespace insertion point")
            updated = original.replace(
                "namespace {", "namespace {\\n\\n" + HELPER, 1
            )
            updated, count = LEGACY_CALL.subn(
                f"{HELPER_NAME}(list_file_path, &list_file_size)", updated
            )
            if count != 1:
                fail(f"replacement count was {count}, expected 1")
            if "#include <cstdint>" not in updated:
                anchor = "#include <memory>"
                if original.count(anchor) != 1:
                    fail("could not safely insert <cstdint> include")
                updated = updated.replace(anchor, "#include <cstdint>\\n" + anchor, 1)

        if updated != original:
            fd, temporary = tempfile.mkstemp(prefix=".sandium-file-size-", dir=str(path.parent))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as output:
                    output.write(updated)
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)

        verified = path.read_text(encoding="utf-8")
        if LEGACY_CALL.search(verified) or HELPER_NAME not in verified:
            fail("post-patch verification failed")
        print(
            "BRAVE_CHROMIUM157_FILE_SIZE_API=PATCHED "
            f"core_sha={core_sha} before_sha256={original_sha} "
            f"after_sha256={hashlib.sha256(verified.encode()).hexdigest()}"
        )
        return

    if helper_present:
        fail("compatibility helper exists but expected legacy call is absent; inspect source manually")

    if re.search(r"base::GetFileSize\\s*\\([^;]*,", original):
        fail("unexpected multi-argument GetFileSize call; refusing broad rewrite")

    print(
        "BRAVE_CHROMIUM157_FILE_SIZE_API=ALREADY_COMPATIBLE "
        f"core_sha={core_sha} source_sha256={original_sha}"
    )


if __name__ == "__main__":
    main()
