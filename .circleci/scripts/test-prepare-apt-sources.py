#!/usr/bin/env python3
"""Offline tests for Sandium APT duplicate-source cleanup."""
import importlib.util
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).with_name("prepare-apt-sources.py")
SPEC = importlib.util.spec_from_file_location("sandium_apt_sources", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    sources = root / "sources.list.d"
    sources.mkdir()
    retry = root / "apt.conf.d" / "80sandium-retries"

    google = "deb [arch=amd64] https://dl.google.com/linux/chrome/deb/ stable main\n"
    (sources / "google.list").write_text(google, encoding="utf-8")
    (sources / "google-chrome.list").write_text(
        google + "deb https://packages.cloud.google.com/apt cloud-sdk main\n",
        encoding="utf-8",
    )
    (sources / "ubuntu.list").write_text(
        "deb http://archive.ubuntu.com/ubuntu noble main universe\n",
        encoding="utf-8",
    )

    result = MODULE.prepare(sources, retry)
    first = (sources / "google.list").read_text(encoding="utf-8")
    second = (sources / "google-chrome.list").read_text(encoding="utf-8")
    ubuntu = (sources / "ubuntu.list").read_text(encoding="utf-8")

    assert result["duplicates"] == 1
    assert google in first
    assert "# sandium-apt-deduplicated:" in second
    assert "packages.cloud.google.com" in second
    assert "archive.ubuntu.com" in ubuntu
    assert 'Acquire::Retries "5";' in retry.read_text(encoding="utf-8")

    # A second pass must be stable and must not comment additional entries.
    before = {p.name: p.read_text(encoding="utf-8") for p in sources.glob("*.list")}
    second_result = MODULE.prepare(sources, retry)
    after = {p.name: p.read_text(encoding="utf-8") for p in sources.glob("*.list")}
    assert second_result["duplicates"] == 0
    assert before == after

print("SANDIUM_APT_SOURCE_TEST=PASS exact_duplicates_only=true retry_config=true idempotent=true")
