#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "${CIRCLE_WORKING_DIRECTORY:?CIRCLE_WORKING_DIRECTORY is required}" && pwd)"
CORE_DIR="$ROOT/brave-work/src/brave"
STRINGS_FILE="$CORE_DIR/browser/ui/android/strings/android_brave_strings.grd"

fail() {
  echo "SANDIUM_SHIELDS_UI_GATE=FAIL $*" >&2
  exit 1
}

[ -s "$STRINGS_FILE" ] || fail "pinned Brave Android string source is missing: $STRINGS_FILE"

python3 - "$STRINGS_FILE" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
source = path.read_text(encoding="utf-8")

def update_message(message_id: str, old_text: str, new_text: str, gate: str) -> None:
    global source
    pattern = re.compile(
        rf'(<message\s+name="{re.escape(message_id)}"[^>]*>)(.*?)(</message>)',
        re.DOTALL,
    )
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        raise SystemExit(
            f"SANDIUM_SHIELDS_UI_GATE=FAIL {gate}: expected one message, found {len(matches)}"
        )

    match = matches[0]
    body = match.group(2)
    old_count = body.count(old_text)
    new_count = body.count(new_text)

    if old_count == 1 and new_count == 0:
        body = body.replace(old_text, new_text, 1)
        source = source[:match.start(2)] + body + source[match.end(2):]
        print(f"{gate}=PATCHED")
    elif old_count == 0 and new_count == 1:
        print(f"{gate}=ALREADY_PATCHED")
    else:
        raise SystemExit(
            f"SANDIUM_SHIELDS_UI_GATE=FAIL {gate}: old={old_count} new={new_count}"
        )

update_message(
    "IDS_CREATE_CUSTOM_FILTERS_TITLE",
    "Create custom filters",
    "My filters",
    "SANDIUM_MY_FILTERS_TITLE",
)

update_message(
    "IDS_CREATE_CUSTOM_FILTER_SUMMARY",
    "Add custom filters you've created, one per line, in the field above. Be sure to use the <ph name=\"ADBLOCK_FILTER_SYNTAX\">%1$s</ph>.",
    "Add supported uBlock Origin-style filter rules, one per line, using the <ph name=\"ADBLOCK_FILTER_SYNTAX\">%1$s</ph>. Sandium applies saved rules through its built-in Shields engine.",
    "SANDIUM_MY_FILTERS_GUIDANCE",
)

path.write_text(source, encoding="utf-8")
verified = path.read_text(encoding="utf-8")
if verified.count("My filters") != 1:
    raise SystemExit("SANDIUM_SHIELDS_UI_GATE=FAIL title post-write check failed")
if "Sandium applies saved rules through its built-in Shields engine." not in verified:
    raise SystemExit("SANDIUM_SHIELDS_UI_GATE=FAIL guidance post-write check failed")
print("SANDIUM_SHIELDS_UI_GATE=PASS")
PY

echo "SANDIUM_SHIELDS_UI=PASS screen_title='My filters' native_engine='Brave Shields'"
