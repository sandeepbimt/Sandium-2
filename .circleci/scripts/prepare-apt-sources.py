#!/usr/bin/env python3
"""Make CircleCI's APT source configuration deterministic before Chromium deps install.

Only exact duplicate legacy .list entries are disabled. Source files and unique
entries are preserved. APT transport retries are configured independently.
"""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

SOURCE_LINE = re.compile(
    r"^\s*(deb(?:-src)?)\s+(?:\[[^\]]+\]\s+)?(\S+)\s+(\S+)\s+(.+?)\s*$"
)
RETRY_CONFIG = """// Sandium: retry transient mirror/network failures during Android dependency setup.
Acquire::Retries "5";
Acquire::http::Timeout "30";
Acquire::https::Timeout "30";
Acquire::ftp::Timeout "30";
"""

def normalize(line: str) -> tuple[str, str, str, str] | None:
    match = SOURCE_LINE.match(line)
    if not match:
        return None
    source_type, options, uri, suite, components = match.groups()
    # Deduplicate only identical source declarations; preserve different arch/signed-by options.
    return source_type, (options or "").strip(), uri.rstrip("/"), suite, " ".join(components.split())

def prepare(directory: Path, retry_file: Path) -> dict[str, int]:
    directory.mkdir(parents=True, exist_ok=True)
    seen: dict[tuple[str, str, str, str], tuple[Path, int]] = {}
    changed_files = 0
    duplicate_lines = 0
    scanned_lines = 0

    for path in sorted(directory.glob("*.list")):
        original = path.read_text(encoding="utf-8", errors="replace")
        output: list[str] = []
        changed = False
        for number, line in enumerate(original.splitlines(keepends=True), start=1):
            key = normalize(line.rstrip("\r\n"))
            if key is None:
                output.append(line)
                continue
            scanned_lines += 1
            if key in seen:
                first_path, first_line = seen[key]
                ending = "\n" if line.endswith("\n") else ""
                body = line.rstrip("\r\n")
                output.append(
                    "# sandium-apt-deduplicated: "
                    f"{first_path.name}:{first_line}: {body}{ending}"
                )
                changed = True
                duplicate_lines += 1
                print(
                    "SANDIUM_APT_DUPLICATE_SOURCE=DISABLED "
                    f"duplicate={path.name}:{number} "
                    f"kept={first_path.name}:{first_line}"
                )
            else:
                seen[key] = (path, number)
                output.append(line)
        if changed:
            path.write_text("".join(output), encoding="utf-8")
            changed_files += 1

    retry_file.parent.mkdir(parents=True, exist_ok=True)
    if not retry_file.exists() or retry_file.read_text(encoding="utf-8") != RETRY_CONFIG:
        retry_file.write_text(RETRY_CONFIG, encoding="utf-8")

    print(
        "SANDIUM_APT_SOURCE_PREP=PASS "
        f"scanned={scanned_lines} duplicate_entries_disabled={duplicate_lines} "
        f"files_changed={changed_files} retries=5"
    )
    return {
        "scanned": scanned_lines,
        "duplicates": duplicate_lines,
        "files_changed": changed_files,
    }

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", type=Path, default=Path("/etc/apt/sources.list.d"))
    parser.add_argument("--retry-config", type=Path, default=Path("/etc/apt/apt.conf.d/80sandium-retries"))
    args = parser.parse_args()
    prepare(args.sources, args.retry_config)

if __name__ == "__main__":
    main()
