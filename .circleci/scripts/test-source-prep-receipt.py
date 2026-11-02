#!/usr/bin/env python3
"""Regression test for the pinned Brave source-preparation receipt."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
RECEIPT_SCRIPT = HERE / "source-prep-receipt.py"


def git(path: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), *args], text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def run(root: Path, pin: str, *extra: str, expected: int = 0) -> str:
    command = [
        sys.executable, str(RECEIPT_SCRIPT), *extra,
        "--root", str(root),
        "--brave-tag", "v1.98.62",
        "--chromium-pin", pin,
        "--reapi-address", "remote.buildbuddy.io:443",
    ]
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    if result.returncode != expected:
        raise AssertionError(
            f"expected exit={expected}, got={result.returncode}\n{result.stdout}"
        )
    return result.stdout


def main() -> None:
    # Import the file list from the production helper so the fixture always
    # covers every file that the receipt claims to protect.
    import importlib.util
    spec = importlib.util.spec_from_file_location("source_prep_receipt", RECEIPT_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    with tempfile.TemporaryDirectory(prefix="sandium-source-receipt-") as temporary:
        root = Path(temporary)
        for relative in module.REQUIRED_FILES:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"receipt fixture: {relative}\n", encoding="utf-8")
            path.chmod(0o755 if relative.endswith("python_remote_wrapper") else 0o644)

        src = root / "brave-work/src"
        core = src / "brave"
        git(core, "init")
        git(core, "config", "user.email", "source-receipt@example.invalid")
        git(core, "config", "user.name", "Source Receipt Test")
        git(core, "add", "-A")
        git(core, "commit", "-m", "pinned Brave fixture")
        git(core, "tag", "v1.98.62")

        git(src, "init")
        git(src, "config", "user.email", "source-receipt@example.invalid")
        git(src, "config", "user.name", "Source Receipt Test")
        git(src, "add", "-A")
        git(src, "commit", "-m", "pinned Chromium fixture")
        pin = git(src, "rev-parse", "HEAD")

        written = run(root, pin, "write")
        assert "BRAVE_PREP_RECEIPT=WRITTEN" in written, written
        first = run(root, pin, "verify")
        assert "BRAVE_PREP_RECEIPT=PASS" in first, first

        # A changed generated build argument must invalidate the receipt and
        # force the caller back to its existing full preparation path.
        args_gn = root / "brave-work/src/out/android_Release_arm64/args.gn"
        original = args_gn.read_text(encoding="utf-8")
        args_gn.write_text(original + "# changed\n", encoding="utf-8")
        changed = run(root, pin, "verify", expected=1)
        assert "BRAVE_PREP_RECEIPT=MISS" in changed, changed
        args_gn.write_text(original, encoding="utf-8")
        restored = run(root, pin, "verify")
        assert "BRAVE_PREP_RECEIPT=PASS" in restored, restored

        wrong_endpoint = subprocess.run(
            [
                sys.executable, str(RECEIPT_SCRIPT), "verify",
                "--root", str(root), "--brave-tag", "v1.98.62",
                "--chromium-pin", pin, "--reapi-address", "wrong.example:443",
            ],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        assert wrong_endpoint.returncode == 1
        assert "BRAVE_PREP_RECEIPT=MISS" in wrong_endpoint.stdout

    print("BRAVE_SOURCE_PREP_RECEIPT_TEST=PASS exact pins + file hashes + modes + safe fallback")


if __name__ == "__main__":
    main()
