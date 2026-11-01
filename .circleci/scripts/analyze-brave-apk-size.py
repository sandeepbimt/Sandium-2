#!/usr/bin/env python3
"""Read-only size and ABI audit for a Brave Android APK or AAB.

Usage:
  python3 .circleci/scripts/analyze-brave-apk-size.py input.apk
  python3 .circleci/scripts/analyze-brave-apk-size.py input.aab --output size-report.txt

The script never extracts files. It reports ZIP entry sizes and inspects ELF
headers for packaged native libraries, so it is safe to run on large artifacts.
"""
from __future__ import annotations

import argparse
import struct
import sys
import zipfile
from collections import defaultdict
from pathlib import Path


def human(value: int) -> str:
    units = ("B", "KiB", "MiB", "GiB")
    amount = float(value)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.2f} {unit}"
        amount /= 1024
    return f"{amount:.2f} GiB"


def abi_for(path: str) -> str | None:
    parts = path.split("/")
    for index, part in enumerate(parts[:-2]):
        if part == "lib":
            candidate = parts[index + 1]
            if candidate in {
                "arm64-v8a", "armeabi-v7a", "armeabi", "x86", "x86_64",
                "mips", "mips64", "riscv64",
            }:
                return candidate
    return None


def elf_machine(archive: zipfile.ZipFile, name: str) -> str:
    try:
        with archive.open(name) as stream:
            header = stream.read(20)
        if len(header) < 20 or header[:4] != bytes((127, 69, 76, 70)):
            return "not-ELF"
        endian = "<" if header[5] == 1 else ">" if header[5] == 2 else None
        if endian is None:
            return "unknown-endian"
        machine = struct.unpack_from(endian + "H", header, 18)[0]
        return {
            3: "EM_386", 40: "EM_ARM", 62: "EM_X86_64",
            183: "EM_AARCH64", 243: "EM_RISCV",
        }.get(machine, f"EM_{machine}")
    except (OSError, KeyError, zipfile.BadZipFile):
        return "unreadable"


def make_report(source: Path) -> str:
    if not source.is_file():
        raise SystemExit(f"APK_SIZE_AUDIT=FAIL file not found: {source}")

    with zipfile.ZipFile(source) as archive:
        infos = [item for item in archive.infolist() if not item.is_dir()]
        if not infos:
            raise SystemExit("APK_SIZE_AUDIT=FAIL archive contains no files")

        abi_stats: dict[str, dict[str, int]] = defaultdict(
            lambda: {"files": 0, "compressed": 0, "uncompressed": 0}
        )
        elf_stats: dict[str, int] = defaultdict(int)
        category_stats: dict[str, dict[str, int]] = defaultdict(
            lambda: {"files": 0, "compressed": 0, "uncompressed": 0}
        )
        symbol_named = []
        largest = sorted(infos, key=lambda item: item.file_size, reverse=True)[:30]

        for item in infos:
            name = item.filename
            abi = abi_for(name)
            if abi and name.endswith(".so"):
                stat = abi_stats[abi]
                stat["files"] += 1
                stat["compressed"] += item.compress_size
                stat["uncompressed"] += item.file_size
                elf_stats[elf_machine(archive, name)] += 1

            lower = name.lower()
            if lower.endswith((".dwo", ".pdb", ".sym", ".debug")) or "/symbols/" in lower:
                symbol_named.append((name, item.file_size))

            if name.endswith(".so"):
                category = "native-libraries"
            elif name.endswith(".dex"):
                category = "dex"
            elif name.startswith("assets/") or "/assets/" in name:
                category = "assets"
            elif name.startswith("res/") or "/res/" in name:
                category = "resources"
            else:
                category = "other"
            stat = category_stats[category]
            stat["files"] += 1
            stat["compressed"] += item.compress_size
            stat["uncompressed"] += item.file_size

        compressed_total = sum(item.compress_size for item in infos)
        uncompressed_total = sum(item.file_size for item in infos)
        abis = sorted(abi_stats)
        is_aab = source.suffix.lower() == ".aab"
        lines = [
            "SANDIUM_BRAVE_SIZE_AUDIT=1",
            f"FILE={source.name}",
            f"FORMAT={'AAB' if is_aab else 'APK'}",
            f"FILE_SIZE_BYTES={source.stat().st_size}",
            f"FILE_SIZE_HUMAN={human(source.stat().st_size)}",
            f"ZIP_ENTRY_COMPRESSED_BYTES={compressed_total}",
            f"ZIP_ENTRY_UNCOMPRESSED_BYTES={uncompressed_total}",
            f"ZIP_ENTRY_COUNT={len(infos)}",
            f"ABI_SET={','.join(abis) if abis else 'none-detected'}",
        ]

        for abi in abis:
            stat = abi_stats[abi]
            lines.append(
                f"ABI[{abi}]=files:{stat['files']},"
                f"compressed:{stat['compressed']}({human(stat['compressed'])}),"
                f"uncompressed:{stat['uncompressed']}({human(stat['uncompressed'])})"
            )

        for machine, count in sorted(elf_stats.items()):
            lines.append(f"ELF_MACHINE[{machine}]={count}")

        for category in ("native-libraries", "dex", "assets", "resources", "other"):
            stat = category_stats[category]
            if stat["files"]:
                lines.append(
                    f"CATEGORY[{category}]=files:{stat['files']},"
                    f"compressed:{stat['compressed']}({human(stat['compressed'])}),"
                    f"uncompressed:{stat['uncompressed']}({human(stat['uncompressed'])})"
                )

        lines.append("LARGEST_ENTRIES_BY_UNCOMPRESSED_SIZE:")
        for item in largest:
            lines.append(
                f"  {human(item.file_size):>12} uncompressed | "
                f"{human(item.compress_size):>12} compressed | {item.filename}"
            )

        lines.append(f"SYMBOL_NAMED_ENTRY_COUNT={len(symbol_named)}")
        for name, size in sorted(symbol_named, key=lambda pair: pair[1], reverse=True)[:20]:
            lines.append(f"  SYMBOL_ENTRY {human(size)} | {name}")

        if "arm64-v8a" in abis and "armeabi-v7a" in abis:
            lines.append("ABI_FOOTPRINT=ARM64_PLUS_32_BIT")
            lines.append("SIZE_FINDING=32-bit and 64-bit native libraries are both packaged.")
        elif abis == ["arm64-v8a"]:
            lines.append("ABI_FOOTPRINT=ARM64_ONLY")
        else:
            lines.append("ABI_FOOTPRINT=REVIEW_REQUIRED")

        lines.append(
            "NOTE=Symbol-named files are listed; embedded ELF debug sections require "
            "a separate ELF section-table inspection."
        )
        lines.append("APK_SIZE_AUDIT=PASS")
        return chr(10).join(lines) + chr(10)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="Brave APK or AAB to inspect")
    parser.add_argument("--output", type=Path, help="write report to this file")
    args = parser.parse_args()
    report = make_report(args.file)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    print(report, end="")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (zipfile.BadZipFile, OSError) as error:
        print(f"APK_SIZE_AUDIT=FAIL {error}", file=sys.stderr)
        raise SystemExit(2)
