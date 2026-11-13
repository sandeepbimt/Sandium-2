#!/usr/bin/env python3
"""Source-level acceptance checks for the Sandium branding refresh overlay."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import xml.etree.ElementTree as ET

EXPECTED = {
    "icon.webp": "dbddd3838a9995ead3ef456a8ab964b7142e4c255232f1e27daf57572a73b3fe",
    "logo-mark.webp": "1f2f20b55c3a1d1ccdcaed4024eb88b31e9b763d5d63b73b68727f1247b127c2",
    "wallpaper.webp": "6f4e5c7ca70a0b0c69ab27874b7a878a9c8a98de34fee706b24a06f8af5ed842",
}

def require(path: Path, *needles: str) -> str:
    if not path.is_file():
        raise SystemExit(f"SANDIUM_BRANDING_TEST=FAIL missing={path}")
    text = path.read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SystemExit(f"SANDIUM_BRANDING_TEST=FAIL path={path} missing={missing!r}")
    return text

SHIELDS_COPY = {
    "IDS_SHIELDS_WARNING_LINE2": "Note: this may reduce Brave's privacy protections.",
    "IDS_ACCESSIBILITY_TOOLBAR_BTN_BRAVE_SHIELDS": "Enable/Disable Brave Shields",
}

def verify_shields_copy(path: Path, *, final: bool = False) -> None:
    """Validate semantics by ID, including sources restored after the final overlay.

    Early preparation may see either pinned upstream copy or a previously branded
    checkpoint. The final pass permits only Sandium. Never accept missing labels,
    duplicates, nested content, or a weaker privacy warning.
    """
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise SystemExit(f"SANDIUM_BRANDING_TEST=FAIL invalid_strings={path}: {exc}")
    for name, upstream in SHIELDS_COPY.items():
        matches = [m for m in root.iter("message") if m.get("name") == name]
        allowed = {upstream.replace("Brave", "Sandium")}
        if not final:
            allowed.add(upstream)
        if (len(matches) != 1 or len(matches[0]) != 0
                or (matches[0].text or "").strip() not in allowed):
            raise SystemExit(f"SANDIUM_BRANDING_TEST=FAIL path={path} message={name} invalid_copy")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--src", type=Path, required=True)
    args = parser.parse_args()
    core, src = args.core.resolve(), args.src.resolve()

    for name, digest in EXPECTED.items():
        if name == "icon.webp":
            path = src / "chrome/android/java/res_chromium_base/mipmap-nodpi/sandium_app_icon.webp"
        elif name == "logo-mark.webp":
            path = core / "android/java/brave-res/drawable-nodpi/sandium_toolbar_mark.webp"
        else:
            path = core / "android/java/brave-res/drawable-nodpi/sandium_wallpaper.webp"
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise SystemExit(f"SANDIUM_BRANDING_TEST=FAIL asset={path}")
        payload = path.read_bytes()
        if payload[:4] != b"RIFF" or payload[8:12] != b"WEBP":
            raise SystemExit(f"SANDIUM_BRANDING_TEST=FAIL invalid_webp={path}")

    themed_logo = src / "chrome/android/java/res_chromium_base/drawable-nodpi/sandium_themed_app_icon.webp"
    if not themed_logo.is_file() or hashlib.sha256(themed_logo.read_bytes()).hexdigest() != EXPECTED["logo-mark.webp"]:
        raise SystemExit(f"SANDIUM_BRANDING_TEST=FAIL themed_asset={themed_logo}")

    require(
        src / "chrome/android/java/res_base/drawable/ic_launcher.xml",
        '@drawable/sandium_app_icon_inset',
        '@drawable/sandium_themed_app_icon',
    )
    require(
        src / "chrome/android/java/res_base/drawable/ic_launcher_round.xml",
        '@drawable/sandium_app_icon_inset',
        '@drawable/sandium_themed_app_icon',
    )
    manifest = require(src / "chrome/android/java/AndroidManifest.xml", 'application_label %}Sandium{% endblock %}')
    if "Sandium Browser" in manifest:
        raise SystemExit("SANDIUM_BRANDING_TEST=FAIL obsolete app label remains")
    require(
        src / "chrome/android/java/res_base/drawable/sandium_app_icon_inset.xml",
        'android:drawable="@mipmap/sandium_app_icon"',
        'android:inset="8%"',
    )
    require(
        core / "android/java/org/chromium/chrome/browser/toolbar/top/BraveToolbarLayoutImpl.java",
        'R.drawable.sandium_toolbar_mark',
        'setImageAlpha(shieldsEnabled ? 255 : 112)',
        'class SandiumShieldsTracer',
        'tracer.setEnabled(shieldsEnabled)',
        'length * 0.35f',
        'ValueAnimator.areAnimatorsEnabled()',
        'unscheduleSelf(this)',
        'mRewardsLayout.setVisibility(View.GONE)',
    )
    require(
        core / "android/java/brave-res/layout/brave_toolbar.xml",
        '@drawable/sandium_toolbar_mark',
    )
    require(
        core / "android/java/brave-res/layout/brave_custom_tabs_toolbar.xml",
        '@drawable/sandium_toolbar_mark',
    )
    for path in (
        core / "android/java/org/chromium/chrome/browser/toolbar/top/BraveToolbarLayoutImpl.java",
        core / "android/java/brave-res/layout/brave_toolbar.xml",
    ):
        text = path.read_text()
        if "sandium_shields_glow" in text or "RenderEffect.createBlurEffect" in text:
            raise SystemExit("SANDIUM_BRANDING_TEST=FAIL obsolete glow remains")
    # A restored checkpoint can already contain the later visible-branding pass.
    verify_shields_copy(core / "browser/ui/android/strings/android_brave_strings.grd")
    require(
        core / "android/java/org/chromium/chrome/browser/ntp_background_images/util/SponsoredContentUtil.java",
        "R.drawable.sandium_wallpaper",
    )
    require(
        core / "android/java/org/chromium/chrome/browser/ntp_background_images/NTPBackgroundImagesBridge.java",
        '"/drawable/sandium_wallpaper"',
        "R.drawable.sandium_wallpaper",
        "import org.chromium.chrome.R;",
        "false,",
    )
    require(
        core / "android/java/org/chromium/chrome/browser/ntp_background_images/util/NTPImageUtil.java",
        'imagePath.startsWith("android.resource://")',
    )
    require(
        core / "android/java/org/chromium/chrome/browser/ntp/BraveNewTabPageLayout.java",
        "((Wallpaper) mNtpImageGlobal).isSponsored()",
    )
    require(
        core / "components/ntp_background_images/common/view_counter_pref_registry.cc",
        "RegisterBooleanPref(prefs::kNewTabPageShowBackgroundImage, true);",
    )
    chrome_build = require(
        src / "chrome/android/BUILD.gn",
        'android_resources("chrome_base_module_resources") {',
        'android_resources("chrome_public_apk_base_module_resources") {',
        "java/res_base/drawable/ic_launcher.xml",
        "java/res_chromium_base/mipmap-nodpi/sandium_app_icon.webp",
        "java/res_chromium_base/drawable-nodpi/sandium_themed_app_icon.webp",
    )
    base_header = 'android_resources("chrome_base_module_resources") {'
    override_header = 'android_resources("chrome_public_apk_base_module_resources") {'
    base_start = chrome_build.find(base_header)
    override_start = chrome_build.find(override_header)
    override_end = chrome_build.find("\n  version_resource_dir =", override_start)
    if base_start < 0 or override_start <= base_start or override_end <= override_start:
        raise SystemExit("SANDIUM_BRANDING_TEST=FAIL Chromium resource target boundaries are missing")
    base_target = chrome_build[base_start:override_start]
    override_target = chrome_build[override_start:override_end]
    inset_source = '"java/res_base/drawable/sandium_app_icon_inset.xml"'
    if base_target.count(inset_source) != 1 or inset_source in override_target:
        raise SystemExit(
            "SANDIUM_BRANDING_TEST=FAIL launcher inset must be listed only in "
            "chrome_base_module_resources, not the res_chromium_base overlay target"
        )
    require(
        core / "android/BUILD.gn",
        "java/brave-res/drawable-nodpi/sandium_toolbar_mark.webp",
        "java/brave-res/drawable-nodpi/sandium_wallpaper.webp",
    )
    print("SANDIUM_BRANDING_TEST=PASS launcher=pass toolbar=pass rewards_hidden=pass popup=pass wallpaper=pass pref_preserved=pass")
if __name__ == "__main__":
    main()
