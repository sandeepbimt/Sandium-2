#!/usr/bin/env python3
"""Offline tests for the pinned Sandium Download Service concurrency overlay."""

import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "apply-sandium-download-concurrency.py"
SPEC = importlib.util.spec_from_file_location("sandium_download_concurrency", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

FIXTURE = """const uint32_t kDefaultMaxConcurrentDownloads = 4;
const uint32_t kDefaultMaxRunningDownloads = 2;
const uint32_t kDefaultMaxScheduledDownloads = 15;
const uint32_t kDefaultMaxRetryCount = 5;
"""

once = MODULE.patch_config(FIXTURE)
twice = MODULE.patch_config(once)
assert once == twice, "download concurrency patch must be idempotent"
for name, value in MODULE.LIMITS.items():
    assert once.count(f"const uint32_t {name} = {value};") == 1
assert "kDefaultMaxRetryCount = 5" in once
assert MODULE.LIMITS == {
    "kDefaultMaxConcurrentDownloads": 8,
    "kDefaultMaxRunningDownloads": 8,
    "kDefaultMaxScheduledDownloads": 64,
}
print("SANDIUM_DOWNLOAD_CONCURRENCY_TEST=PASS")
print("SANDIUM_DOWNLOAD_LIMITS=8-running/8-concurrent/64-scheduled")
