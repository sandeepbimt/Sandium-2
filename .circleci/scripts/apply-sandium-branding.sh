#!/usr/bin/env bash
set -euo pipefail

ROOT="$CIRCLE_WORKING_DIRECTORY"
SRC_DIR="$ROOT/brave-work/src"
CORE_DIR="$SRC_DIR/brave"
BRAND_DIR="$ROOT/.circleci/branding"
CHROMIUM_PIN="d331de35ca8ab1358c7a17e4bd41627d55eaef51"
BRAVE_PIN="v1.98.62"

fail() {
  echo "SANDIUM_BRANDING_GATE=FAIL $*" >&2
  exit 1
}

[ -d "$SRC_DIR/.git" ] || fail "Chromium source checkout is missing"
[ -d "$CORE_DIR/.git" ] || fail "Brave source checkout is missing"
actual_chromium="$(git -C "$SRC_DIR" rev-parse HEAD 2>/dev/null || true)"
actual_brave="$(git -C "$CORE_DIR" describe --tags --exact-match 2>/dev/null || true)"
[ "$actual_chromium" = "$CHROMIUM_PIN" ] || fail "unexpected Chromium source pin: $actual_chromium"
[ "$actual_brave" = "$BRAVE_PIN" ] || fail "unexpected Brave source pin: $actual_brave"
echo "SANDIUM_BRANDING_SOURCE_GATE=PASS brave=$actual_brave chromium=$actual_chromium"

RESOURCE_DIR="$SRC_DIR/chrome/android/java/res_chromium_base"
for name in app_icon.png layered_app_icon.png layered_app_icon_background.png; do
  source="$BRAND_DIR/mipmap-xxxhdpi/$name"
  [ -s "$source" ] || fail "missing checked-in branding asset: $source"
done
mkdir -p "$RESOURCE_DIR/mipmap-xxxhdpi"
cp "$BRAND_DIR/mipmap-xxxhdpi/app_icon.png" "$RESOURCE_DIR/mipmap-xxxhdpi/app_icon.png"
cp "$BRAND_DIR/mipmap-xxxhdpi/layered_app_icon.png" "$RESOURCE_DIR/mipmap-xxxhdpi/layered_app_icon.png"
cp "$BRAND_DIR/mipmap-xxxhdpi/layered_app_icon_background.png" "$RESOURCE_DIR/mipmap-xxxhdpi/layered_app_icon_background.png"

python3 - "$SRC_DIR" <<'PY'
from pathlib import Path
import re
import sys

src = Path(sys.argv[1])

def replace_once(path: Path, old: str, new: str, gate: str) -> None:
    if not path.is_file():
        raise SystemExit(f"SANDIUM_BRANDING_GATE=FAIL missing upstream resource: {path}")
    content = path.read_text(encoding="utf-8")
    old_count = content.count(old)
    new_count = content.count(new)
    if old_count == 1 and new_count == 0:
        path.write_text(content.replace(old, new, 1), encoding="utf-8")
        print(f"{gate}=PATCHED")
    elif old_count == 0 and new_count == 1:
        print(f"{gate}=ALREADY_PATCHED")
    else:
        raise SystemExit(f"SANDIUM_BRANDING_GATE=FAIL {gate} marker counts old={old_count} new={new_count}")

# Keep one high-density master; Android scales the mipmap for other display densities.
gn = src / "chrome/android/BUILD.gn"
if not gn.is_file():
    raise SystemExit(f"SANDIUM_BRANDING_GATE=FAIL missing {gn}")
source = gn.read_text(encoding="utf-8")
pattern = re.compile(
    r'^\s*"java/res_chromium_base/mipmap-(?:hdpi|mdpi|xhdpi|xxhdpi)/'
    r'(?:app_icon|layered_app_icon|layered_app_icon_background)\.png",\s*\n',
    re.MULTILINE,
)
source, removed = pattern.subn("", source)
master = re.findall(
    r'^\s*"java/res_chromium_base/mipmap-xxxhdpi/'
    r'(?:app_icon|layered_app_icon|layered_app_icon_background)\.png",\s*$',
    source,
    re.MULTILINE,
)
if removed == 24 and len(master) == 6:
    gn.write_text(source, encoding="utf-8")
    print("SANDIUM_BRANDING_RESOURCE_DENSITY_GATE=PATCHED")
elif removed == 0 and len(master) == 6:
    print("SANDIUM_BRANDING_RESOURCE_DENSITY_GATE=ALREADY_PATCHED")
else:
    raise SystemExit(f"SANDIUM_BRANDING_GATE=FAIL resource list counts removed={removed} master={len(master)}")

launcher = src / "chrome/android/java/res_base/drawable/ic_launcher.xml"
replace_once(
    launcher,
    '<background android:drawable="@android:color/white"/>',
    '<background android:drawable="@mipmap/layered_app_icon_background"/>',
    "SANDIUM_BRANDING_ADAPTIVE_BACKGROUND",
)

foreground = src / "chrome/android/java/res_chromium_base/mipmap-nodpi/layered_app_icon_foreground.xml"
foreground.write_text(
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<bitmap xmlns:android="http://schemas.android.com/apk/res/android"\n'
    '    android:src="@mipmap/layered_app_icon"\n'
    '    android:gravity="center" />\n',
    encoding="utf-8",
)
print("SANDIUM_BRANDING_ADAPTIVE_FOREGROUND=PASS")

themed = src / "chrome/android/java/res_chromium_base/drawable/themed_app_icon.xml"
themed.write_text(
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<bitmap xmlns:android="http://schemas.android.com/apk/res/android"\n'
    '    android:src="@mipmap/layered_app_icon"\n'
    '    android:gravity="center" />\n',
    encoding="utf-8",
)
print("SANDIUM_BRANDING_THEMED_ICON=PASS")

manifest = src / "chrome/android/java/AndroidManifest.xml"
replace_once(
    manifest,
    'android:label="{% block application_label %}@string/app_name{% endblock %}"',
    'android:label="{% block application_label %}Sandium Browser{% endblock %}"',
    "SANDIUM_BRANDING_APP_LABEL",
)

checks = {
    launcher: '@mipmap/layered_app_icon_background',
    foreground: '@mipmap/layered_app_icon',
    themed: '@mipmap/layered_app_icon',
    manifest: 'Sandium Browser',
}
for path, marker in checks.items():
    if marker not in path.read_text(encoding="utf-8"):
        raise SystemExit(f"SANDIUM_BRANDING_GATE=FAIL post-write check missing {marker}")
print("SANDIUM_BRANDING_RESOURCE_GATE=PASS")
PY

for name in app_icon.png layered_app_icon.png layered_app_icon_background.png; do
  [ -s "$RESOURCE_DIR/mipmap-xxxhdpi/$name" ] || fail "branding asset was not copied: $name"
done
echo "SANDIUM_BRANDING_GATE=PASS app_label=Sandium Browser launcher=Sandium adaptive=enabled"
