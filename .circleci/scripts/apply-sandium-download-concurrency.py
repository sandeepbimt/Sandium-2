#!/usr/bin/env python3
"""Raise the pinned Chromium Download Service limits for Sandium's 29-list bootstrap.

The Download Service owns network transfers; this does not create one OS thread per
URL. It permits up to eight downloads to run concurrently and enough scheduled
slots for all default lists, while preserving Chromium's normal retry/scheduling
logic and Sandium's existing UI-priority request flag.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

EXPECTED_CHROMIUM_SHA = "d331de35ca8ab1358c7a17e4bd41627d55eaef51"
CONFIG = Path("components/download/internal/background_service/config.cc")

LIMITS = {
    "kDefaultMaxConcurrentDownloads": 8,
    "kDefaultMaxRunningDownloads": 8,
    "kDefaultMaxScheduledDownloads": 64,
}


def git_sha(src: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(src), "rev-parse", "HEAD"], text=True
    ).strip()


def patch_config(source: str) -> str:
    for name, value in LIMITS.items():
        import re

        pattern = rf"(const uint32_t {name}\s*=\s*)\d+(\s*;)"
        replacement = rf"\g<1>{value}\g<2>"
        updated, count = re.subn(pattern, replacement, source)
        if count != 1:
            # Idempotence: already-correct value is accepted; anything else fails.
            expected = f"const uint32_t {name} = {value};"
            if source.count(expected) != 1:
                raise SystemExit(
                    f"SANDIUM_DOWNLOAD_CONCURRENCY=FAIL expected one {name} assignment; "
                    f"replacement_count={count}"
                )
        else:
            source = updated

    for name, value in LIMITS.items():
        expected = f"const uint32_t {name} = {value};"
        if source.count(expected) != 1:
            raise SystemExit(
                f"SANDIUM_DOWNLOAD_CONCURRENCY=FAIL post-write verification failed: {name}"
            )
    return source


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True, type=Path, help="Pinned Chromium source root")
    args = parser.parse_args()
    src = args.src.resolve()

    actual = git_sha(src)
    if actual != EXPECTED_CHROMIUM_SHA:
        raise SystemExit(
            "SANDIUM_DOWNLOAD_CONCURRENCY_PIN=FAIL "
            f"expected={EXPECTED_CHROMIUM_SHA} actual={actual}"
        )

    path = src / CONFIG
    if not path.is_file():
        raise SystemExit(f"SANDIUM_DOWNLOAD_CONCURRENCY=FAIL missing {path}")

    before = path.read_text(encoding="utf-8")
    after = patch_config(before)
    if after != before:
        path.write_text(after, encoding="utf-8")
    if path.read_text(encoding="utf-8") != after:
        raise SystemExit("SANDIUM_DOWNLOAD_CONCURRENCY=FAIL write verification failed")

    print(f"SANDIUM_DOWNLOAD_CONCURRENCY_PIN=PASS chromium={actual}")
    print("SANDIUM_DOWNLOAD_MAX_CONCURRENT=8")
    print("SANDIUM_DOWNLOAD_MAX_RUNNING=8")
    print("SANDIUM_DOWNLOAD_MAX_SCHEDULED_PER_CLIENT=64")
    print("SANDIUM_DOWNLOAD_PRIORITY=UI (from_ui=true; battery-insensitive; no network restriction)")
    print("SANDIUM_DOWNLOAD_CONCURRENCY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
