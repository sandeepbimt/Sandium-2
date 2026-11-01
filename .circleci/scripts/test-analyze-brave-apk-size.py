#!/usr/bin/env python3
"""Synthetic ZIP/ELF regression test for analyze-brave-apk-size.py."""
from __future__ import annotations

import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).with_name("analyze-brave-apk-size.py")


def fake_elf(machine: int) -> bytes:
    header = bytearray(64)
    header[:4] = bytes((127, 69, 76, 70))
    header[4] = 2  # ELFCLASS64
    header[5] = 1  # little-endian
    struct.pack_into("<H", header, 18, machine)
    return bytes(header)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sandium-apk-audit-") as temp:
        root = Path(temp)
        apk = root / "fixture.apk"
        report = root / "size-report.txt"
        with zipfile.ZipFile(apk, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("lib/arm64-v8a/libfixture.so", fake_elf(183))
            archive.writestr("lib/armeabi-v7a/libfixture.so", fake_elf(40))
            archive.writestr("assets/test.dat", b"asset-data" * 100)

        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(apk), "--output", str(report)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
        )
        output = result.stdout
        expected = (
            "FORMAT=APK",
            "ABI_SET=arm64-v8a,armeabi-v7a",
            "ABI[arm64-v8a]=",
            "ABI[armeabi-v7a]=",
            "ELF_MACHINE[EM_AARCH64]=1",
            "ELF_MACHINE[EM_ARM]=1",
            "ABI_FOOTPRINT=ARM64_PLUS_32_BIT",
            "APK_SIZE_AUDIT=PASS",
        )
        missing = [value for value in expected if value not in output]
        if missing:
            raise AssertionError(
                "APK size audit output missing expected fields: %r\n%s"
                % (missing, output)
            )
        if not report.is_file() or report.read_text(encoding="utf-8") != output:
            raise AssertionError("APK size audit report file does not match stdout")
    print("BRAVE_APK_SIZE_AUDIT_SELF_TEST=PASS dual-ABI ZIP/ELF fixture")


if __name__ == "__main__":
    main()
