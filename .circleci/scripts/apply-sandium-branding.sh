#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "${CIRCLE_WORKING_DIRECTORY:?CIRCLE_WORKING_DIRECTORY is required}" && pwd)"
SRC_DIR="$ROOT/brave-work/src"
CORE_DIR="$SRC_DIR/brave"
SCRIPT_DIR="$ROOT/.circleci/scripts"
BRAND_DIR="$ROOT/.circleci/branding"
SOURCE_DIR="$BRAND_DIR/source"
GENERATED_DIR="$ROOT/.sandium-branding-generated"
GENERATOR="$SCRIPT_DIR/generate-sandium-density-assets.py"
CHROMIUM_PIN="d331de35ca8ab1358c7a17e4bd41627d55eaef51"
BRAVE_PIN="v1.98.62"
DENSITIES=(mdpi hdpi xhdpi xxhdpi xxxhdpi)
ASSETS=(app_icon.png layered_app_icon.png layered_app_icon_background.png)

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

[ -s "$GENERATOR" ] || fail "density generator not found at project-root path: $GENERATOR"
[ -d "$SOURCE_DIR" ] || fail "branding source directory missing: $SOURCE_DIR"
for name in "${ASSETS[@]}"; do
  [ -s "$SOURCE_DIR/$name" ] || fail "branding master image missing: $SOURCE_DIR/$name"
done

python3 "$GENERATOR" \
  --source-dir "$SOURCE_DIR" \
  --output-dir "$GENERATED_DIR" \
  --gn-file "$SRC_DIR/chrome/android/BUILD.gn"

RESOURCE_DIR="$SRC_DIR/chrome/android/java/res_chromium_base"
for density in "${DENSITIES[@]}"; do
  source_dir="$GENERATED_DIR/mipmap-$density"
  target_dir="$RESOURCE_DIR/mipmap-$density"
  mkdir -p "$target_dir"
  for name in "${ASSETS[@]}"; do
    source="$source_dir/$name"
    target="$target_dir/$name"
    [ -s "$source" ] || fail "generated density asset missing: $source"
    cp "$source" "$target"
  done
  echo "SANDIUM_BRANDING_DENSITY_COPY=PASS density=$density"
done

python3 - "$SRC_DIR" <<'PY'
from pathlib import Path
import struct
import sys

src = Path(sys.argv[1])
resource_root = src / "chrome/android/java/res_chromium_base"
expected_sizes = {
    "mdpi": 48,
    "hdpi": 72,
    "xhdpi": 96,
    "xxhdpi": 144,
    "xxxhdpi": 192,
}
assets = (
    "app_icon.png",
    "layered_app_icon.png",
    "layered_app_icon_background.png",
)
for density, size in expected_sizes.items():
    for name in assets:
        path = resource_root / f"mipmap-{density}" / name
        if not path.is_file():
            raise SystemExit(f"SANDIUM_BRANDING_GATE=FAIL copied resource missing: {path}")
        data = path.read_bytes()
        if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
            raise SystemExit(f"SANDIUM_BRANDING_GATE=FAIL invalid PNG: {path}")
        width, height = struct.unpack(">II", data[16:24])
        if (width, height) != (size, size):
            raise SystemExit(
                f"SANDIUM_BRANDING_GATE=FAIL wrong dimensions for {path}: "
                f"{width}x{height}; expected {size}x{size}"
            )
    print(f"SANDIUM_BRANDING_DENSITY_GATE=PASS density={density} size={size}")

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
        raise SystemExit(
            f"SANDIUM_BRANDING_GATE=FAIL {gate} marker counts old={old_count} new={new_count}"
        )

launcher = src / "chrome/android/java/res_base/drawable/ic_launcher.xml"
replace_once(
    launcher,
    '<background android:drawable="@android:color/white"/>',
    '<background android:drawable="@mipmap/layered_app_icon_background"/>',
    "SANDIUM_BRANDING_ADAPTIVE_BACKGROUND",
)

foreground = resource_root / "mipmap-nodpi/layered_app_icon_foreground.xml"
foreground.write_text(
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<bitmap xmlns:android="http://schemas.android.com/apk/res/android"\n'
    '    android:src="@mipmap/layered_app_icon"\n'
    '    android:gravity="center" />\n',
    encoding="utf-8",
)
print("SANDIUM_BRANDING_ADAPTIVE_FOREGROUND=PASS")

themed = resource_root / "drawable/themed_app_icon.xml"
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

echo "SANDIUM_BRANDING_GATE=PASS app_label=Sandium Browser densities=mdpi,hdpi,xhdpi,xxhdpi,xxxhdpi adaptive=enabled"

# Apply the first Sandium-native Shields UI adaptation after the source pin
# has been verified and before the Android build graph is generated.
bash "$SCRIPT_DIR/apply-sandium-shields-ui.sh"
