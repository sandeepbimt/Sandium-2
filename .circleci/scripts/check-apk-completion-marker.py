#!/usr/bin/env python3
"""Validate a cached Sandium APK completion marker defensively.

Accepts LF/CRLF, an optional UTF-8 BOM, and surrounding whitespace. Reports
exactly which required flags are absent or not true.
"""
from __future__ import annotations

import sys
from pathlib import Path

REQUIRED = (
    "BUILD_FINISHED",
    "APK_ARCHIVE_VALID",
    "APK_SIGNATURE_VALID",
    "APK_PACKAGE_ID_VALID",
    "APK_BRANDING_VALID",
)


def read_marker(path: Path) -> dict[str, str]:
    raw = path.read_text(encoding="utf-8-sig")
    values: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check-apk-completion-marker.py <marker>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"APK_COMPLETION_MARKER=INVALID reason=missing path={path}")
        return 1
    try:
        values = read_marker(path)
    except (OSError, UnicodeError) as exc:
        print(f"APK_COMPLETION_MARKER=INVALID reason=unreadable error={exc}")
        return 1

    print(f"APK_COMPLETION_MARKER_PATH={path}")
    missing = []
    for key in REQUIRED:
        actual = values.get(key)
        print(f"{key}={actual if actual is not None else '<missing>'}")
        if actual != "true":
            missing.append(key)
    if missing:
        print("APK_COMPLETION_MARKER=INVALID failed_keys=" + ",".join(missing))
        return 1
    print("APK_COMPLETION_MARKER=VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
