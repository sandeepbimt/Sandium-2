#!/usr/bin/env python3
"""Regression tests for cached APK completion marker parsing."""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / ".circleci/scripts/check-apk-completion-marker.py"
GOOD = (
    "BUILD_FINISHED=true\n"
    "APK_ARCHIVE_VALID=true\n"
    "APK_SIGNATURE_VALID=true\n"
    "APK_PACKAGE_ID_VALID=true\n"
    "APK_BRANDING_VALID=true\n"
    "APK_PACKAGE_ID=com.brave.browser_default\n"
)


def run(content: str | None) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as directory:
        marker = Path(directory) / "marker.txt"
        if content is not None:
            marker.write_bytes(content.encode("utf-8"))
        return subprocess.run(
            [sys.executable, str(CHECKER), str(marker)],
            text=True, capture_output=True, check=False,
        )


def main() -> None:
    result = run(GOOD)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "APK_COMPLETION_MARKER=VALID" in result.stdout

    # CircleCI cache files should also validate if line endings or BOM differ.
    result = run("\ufeff" + GOOD.replace("\n", "\r\n"))
    assert result.returncode == 0, result.stdout + result.stderr

    result = run(GOOD.replace("APK_BRANDING_VALID=true", "APK_BRANDING_VALID=false"))
    assert result.returncode == 1
    assert "failed_keys=APK_BRANDING_VALID" in result.stdout

    result = run(GOOD.replace("APK_PACKAGE_ID_VALID=true\n", ""))
    assert result.returncode == 1
    assert "failed_keys=APK_PACKAGE_ID_VALID" in result.stdout

    result = run(None)
    assert result.returncode == 1
    assert "reason=missing" in result.stdout
    print("APK_COMPLETION_MARKER_TEST=PASS")


if __name__ == "__main__":
    main()
