"""Apply checked source edits to the pinned adblock-rust checkout."""

import argparse
from pathlib import Path

VENDOR = Path("third_party/rust/chromium_crates_io/vendor/adblock-v0_13/src")


def plan_vendor_edits(core, edits, feature):
    changes = {}
    installed = {}
    for name, before, after in edits:
        path = core / VENDOR / name
        current = changes[path] if path in changes else path.read_text()
        if current.count(after) == 1 and before not in current.replace(after, "", 1):
            installed.setdefault(path, set()).add(True)
        elif current.count(before) == 1 and after not in current:
            installed.setdefault(path, set()).add(False)
            changes[path] = current.replace(before, after, 1)
        else:
            raise ValueError(f"Unexpected {feature} source in {name}")
    if any(len(states) > 1 for states in installed.values()):
        raise ValueError(f"Incomplete {feature} installation")
    return changes


def apply_or_verify(plan, description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("core", type=Path)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    changes = plan(args.core)
    if changes and args.verify_only:
        parser.error("required native matcher changes are missing")
    for path, text in changes.items():
        path.write_text(text)
