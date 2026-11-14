#!/usr/bin/env python3
"""Acceptance checks for Sandium's annotated Brave UI policy."""
from __future__ import annotations
import argparse
import re
from pathlib import Path

def read(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"SANDIUM_UI_TEST=FAIL missing={path}")
    return path.read_text(encoding="utf-8")

def require(path: Path, *needles: str) -> str:
    content = read(path)
    missing = [needle for needle in needles if needle not in content]
    if missing:
        raise SystemExit(f"SANDIUM_UI_TEST=FAIL path={path} missing={missing!r}")
    return content

UI_COPY = {
    "IDS_BRAVE_SHIELDS_AND_PRIVACY": "Brave Shields & privacy",
    "IDS_PREFS_SECTION_BRAVE_SHIELDS_GLOBALS": "Brave shields global defaults",
    "IDS_PREFS_USE_CUSTOM_TABS_TITLE": "Open external links in Brave",
    "IDS_SETTINGS_APP_LINKS_LABEL": "Allow app links to open in apps outside of Brave",
    "IDS_PREFS_CLOSING_ALL_TABS_CLOSES_BRAVE": "Closing all tabs closes Brave",
}


def verify_message_copy(path, expected, final=False):
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(read(path))
    except ET.ParseError as exc:
        raise SystemExit(f"SANDIUM_UI_TEST=FAIL malformed GRD: {path}: {exc}")
    for name, upstream in expected.items():
        messages = root.findall(f".//message[@name='{name}']")
        allowed = {upstream.replace("Brave", "Sandium")}
        if not final:
            allowed.add(upstream)
        if (len(messages) != 1 or len(messages[0]) != 0
                or (messages[0].text or "").strip() not in allowed):
            raise SystemExit(f"SANDIUM_UI_TEST=FAIL {name}: expected exact browser identity copy")


def verify_ui_identity(core, src, final=False):
    # Early gates see either functional-overlay text or a fully branded checkpoint.
    # Match stable IDs and exact copy; unrelated text must never satisfy the gate.
    verify_message_copy(core / "browser/ui/android/strings/android_brave_strings.grd",
                        UI_COPY, final)
    verify_message_copy(src / "chrome/browser/ui/android/strings/android_chrome_strings.grd",
                        {"IDS_MAKE_CHROME_DEFAULT": "Make Brave default"}, final)


def expect_attr(path: Path, key: str, attribute: str, value: str) -> None:
    content = read(path)
    tags = re.findall(r"<[A-Za-z_][A-Za-z0-9_.:-]*\b[^>]*>", content, re.DOTALL)
    matches = [tag for tag in tags if f'android:key="{key}"' in tag]
    if len(matches) != 1:
        raise SystemExit(f"SANDIUM_UI_TEST=FAIL path={path} key={key} matches={len(matches)}")
    match = re.search(re.escape(attribute) + r'="([^"]*)"', matches[0])
    actual = None if match is None else match.group(1)
    if actual != value:
        raise SystemExit(f"SANDIUM_UI_TEST=FAIL path={path} key={key} {attribute}={actual!r} expected={value!r}")

def verify_repository_policy(repo: Path) -> None:
    # Full invokes unconditional shell wrappers; verify their actual commands and
    # stage ordering instead of demanding removed branch-gated inline YAML text.
    from flow_wiring import verify_full_wiring
    try:
        verify_full_wiring(repo)
    except ValueError as exc:
        raise SystemExit(f"SANDIUM_UI_TEST=FAIL Full wiring: {exc}") from exc

    branding = require(repo / ".circleci/scripts/apply-sandium-branding-refresh.py",
        '"Sandium"', 'android:inset="8%"', "sandium_shields_glow")
    if "Sandium Browser" in branding:
        raise SystemExit("SANDIUM_UI_TEST=FAIL app display name must be Sandium only")

    prepare = require(repo / ".circleci/scripts/prepare-brave-source.sh")
    forbidden_gn_overrides = (
        "--gn enable_brave_rewards:false",
        "--gn enable_brave_news:false",
        "--gn enable_brave_vpn_v1:false",
        "--gn enable_brave_vpn_v2:false",
        "--gn enable_brave_wallet:false",
        "--gn enable_ai_chat:false",
    )
    if any(item in prepare for item in forbidden_gn_overrides):
        raise SystemExit("SANDIUM_UI_TEST=FAIL annotated UI removals must not disable vanilla Brave modules")
    full_overlays = require(repo / ".circleci/scripts/apply-sandium-full-overlays.py")
    if "ai_android_build_updated = transform_ai_chat_android_build" in full_overlays:
        raise SystemExit("SANDIUM_UI_TEST=FAIL AI Chat source must remain vanilla Brave")
    ui_overlay = require(repo / ".circleci/scripts/apply-sandium-ui-prune.py")
    if "patch_main_preferences_base(core)" in ui_overlay:
        raise SystemExit("SANDIUM_UI_TEST=FAIL VPN callout must not receive an unrequested source modification")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--src", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args()
    core, src, repo = args.core.resolve(), args.src.resolve(), args.repo_root.resolve()

    menu = require(core / "browser/customize_menu/android/java/src/org/chromium/brave/browser/customize_menu/CustomizeBraveMenu.java",
        "public static boolean isRemovedBySandium", '"brave_wallet_id"', '"brave_leo_id"',
        '"brave_rewards_id"', '"brave_news_id"', '"request_brave_vpn_id"',
        "if (isRemovedBySandium(resources, itemId)) return false;",
        "if (isRemovedBySandium(resources, id)) continue;",
        "MENU_ICON_MAP.put(R.id.default_browser_promo_menu_id, R.drawable.ic_social_brave_release_favicon_fullheight_color);")
    require(core / "android/java/org/chromium/chrome/browser/tabbed_mode/BraveTabbedAppMenuPropertiesDelegate.java",
        "R.string.make_chrome_default,",
        "R.drawable.ic_social_brave_release_favicon_fullheight_color,")

    main_xml = core / "android/java/brave-res/xml/brave_main_preferences.xml"
    for key in ("brave_news_v2", "brave_wallet", "brave_vpn", "brave_leo",
                "brave_sync_layout", "brave_stats"):
        expect_attr(main_xml, key, "app:isPreferenceVisible", "false")
    require(repo / ".circleci/scripts/apply-sandium-full-overlays.py",
        "SANDIUM_ORIGIN_ENTRY_REMOVED")
    if 'android:key="brave_origin"' in main_xml.read_text(encoding="utf-8"):
        raise SystemExit("SANDIUM_UI_TEST=FAIL Origin entry should be removed by full overlays")
    require(core / "android/java/org/chromium/chrome/browser/settings/BraveMainPreferencesBase.java",
        "// SANDIUM_REMOVED_ORIGIN_ORDER_GUARD",
        "&& findPreference(PREF_BRAVE_ORIGIN) != null) {",
        "setPreferenceOrder(PREF_BRAVE_ORIGIN, ++generalOrder);")
    expect_attr(main_xml, "closing_all_tabs_closes_brave", "app:isPreferenceVisible", "true")
    # VPN remains vanilla Brave; the annotated UI policy hides its entry only.

    search_xml = core / "android/java/brave-res/xml/brave_search_engines_preferences.xml"
    expect_attr(search_xml, "search_suggestions", "app:isPreferenceVisible", "false")
    expect_attr(search_xml, "send_web_discovery", "app:isPreferenceVisible", "false")
    require(core / "android/java/org/chromium/chrome/browser/settings/BraveSearchEnginesPreferences.java",
        'indexData.removeEntryForKey(frag, "search_suggestions");',
        'indexData.removeEntryForKey(frag, "send_web_discovery");')
    require(core / "android/java/org/chromium/chrome/browser/settings/BraveSearchEngineUtils.java",
        "SANDIUM_GOOGLE_SEARCH_DEFAULTS_APPLIED", "applySandiumGoogleSearchDefaults(profile, templateUrlService);",
        '"Google".equalsIgnoreCase(templateUrl.getShortName())',
        "setDSEPrefs(googleTemplateUrl, profile);", "setPrivateDSEPrefs(googleTemplateUrl);",
        "BravePreferenceKeys.DEFAULT_SEARCH_ENGINE_CHANGED, true",
        "SharedPreferencesManager preferences = ChromeSharedPreferences.getInstance();")
    adapter = require(src / "chrome/browser/search_engines/android/java/src/org/chromium/chrome/browser/search_engines/settings/SearchEngineAdapter.java",
        "private static boolean isSandiumHiddenBraveEngine(TemplateUrl templateUrl)",
        "prepopulatedUrls.removeIf(SearchEngineAdapter::isSandiumHiddenBraveEngine);",
        "recentlyVisitedUrls.removeIf(SearchEngineAdapter::isSandiumHiddenBraveEngine);",
        "|| !isSandiumHiddenBraveEngine(defaultSearchEngineTemplateUrl)")
    if "if (!mProfile.isOffTheRecord())" in adapter:
        raise SystemExit("SANDIUM_UI_TEST=FAIL Brave search engine filter is not applied to both tabs")
    if adapter.index("prepopulatedUrls.removeIf") > adapter.index("int selectedSearchEnginePosition = -1;"):
        raise SystemExit("SANDIUM_UI_TEST=FAIL Brave filter runs after selected-position calculation")

    privacy_xml = core / "android/java/brave-res/xml/brave_privacy_preferences.xml"
    for key in ("ens", "sns", "send_p3a_analytics", "send_crash_reports",
                "brave_stats_usage_ping", "sponsored_ads_enabled"):
        expect_attr(privacy_xml, key, "app:isPreferenceVisible", "false")
    for key in ("send_crash_reports", "brave_stats_usage_ping", "sponsored_ads_enabled"):
        expect_attr(privacy_xml, key, "android:defaultValue", "false")
    expect_attr(src / "chrome/android/java/res/xml/privacy_preferences.xml",
        "incognito_lock", "app:isPreferenceVisible", "false")
    require(core / "android/java/org/chromium/chrome/browser/privacy/settings/BravePrivacySettings.java",
        'indexData.removeEntryForKey(frag, "incognito_lock");',
        'indexData.removeEntryForKey(frag, "ens");',
        'indexData.removeEntryForKey(frag, "sns");',
        'indexData.removeEntryForKey(frag, "send_p3a_analytics");',
        'indexData.removeEntryForKey(frag, "send_crash_reports");',
        'indexData.removeEntryForKey(frag, "brave_stats_usage_ping");',
        'indexData.removeEntryForKey(frag, "sponsored_ads_enabled");')

    leo = core / "android/java/brave-res/xml/brave_leo_preferences.xml"
    for key in ("autocomplete_switch", "leo_quick_search_engine", "history_switch"):
        expect_attr(leo, key, "android:defaultValue", "false")
    expect_attr(leo, "history_switch", "app:isPreferenceVisible", "true")

    wallet = core / "android/java/brave-res/xml/brave_wallet_preferences.xml"
    for key in ("web3_notifications_switch", "nft_auto_discovery_switch"):
        expect_attr(wallet, key, "android:defaultValue", "false")
    require(core / "android/java/org/chromium/chrome/browser/settings/BraveWalletPreferences.java",
        "readBoolean(PREF_BRAVE_WALLET_WEB3_NOTIFICATIONS, false)")

    verify_ui_identity(core, src)
    duplicate_overlay = core / "android/java/brave-res/values/sandium_ui_overrides.xml"
    if duplicate_overlay.exists():
        raise SystemExit(
            "SANDIUM_UI_TEST=FAIL duplicate sandium_ui_overrides.xml must not be packaged"
        )
    core_build = read(core / "android/BUILD.gn")
    if '"java/brave-res/values/sandium_ui_overrides.xml"' in core_build:
        raise SystemExit(
            "SANDIUM_UI_TEST=FAIL duplicate Sandium default-browser string remains in GN sources"
        )

    verify_repository_policy(repo)

    print("SANDIUM_UI_TEST=PASS menu=removed settings=pruned "
          "standard_search=google private_search=google_brave_removed "
          "privacy=off_then_hidden wallet=none_off leo=off vanilla_wallet_vpn_ai_news_rewards=true "
          "base=850_preserved app_name=Sandium")

if __name__ == "__main__":
    main()
