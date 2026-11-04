#!/usr/bin/env python3
"""Synthetic ZIP tests for the strict ARM64-only Brave APK size gate."""
from __future__ import annotations

import runpy
import struct
import tempfile
import zipfile
from pathlib import Path

MODULE = runpy.run_path(str(Path(__file__).with_name("analyze-brave-apk-size.py")))
make_report = MODULE["make_report"]


def elf_header(machine: int) -> bytes:
    header = bytearray(20)
    header[:4] = bytes((127, 69, 76, 70))
    header[4] = 2
    header[5] = 1
    struct.pack_into("<H", header, 18, machine)
    return bytes(header)


def make_apk(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)


def must_fail(path: Path, expected: str) -> None:
    try:
        make_report(path, require_arm64_only=True)
    except SystemExit as error:
        assert expected in str(error), str(error)
    else:
        raise AssertionError("invalid APK passed: " + path.name)


def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        arm64 = root / "arm64.apk"
        make_apk(arm64, {
            "lib/arm64-v8a/libchrome.so": elf_header(183) + b"x" * 64,
            "assets/base.pak": b"asset",
        })
        report = make_report(arm64, require_arm64_only=True)
        assert "ABI_SET=arm64-v8a" in report
        assert "ABI_FOOTPRINT=ARM64_ONLY" in report
        assert "ELF_MACHINE[EM_AARCH64]=1" in report

        multi = root / "multi-abi.apk"
        make_apk(multi, {
            "lib/arm64-v8a/libchrome.so": elf_header(183) + b"x" * 64,
            "lib/armeabi-v7a/libchrome.so": elf_header(40) + b"y" * 64,
        })
        must_fail(multi, "ARM64-only")

        wrong_elf = root / "wrong-elf.apk"
        make_apk(wrong_elf, {
            "lib/arm64-v8a/libchrome.so": elf_header(40) + b"z" * 64,
        })
        must_fail(wrong_elf, "not EM_AARCH64")

    print("SANDIUM_APK_SIZE_UNIT_TEST=PASS arm64_only=true multi_abi_rejected=true")


if __name__ == "__main__":
    main()
