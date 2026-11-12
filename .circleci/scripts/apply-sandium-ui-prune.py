#!/usr/bin/env python3
"""Apply Sandium's source-preserving UI policy overlay to the pinned Brave tree."""
from __future__ import annotations
import argparse
import re
from pathlib import Path

def read(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"required source file is missing: {path}")
    return path.read_text(encoding="utf-8")

def write(path: Path, content: str, label: str) -> None:
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        print(f"SANDIUM_UI_PATCH={label}:ALREADY_APPLIED")
        return
    path.write_text(content, encoding="utf-8")
    print(f"SANDIUM_UI_PATCH={label}:APPLIED")

def replace_once(path: Path, old: str, new: str, label: str) -> None:
    source = read(path)
    if new in source:
        print(f"SANDIUM_UI_PATCH={label}:ALREADY_APPLIED")
        return
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one source anchor, found {count}: {path}")
    write(path, source.replace(old, new, 1), label)

def insert_before_once(path: Path, anchor: str, addition: str, marker: str, label: str) -> None:
    source = read(path)
    if marker in source:
        print(f"SANDIUM_UI_PATCH={label}:ALREADY_APPLIED")
        return
    count = source.count(anchor)
    if count != 1:
        raise RuntimeError(f"{label}: expected one insertion anchor, found {count}: {path}")
    write(path, source.replace(anchor, addition + anchor, 1), label)

def insert_after_once(path: Path, anchor: str, addition: str, marker: str, label: str) -> None:
    source = read(path)
    if marker in source:
        print(f"SANDIUM_UI_PATCH={label}:ALREADY_APPLIED")
        return
    count = source.count(anchor)
    if count != 1:
        raise RuntimeError(f"{label}: expected one insertion anchor, found {count}: {path}")
    write(path, source.replace(anchor, anchor + addition, 1), label)

def set_xml_attribute(path: Path, key: str, attribute: str, value: str) -> None:
    source = read(path)
    tags = re.compile(r"<[A-Za-z_][A-Za-z0-9_.:-]*\b[^>]*>", re.DOTALL)
    matches = [m for m in tags.finditer(source) if f'android:key="{key}"' in m.group(0)]
    if len(matches) != 1:
        raise RuntimeError(f"xml preference {key}: expected one element, found {len(matches)}: {path}")
    match = matches[0]
    tag = match.group(0)
    attr = re.compile(re.escape(attribute) + r'="[^"]*"')
    replacement = f'{attribute}="{value}"'
    if attr.search(tag):
        updated = attr.sub(replacement, tag, count=1)
    elif tag.endswith("/>"):
        updated = tag[:-2] + " " + replacement + " />"
    else:
        updated = tag[:-1] + " " + replacement + ">"
    if updated != tag:
        write(path, source[:match.start()] + updated + source[match.end():],
              f"xml-{key}-{attribute.replace(':', '-')}")


def set_visible(path: Path, key: str, visible: bool) -> None:
    set_xml_attribute(path, key, "app:isPreferenceVisible", "true" if visible else "false")

def set_default(path: Path, key: str, value: str) -> None:
    set_xml_attribute(path, key, "android:defaultValue", value)

def patch_customize_menu(core: Path) -> None:
    path = core / "browser/customize_menu/android/java/src/org/chromium/brave/browser/customize_menu/CustomizeBraveMenu.java"
    helper = """    public static boolean isRemovedBySandium(final Resources resources, final int itemId) {
        try {
            String resourceName = resources.getResourceEntryName(itemId);
            return "brave_wallet_id".equals(resourceName)
                    || "brave_leo_id".equals(resourceName)
                    || "brave_rewards_id".equals(resourceName)
                    || "brave_news_id".equals(resourceName)
                    || "request_brave_vpn_id".equals(resourceName)
                    || "request_vpn_location_id".equals(resourceName);
        } catch (Resources.NotFoundException ignored) {
            return false;
        }
    }

"""
    insert_before_once(path, "    public static boolean isVisible(final Resources resources, final int itemId) {",
        helper, "public static boolean isRemovedBySandium", "menu-remove-policy-helper")
    replace_once(path,
        """    public static boolean isVisible(final Resources resources, final int itemId) {
        String resourceName;
""",
        """    public static boolean isVisible(final Resources resources, final int itemId) {
        if (isRemovedBySandium(resources, itemId)) return false;
        String resourceName;
""", "menu-remove-policy-visible")
    replace_once(path,
        """            int id = item.model.get(AppMenuItemProperties.MENU_ITEM_ID);
            CharSequence title = item.model.get(AppMenuItemProperties.TITLE);
""",
        """            int id = item.model.get(AppMenuItemProperties.MENU_ITEM_ID);
            if (isRemovedBySandium(resources, id)) continue;
            CharSequence title = item.model.get(AppMenuItemProperties.TITLE);
""", "menu-remove-policy-customize-list")
    replace_once(path,
        "        MENU_ICON_MAP.put(R.id.default_browser_promo_menu_id, R.drawable.ic_set_as_default);\n",
        "        MENU_ICON_MAP.put(R.id.default_browser_promo_menu_id, R.drawable.ic_social_brave_release_favicon_fullheight_color);\n",
        "customize-default-browser-brave-logo")

def patch_default_browser_icon(core: Path) -> None:
    path = core / "android/java/org/chromium/chrome/browser/tabbed_mode/BraveTabbedAppMenuPropertiesDelegate.java"
    replace_once(path,
        """                        R.string.make_chrome_default,
                        0,
                        isMenuIconAtStart()));
""",
        """                        R.string.make_chrome_default,
                        R.drawable.ic_social_brave_release_favicon_fullheight_color,
                        isMenuIconAtStart()));
""", "main-menu-default-browser-brave-logo")

def patch_main_preferences(core: Path) -> None:
    path = core / "android/java/brave-res/xml/brave_main_preferences.xml"
    for key in ("brave_news_v2", "brave_wallet", "brave_vpn", "brave_leo",
                "brave_origin", "brave_sync_layout", "brave_stats"):
        set_visible(path, key, False)
    set_visible(path, "closing_all_tabs_closes_brave", True)

def patch_main_preferences_base(core: Path) -> None:
    path = core / "android/java/org/chromium/chrome/browser/settings/BraveMainPreferencesBase.java"
    insert_before_once(path, "    private void rearrangePreferenceOrders() {",
        "    private static final boolean SANDIUM_SHOW_BRAVE_VPN_CALLOUT = false;\n\n",
        "SANDIUM_SHOW_BRAVE_VPN_CALLOUT", "hide-vpn-settings-callout-flag")
    replace_once(path,
        """        if (getActivity() != null
                && !getActivity().isFinishing()
                && BraveVpnPrefUtils.shouldShowCallout()
""",
        """        if (SANDIUM_SHOW_BRAVE_VPN_CALLOUT
                && getActivity() != null
                && !getActivity().isFinishing()
                && BraveVpnPrefUtils.shouldShowCallout()
""", "hide-vpn-settings-callout")

def patch_search_engine_preferences(core: Path) -> None:
    xml = core / "android/java/brave-res/xml/brave_search_engines_preferences.xml"
    set_visible(xml, "search_suggestions", False)
    set_visible(xml, "send_web_discovery", False)
    java = core / "android/java/org/chromium/chrome/browser/settings/BraveSearchEnginesPreferences.java"
    anchor = "                    String frag = BraveSearchEnginesPreferences.class.getName();\n"
    addition = ('                    indexData.removeEntryForKey(frag, "search_suggestions");\n'
                '                    indexData.removeEntryForKey(frag, "send_web_discovery");\n')
    insert_after_once(java, anchor, addition,
        'indexData.removeEntryForKey(frag, "search_suggestions");', "search-engine-hidden-search-index")

def patch_search_engine_utils(core: Path) -> None:
    path = core / "android/java/org/chromium/chrome/browser/settings/BraveSearchEngineUtils.java"
    constant = ('    private static final String SANDIUM_GOOGLE_SEARCH_DEFAULTS_APPLIED = '
                '"sandium.google_search_defaults_applied_v1";\n\n')
    insert_before_once(path, "    private static void doInitializeBraveSearchEngineStates(",
        constant, "SANDIUM_GOOGLE_SEARCH_DEFAULTS_APPLIED", "google-search-migration-marker")
    helper = """    private static void applySandiumGoogleSearchDefaults(
            Profile profile, TemplateUrlService templateUrlService) {
        if (profile.isOffTheRecord() || templateUrlService.isDefaultSearchManaged()) return;
        ChromeSharedPreferences preferences = ChromeSharedPreferences.getInstance();
        if (preferences.readBoolean(SANDIUM_GOOGLE_SEARCH_DEFAULTS_APPLIED, false)) return;
        TemplateUrl googleTemplateUrl = null;
        for (TemplateUrl templateUrl : templateUrlService.getTemplateUrls()) {
            if (templateUrl.getIsPrepopulated()
                    && "Google".equalsIgnoreCase(templateUrl.getShortName())) {
                googleTemplateUrl = templateUrl;
                break;
            }
        }
        if (googleTemplateUrl == null) return;
        setDSEPrefs(googleTemplateUrl, profile);
        setPrivateDSEPrefs(googleTemplateUrl);
        preferences.writeBoolean(BravePreferenceKeys.DEFAULT_SEARCH_ENGINE_CHANGED, true);
        preferences.writeBoolean(SANDIUM_GOOGLE_SEARCH_DEFAULTS_APPLIED, true);
    }

"""
    insert_before_once(path, "    public static void setDSEPrefs(TemplateUrl templateUrl, Profile profile) {",
        helper, "private static void applySandiumGoogleSearchDefaults(", "google-search-migration-method")
    replace_once(path,
        """        initializeDSEPrefs(profile);
        updateActiveDSE(profile, templateUrlService);
""",
        """        initializeDSEPrefs(profile);
        applySandiumGoogleSearchDefaults(profile, templateUrlService);
        updateActiveDSE(profile, templateUrlService);
""", "google-search-defaults-standard-and-private")

def patch_search_engine_adapter(src: Path) -> None:
    path = src / "chrome/browser/search_engines/android/java/src/org/chromium/chrome/browser/search_engines/settings/SearchEngineAdapter.java"
    helper = """    private static boolean isSandiumHiddenBraveEngine(TemplateUrl templateUrl) {
        return templateUrl.getIsPrepopulated()
                && "Brave".equalsIgnoreCase(templateUrl.getShortName());
    }

"""
    insert_before_once(path, "    private void refreshData() {", helper,
        "private static boolean isSandiumHiddenBraveEngine(", "hide-brave-search-engine-helper")
    insert_before_once(path, "        // Convert the TemplateUrl index into an item index for the view.",
        """        // The annotated X removes Brave from both Standard and Private engine lists.
        prepopulatedUrls = new ArrayList<>(prepopulatedUrls);
        recentlyVisitedUrls = new ArrayList<>(recentlyVisitedUrls);
        prepopulatedUrls.removeIf(SearchEngineAdapter::isSandiumHiddenBraveEngine);
        recentlyVisitedUrls.removeIf(SearchEngineAdapter::isSandiumHiddenBraveEngine);

""",
        "prepopulatedUrls.removeIf(SearchEngineAdapter::isSandiumHiddenBraveEngine)",
        "remove-brave-from-all-search-engine-lists")
    replace_once(path, "        boolean didNotFindDseInLists = selectedSearchEnginePosition == -1;\n",
        """        boolean didNotFindDseInLists =
                selectedSearchEnginePosition == -1
                        && (defaultSearchEngineTemplateUrl == null
                                || !isSandiumHiddenBraveEngine(defaultSearchEngineTemplateUrl));
""", "prevent-hidden-brave-search-engine-fallback")

def patch_privacy_preferences(core: Path, src: Path) -> None:
    brave_xml = core / "android/java/brave-res/xml/brave_privacy_preferences.xml"
    for key in ("ens", "sns", "send_p3a_analytics", "send_crash_reports",
                "brave_stats_usage_ping", "sponsored_ads_enabled"):
        set_visible(brave_xml, key, False)
    for key in ("send_crash_reports", "brave_stats_usage_ping", "sponsored_ads_enabled"):
        set_default(brave_xml, key, "false")
    set_visible(src / "chrome/android/java/res/xml/privacy_preferences.xml", "incognito_lock", False)
    java = core / "android/java/org/chromium/chrome/browser/privacy/settings/BravePrivacySettings.java"
    anchor = "                    String frag = BravePrivacySettings.class.getName();\n"
    addition = (
        '                    indexData.removeEntryForKey(frag, "incognito_lock");\n'
        '                    indexData.removeEntryForKey(frag, "ens");\n'
        '                    indexData.removeEntryForKey(frag, "sns");\n'
        '                    indexData.removeEntryForKey(frag, "send_p3a_analytics");\n'
        '                    indexData.removeEntryForKey(frag, "send_crash_reports");\n'
        '                    indexData.removeEntryForKey(frag, "brave_stats_usage_ping");\n'
        '                    indexData.removeEntryForKey(frag, "sponsored_ads_enabled");\n'
    )
    insert_after_once(java, anchor, addition,
        'indexData.removeEntryForKey(frag, "incognito_lock");', "privacy-hidden-search-index")

def patch_leo_wallet_preferences(core: Path) -> None:
    leo = core / "android/java/brave-res/xml/brave_leo_preferences.xml"
    for key in ("autocomplete_switch", "leo_quick_search_engine", "history_switch"):
        set_default(leo, key, "false")
    set_visible(leo, "history_switch", True)
    wallet = core / "android/java/brave-res/xml/brave_wallet_preferences.xml"
    # Brave reports the native wallet enum as the source of truth; its None state is already index 0.
    set_default(wallet, "web3_notifications_switch", "false")
    set_default(wallet, "nft_auto_discovery_switch", "false")
    replace_once(core / "android/java/org/chromium/chrome/browser/settings/BraveWalletPreferences.java",
        "readBoolean(PREF_BRAVE_WALLET_WEB3_NOTIFICATIONS, true)",
        "readBoolean(PREF_BRAVE_WALLET_WEB3_NOTIFICATIONS, false)",
        "wallet-web3-notifications-default-off")

def patch_make_brave_default_label(core: Path) -> None:
    path = core / "android/java/brave-res/values/sandium_ui_overrides.xml"
    expected = """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="make_chrome_default">Make Brave default</string>
</resources>
"""
    if path.is_file():
        source = read(path)
        if '<string name="make_chrome_default">Make Brave default</string>' in source:
            print("SANDIUM_UI_PATCH=make-brave-default-label:ALREADY_APPLIED")
        elif '<string name="make_chrome_default">' in source:
            source = re.sub(r'<string name="make_chrome_default">.*?</string>',
                '<string name="make_chrome_default">Make Brave default</string>',
                source, count=1, flags=re.DOTALL)
            write(path, source, "make-brave-default-label")
        elif "</resources>" in source:
            write(path, source.replace("</resources>",
                '    <string name="make_chrome_default">Make Brave default</string>\n</resources>', 1),
                "make-brave-default-label")
        else:
            raise RuntimeError(f"invalid resource overlay XML: {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        write(path, expected, "make-brave-default-label")
    insert_after_once(core / "android/BUILD.gn",
        '    "java/brave-res/values/array.xml",\n',
        '    "java/brave-res/values/sandium_ui_overrides.xml",\n',
        '"java/brave-res/values/sandium_ui_overrides.xml"',
        "register-make-brave-default-resource")

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--src", type=Path, required=True)
    args = parser.parse_args()
    core, src = args.core.resolve(), args.src.resolve()
    patch_customize_menu(core)
    patch_default_browser_icon(core)
    patch_main_preferences(core)
    patch_main_preferences_base(core)
    patch_search_engine_preferences(core)
    patch_search_engine_utils(core)
    patch_search_engine_adapter(src)
    patch_privacy_preferences(core, src)
    patch_leo_wallet_preferences(core)
    patch_make_brave_default_label(core)
    print("SANDIUM_UI_POLICY=PASS menu=removed settings=pruned "
          "search=google_standard_google_private_brave_removed privacy=off_and_hidden "
          "wallet=none_off leo=off clean_base_preserved=true")

if __name__ == "__main__":
    main()
