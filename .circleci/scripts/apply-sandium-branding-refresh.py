#!/usr/bin/env python3
"""Apply the Sandium Android brand refresh to the pinned Brave/Chromium source."""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
from pathlib import Path

EXPECTED_CORE_TAG = "v1.98.62"
EXPECTED_CORE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
EXPECTED_CHROMIUM_SHA = "d331de35ca8ab1358c7a17e4bd41627d55eaef51"

ASSETS = {
    "icon.webp": "dbddd3838a9995ead3ef456a8ab964b7142e4c255232f1e27daf57572a73b3fe",
    "logo-mark.webp": "1f2f20b55c3a1d1ccdcaed4024eb88b31e9b763d5d63b73b68727f1247b127c2",
    "wallpaper.webp": "6f4e5c7ca70a0b0c69ab27874b7a878a9c8a98de34fee706b24a06f8af5ed842",
}

def read(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"required source file is missing: {path}")
    return path.read_text(encoding="utf-8")

def write(path: Path, content: str, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file() or path.read_text(encoding="utf-8") != content:
        path.write_text(content, encoding="utf-8")
    if path.read_text(encoding="utf-8") != content:
        raise RuntimeError(f"{label}: post-write verification failed")
    print(f"SANDIUM_BRANDING_PATCH={label}:PASS")

def replace_once(path: Path, old: str, new: str, label: str) -> None:
    source = read(path)
    if new in source:
        print(f"SANDIUM_BRANDING_PATCH={label}:ALREADY_APPLIED")
        return
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one source anchor, found {count}: {path}")
    write(path, source.replace(old, new, 1), label)

def replace_android_icon_item(path: Path, element: str, drawable: str, label: str) -> None:
    """Set one adaptive-icon element regardless of the checkpoint's prior drawable."""
    source = read(path)
    pattern = re.compile(r"<" + re.escape(element) + r"\\b[^>]*/>")
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        raise RuntimeError(
            f"{label}: expected one <{element}> element, found {len(matches)}: {path}"
        )
    replacement = f'<{element} android:drawable="{drawable}"/>'
    if matches[0].group(0) == replacement:
        print(f"SANDIUM_BRANDING_PATCH={label}:ALREADY_APPLIED")
        return
    updated = source[:matches[0].start()] + replacement + source[matches[0].end():]
    write(path, updated, label)

def remove_once(path: Path, old: str, label: str) -> None:
    source = read(path)
    if old not in source:
        print(f"SANDIUM_BRANDING_PATCH={label}:ALREADY_APPLIED")
        return
    if source.count(old) != 1:
        raise RuntimeError(f"{label}: expected one import to remove, found {source.count(old)}")
    write(path, source.replace(old, "", 1), label)

def add_gn_source(path: Path, anchor: str, addition: str, label: str) -> None:
    source = read(path)
    if addition in source:
        print(f"SANDIUM_BRANDING_PATCH={label}:ALREADY_APPLIED")
        return
    count = source.count(anchor)
    if count < 1:
        raise RuntimeError(f"{label}: GN anchor missing")
    # Chromium lists shared base resources in both the base-module and
    # override-module targets; register the new assets in every matching list.
    write(path, source.replace(anchor, anchor + addition), label)

def git_value(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()

def verify_pins(core: Path, src: Path) -> None:
    actual_tag = git_value(core, "describe", "--tags", "--exact-match")
    actual_core = git_value(core, "rev-parse", "HEAD")
    actual_chromium = git_value(src, "rev-parse", "HEAD")
    expected = (EXPECTED_CORE_TAG, EXPECTED_CORE_SHA, EXPECTED_CHROMIUM_SHA)
    actual = (actual_tag, actual_core, actual_chromium)
    if actual != expected:
        raise RuntimeError(
            "SANDIUM_BRANDING_PIN_GATE=FAIL "
            f"expected={expected!r} actual={actual!r}"
        )
    print(
        "SANDIUM_BRANDING_PIN_GATE=PASS "
        f"brave={actual_tag}@{actual_core} chromium={actual_chromium}"
    )

def install_asset(source_dir: Path, name: str, destination: Path) -> None:
    source = source_dir / name
    if not source.is_file():
        raise RuntimeError(f"missing official Sandium asset: {source}")
    payload = source.read_bytes()
    if payload[:4] != b"RIFF" or payload[8:12] != b"WEBP":
        raise RuntimeError(f"asset is not a valid WebP: {source}")
    digest = hashlib.sha256(payload).hexdigest()
    if digest != ASSETS[name]:
        raise RuntimeError(f"asset checksum mismatch for {name}: {digest}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.is_file() or destination.read_bytes() != payload:
        shutil.copyfile(source, destination)
    if destination.read_bytes() != payload:
        raise RuntimeError(f"asset copy verification failed: {destination}")
    print(f"SANDIUM_BRANDING_ASSET={name}:PASS sha256={digest}")

def replace_toolbar_method(core: Path) -> None:
    path = core / "android/java/org/chromium/chrome/browser/toolbar/top/BraveToolbarLayoutImpl.java"
    source = read(path)
    start = "    private void setRewardsLayoutVisibility(int visibility) {"
    end = "    private void requestToolbarSnapshotCapture() {"
    begin = source.find(start)
    finish = source.find(end, begin + len(start))
    if begin < 0 or finish < 0:
        raise RuntimeError("toolbar Rewards visibility method anchors changed")
    replacement = """    private void setRewardsLayoutVisibility(int requestedVisibility) {
        if (mRewardsLayout == null || mRewardsLayout.getVisibility() == View.GONE) {
            return;
        }
        // Sandium hides only the toolbar affordance. Rewards services, settings,
        // native components and policy handling remain intact.
        mRewardsLayout.setVisibility(View.GONE);
        updateShieldsLayoutBackground(true);
        if (BraveReflectionUtil.equalTypes(this.getClass(), ToolbarTablet.class)) {
            post(mRewardsLayout::requestLayout);
            invalidateToolbarSnapshotOnTablet();
        }
    }

"""
    method = source[begin:finish]
    if "mRewardsLayout.setVisibility(View.GONE);" in method and "requestedVisibility" in method:
        print("SANDIUM_BRANDING_PATCH=hide-toolbar-rewards:ALREADY_APPLIED")
    else:
        write(path, source[:begin] + replacement + source[finish:], "hide-toolbar-rewards")

    source = read(path)
    start = "    public void updateBraveShieldsButtonState(Tab tab) {"
    end = "    private boolean isShieldsOnForTab(Tab tab) {"
    begin = source.find(start)
    finish = source.find(end, begin + len(start))
    if begin < 0 or finish < 0:
        raise RuntimeError("toolbar Shields state method anchors changed")
    replacement = """    public void updateBraveShieldsButtonState(Tab tab) {
        if (mBraveShieldsButton == null) {
            assert false;
            return;
        }

        // Keep Brave's original state semantics: null-tab and Shields-off states
        // are subdued; a real tab with Shields enabled uses the full-strength mark.
        boolean shieldsEnabled = tab != null && isShieldsOnForTab(tab);
        mBraveShieldsButton.setImageResource(R.drawable.sandium_toolbar_mark);
        mBraveShieldsButton.setImageAlpha(shieldsEnabled ? 255 : 112);

        // Hide only the toolbar Rewards/BAT view. Do not disable the Rewards backend.
        setRewardsLayoutVisibility(View.GONE);
        updateShieldsLayoutBackground(true);
    }

"""
    method = source[begin:finish]
    if "R.drawable.sandium_toolbar_mark" in method and "setImageAlpha(shieldsEnabled ? 255 : 112)" in method:
        print("SANDIUM_BRANDING_PATCH=toolbar-shields-mark:ALREADY_APPLIED")
    else:
        write(path, source[:begin] + replacement + source[finish:], "toolbar-shields-mark")

def apply(args: argparse.Namespace) -> None:
    core = args.core.resolve()
    src = args.src.resolve()
    root = args.repo_root.resolve()
    verify_pins(core, src)

    source_dir = root / ".circleci/branding/source"
    install_asset(source_dir, "icon.webp",
                  src / "chrome/android/java/res_chromium_base/mipmap-nodpi/sandium_app_icon.webp")
    install_asset(source_dir, "logo-mark.webp",
                  src / "chrome/android/java/res_chromium_base/drawable-nodpi/sandium_themed_app_icon.webp")
    install_asset(source_dir, "logo-mark.webp",
                  core / "android/java/brave-res/drawable-nodpi/sandium_toolbar_mark.webp")
    install_asset(source_dir, "wallpaper.webp",
                  core / "android/java/brave-res/drawable-nodpi/sandium_wallpaper.webp")

    chrome_build = src / "chrome/android/BUILD.gn"
    add_gn_source(
        chrome_build,
        '      "java/res_chromium_base/drawable/themed_app_icon.xml",\n',
        '      "java/res_chromium_base/drawable-nodpi/sandium_themed_app_icon.webp",\n'
        '      "java/res_chromium_base/mipmap-nodpi/sandium_app_icon.webp",\n',
        "register-chromium-brand-assets",
    )
    brave_build = core / "android/BUILD.gn"
    add_gn_source(
        brave_build,
        '    "java/brave-res/drawable-nodpi/dylan_malval_sea_min.webp",\n',
        '    "java/brave-res/drawable-nodpi/sandium_toolbar_mark.webp",\n'
        '    "java/brave-res/drawable-nodpi/sandium_wallpaper.webp",\n',
        "register-brave-brand-assets",
    )

    launcher = src / "chrome/android/java/res_base/drawable/ic_launcher.xml"
    replace_android_icon_item(launcher, "background", "@android:color/black", "launcher-background")
    replace_android_icon_item(launcher, "foreground", "@mipmap/sandium_app_icon", "launcher-foreground")
    replace_android_icon_item(launcher, "monochrome", "@drawable/sandium_themed_app_icon", "launcher-monochrome")

    launcher_round = src / "chrome/android/java/res_base/drawable/ic_launcher_round.xml"
    replace_android_icon_item(launcher_round, "background", "@android:color/black", "round-launcher-background")
    replace_android_icon_item(launcher_round, "foreground", "@mipmap/sandium_app_icon", "round-launcher-foreground")
    replace_android_icon_item(launcher_round, "monochrome", "@drawable/sandium_themed_app_icon", "round-launcher-monochrome")
    replace_once(
        src / "chrome/android/java/AndroidManifest.xml",
        'android:label="{% block application_label %}@string/app_name{% endblock %}"',
        'android:label="{% block application_label %}Sandium{% endblock %}"',
        "application-label",
    )

    toolbar_xml = core / "android/java/brave-res/layout/brave_toolbar.xml"
    replace_once(
        toolbar_xml,
        'android:src="@drawable/ic_social_brave_release_favicon_fullheight_color"',
        'android:src="@drawable/sandium_toolbar_mark"',
        "toolbar-layout-mark",
    )
    custom_tabs_xml = core / "android/java/brave-res/layout/brave_custom_tabs_toolbar.xml"
    replace_once(
        custom_tabs_xml,
        'android:src="@drawable/ic_social_brave_release_favicon_fullheight_color"',
        'android:src="@drawable/sandium_toolbar_mark"',
        "custom-tabs-toolbar-mark",
    )
    replace_toolbar_method(core)

    strings = core / "browser/ui/android/strings/android_brave_strings.grd"
    replace_once(
        strings,
        "Note: this may reduce Brave's privacy protections.",
        "Note: this may reduce Sandium's privacy protections.",
        "shields-warning-copy",
    )
    replace_once(
        strings,
        "Enable/Disable Brave Shields",
        "Open Sandium protection controls",
        "shields-accessibility-copy",
    )

    sponsored = core / "android/java/org/chromium/chrome/browser/ntp_background_images/util/SponsoredContentUtil.java"
    remove_once(
        sponsored,
        "import org.chromium.chrome.browser.ntp_background_images.model.ImageCredit;",
        "remove-unused-wallpaper-credit-import",
    )
    replace_once(
        sponsored,
        """    private static final List<BackgroundImage> sBackgroundImages =
            new ArrayList<BackgroundImage>(
                    Arrays.asList(
                            new BackgroundImage(
                                    R.drawable.dylan_malval_sea_min,
                                    1300,
                                    720,
                                    new ImageCredit(
                                            "Dylan Malval",
                                            "https://www.instagram.com/vass_captures/"))));
""",
        """    private static final List<BackgroundImage> sBackgroundImages =
            new ArrayList<BackgroundImage>(
                    Arrays.asList(new BackgroundImage(R.drawable.sandium_wallpaper, 270, 480)));
""",
        "ntp-default-wallpaper",
    )

    bridge = core / "android/java/org/chromium/chrome/browser/ntp_background_images/NTPBackgroundImagesBridge.java"
    bridge_source = read(bridge)
    if "import org.chromium.base.ContextUtils;" not in bridge_source:
        bridge_source = bridge_source.replace(
            "import org.chromium.base.Callback;\n",
            "import org.chromium.base.Callback;\nimport org.chromium.base.ContextUtils;\n",
            1,
        )
        write(bridge, bridge_source, "wallpaper-resource-context-import")
    if "import org.chromium.chrome.R;" not in bridge_source:
        bridge_source = bridge_source.replace(
            "import org.chromium.base.ThreadUtils;\n",
            "import org.chromium.base.ThreadUtils;\n\nimport org.chromium.chrome.R;\n",
            1,
        )
    if bridge_source != read(bridge):
        write(bridge, bridge_source, "wallpaper-resource-imports")
    remove_once(
        bridge,
        "import org.chromium.chrome.browser.ntp_background_images.model.ImageCredit;",
        "remove-unused-wallpaper-credit-import",
    )
    replace_once(
        bridge,
        """    public static BackgroundImage createWallpaper(String imagePath, String author, String link) {
        return new BackgroundImage(imagePath, 0, 0, new ImageCredit(author, link));
    }
""",
        """    public static BackgroundImage createWallpaper(String imagePath, String author, String link) {
        return new BackgroundImage(R.drawable.sandium_wallpaper, 270, 480);
    }
""",
        "normal-wallpaper-callback",
    )
    replace_once(
        bridge,
        """        // The metricType int value can be passed directly since @IntDef just validates the value
        return new Wallpaper(
                imagePath,
                focalPointX,
                focalPointY,
                logoPath,
                logoDestinationUrl,
                isSponsored,
                creativeInstanceId,
                wallpaperId,
                isRichMedia,
                metricType);
""",
        """        // Replace remote/branded artwork with the bundled Sandium wallpaper while
        // preserving the callback contract and using the installed app's resource URI.
        String resourceUri =
                "android.resource://"
                        + ContextUtils.getApplicationContext().getPackageName()
                        + "/drawable/sandium_wallpaper";
        return new Wallpaper(
                resourceUri,
                focalPointX,
                focalPointY,
                null,
                "",
                false,
                "",
                "",
                false,
                metricType);
""",
        "branded-wallpaper-callback",
    )

    image_util = core / "android/java/org/chromium/chrome/browser/ntp_background_images/util/NTPImageUtil.java"
    replace_once(
        image_util,
        '        Uri imageFileUri = Uri.parse("file://" + imagePath);',
        '        Uri imageFileUri = imagePath.startsWith("android.resource://")\n'
        '                ? Uri.parse(imagePath)\n'
        '                : Uri.parse("file://" + imagePath);',
        "android-resource-wallpaper-uri",
    )

    ntp_layout = core / "android/java/org/chromium/chrome/browser/ntp/BraveNewTabPageLayout.java"
    replace_once(
        ntp_layout,
        """                && mNtpImageGlobal instanceof Wallpaper
                && getTab() != null
""",
        """                && mNtpImageGlobal instanceof Wallpaper
                && ((Wallpaper) mNtpImageGlobal).isSponsored()
                && getTab() != null
""",
        "sponsored-infobar-guard",
    )

    # The pinned Brave source already registers this preference as true. Do not
    # write a profile preference here: existing users' explicit setting is preserved.
    pref_registry = core / "components/ntp_background_images/browser/view_counter_pref_registry.cc"
    pref_source = read(pref_registry)
    if "RegisterBooleanPref(prefs::kNewTabPageShowBackgroundImage, true);" not in pref_source:
        raise RuntimeError("fresh-profile wallpaper default is no longer true; review before changing")
    print("SANDIUM_BRANDING_NTP_DEFAULT=PASS fresh_profile=true user_override=preserved")
    print("SANDIUM_BRANDING_GATE=PASS mode=android-resource-java")
    
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--src", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    apply(parser.parse_args())

if __name__ == "__main__":
    main()
