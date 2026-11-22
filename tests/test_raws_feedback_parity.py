"""Ensure the #1483 feedback fixes coexist in the one active overlay."""
import hashlib
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
RECIPE = json.loads((ROOT / "raws-adblock/production-restore-recipe.json").read_text())["files"]
POST = ROOT / "raws-adblock/production-postimages"
ANDROID = "{http://schemas.android.com/apk/res/android}"


class CombinedFeedback(unittest.TestCase):
    def read(self, filename):
        matches = [entry["after_sha256"] for path, entry in RECIPE.items()
                   if path.endswith("/" + filename)]
        self.assertEqual(len(matches), 1, filename)
        data = (POST / matches[0]).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), matches[0])
        return data

    def test_real_home_omnibox_and_real_page_controls_coexist(self):
        toolbar = self.read("ToolbarPhone.java").decode()
        self.assertIn("isRawSBottomNativeHomeOmnibox()", toolbar)
        self.assertIn("mRawSPageActionsActive", toolbar)
        self.assertIn("getRawSUnifiedPaintBounds(", toolbar)
        self.assertIn("tab.canGoForward()", toolbar)
        self.assertIn("centerRawSHomeWallpaper(width, height, mRawSHomeWallpaperCandidate)",
                      self.read("FeedSurfaceCoordinator.java").decode())
        self.assertEqual(hashlib.sha256(self.read("raws_home_wallpaper.webp")).hexdigest(),
                         "c4a3f16fc676e3202b68064dc5e526cec3d2985f513c44ddc202395dca03514f")

    def test_appearance_rows_bind_native_configuration(self):
        prefs = ET.fromstring(self.read("appearance_preferences.xml"))
        rows = {row.get(ANDROID + "key"): row for row in prefs.iter()
                if row.get(ANDROID + "key")}
        wanted = ["raws_parity_transition_blur", "raws_parity_darken_transition"]
        for key in wanted:
            row = rows[key]
            # Programmatic handlers commit through the single startup owner;
            # do not let Preference bootstrap persist a second value.
            self.assertEqual(row.get(ANDROID + "persistent"), "false")
            self.assertNotEqual(row.get(ANDROID + "enabled"), "false")
            self.assertIsNone(row.get(ANDROID + "fragment"))
            self.assertFalse(row.findall("intent"))
        appearance = self.read("AppearanceSettingsFragment.java").decode()
        self.assertIn("RawSNavigationAppearance", appearance)
        self.assertLess(int(rows[wanted[0]].get(ANDROID + "order")),
                        int(rows[wanted[1]].get(ANDROID + "order")))
        main = ET.fromstring(self.read("main_preferences.xml"))
        self.assertFalse(any(row.get(ANDROID + "key") == "raws_ui_sandium_address_bar_color"
                             for row in main.iter()))
        self.assertIn("wallpaperIncludesBrand= */ false", self.read("NewTabPage.java").decode())
        self.assertEqual(hashlib.sha256(self.read("raws_home_brand.png")).hexdigest(),
                         "b4d37afa2feec195ea8e83f1825fd1aa5470d21bb4494f453373c692966fbdb2")


    def test_global_shields_routes_to_native_cookie_settings_and_filter_page(self):
        prefs = ET.fromstring(self.read("raws_protection_preferences.xml"))
        rows = {x.get(ANDROID + "key"): x for x in prefs}
        self.assertTrue(rows["raws_protection_third_party_cookies"].get(
            ANDROID + "fragment").endswith("SingleCategorySettings"))
        self.assertTrue(rows["raws_content_filters"].get(
            ANDROID + "fragment").endswith("RawsProtectionSettings"))
        self.assertFalse({"raws_refresh_filters", "raws_filter_list_details"} & rows.keys())
        java = self.read("RawsProtectionSettings.java").decode()
        self.assertIn("SingleCategorySettings.EXTRA_CATEGORY", java)
        self.assertIn('"third_party_cookies"', java)
        self.assertIn("SHOW_AS_ACTION_NEVER", java)
        self.assertIn("mFilterStatusHandler.removeCallbacks(mFilterStatusPoll)", java)
        self.assertIn("RawsProtectionCopy.setSubscriptionEnabled(", java)
        service = self.read("subscription_service.h").decode()
        self.assertIn('entry.Set("lastDownloadEpochSeconds"', service)
        self.assertIn('entry.Set("cachedBytes"', service)
        self.assertIn('flags_[i].success > 0', service)

    def test_native_dns_off_retains_template_and_policy_guarded_selection(self):
        java = self.read("SecureDnsSettings.java").decode()
        start = java.index("private static boolean storePreferenceState")
        off, rest = java[start:].split("} else if (!controlState.secure)", 1)
        self.assertIn("setMode(SecureDnsMode.OFF)", off)
        self.assertNotIn("setConfig", off)
        self.assertIn("SecureDnsBridge.isConfigManaged()", java)
        self.assertIn("SecureDnsBridge.isModeManaged()", java)
        self.assertIn("QUAD9_TEMPLATE", java)
        self.assertIn("SecureDnsBridge.isValidConfig", java)
        self.assertIn("MAX_PROVIDERS = 12", java)
        self.assertIn("selectInlineProvider(host,", self.read("RawSSetupFirstRunFragment.java").decode())

    def test_deamp_preserves_the_native_request_owner(self):
        client = self.read("chrome_content_browser_client.cc").decode()
        self.assertIn("kRawSGoogleDeAmpPref, true", client)
        self.assertIn("RawSGoogleAmpSwap::DidFinishNavigation", client)
        scoped = client[client.index("GURL RawSGoogleAmpPublisher"):
                        client.index("constexpr char kSandiumPendingPopupKey")]
        self.assertNotIn(".path_piece()", scoped)
        self.assertNotIn(".host_piece()", scoped)
        self.assertIn("OpenURLParams::FromNavigationHandle", scoped)
        self.assertIn("controller.GetPendingEntry()", scoped)
        self.assertIn("GetResponseBody(", scoped)
        self.assertIn("base::Milliseconds(80)", scoped)
        self.assertIn("if (!sandium_popup && handle.IsInPrimaryMainFrame())", client)


    def test_wallpaper_picker_nullable_annotation_targets_nested_type(self):
        coordinator = self.read("FeedSurfaceCoordinator.java").decode()
        self.assertIn(
            "private WindowAndroid.@Nullable IntentCallback mRawSImagePickerCallback;",
            coordinator)
        self.assertNotIn("private @Nullable WindowAndroid.IntentCallback", coordinator)

    def test_unified_toolbar_uses_existing_accessible_java_owners(self):
        model = self.read("LocationBarModel.java").decode()
        toolbar = self.read("ToolbarPhone.java").decode()
        layout = self.read("LocationBarLayout.java").decode()
        phone = self.read("LocationBarPhone.java").decode()
        gate = "org.chromium.chrome.browser.ui.bottombar.BottomBarConfigUtils;"
        self.assertIn("import " + gate, model)
        self.assertIn("import " + gate, toolbar)
        self.assertNotIn("toolbar.bottom.BottomBarConfigUtils", model)
        self.assertIn("instanceof LocationBarLayout layout", toolbar)
        self.assertNotIn("import org.chromium.chrome.browser.omnibox.LocationBarPhone;", toolbar)
        self.assertIn("class LocationBarPhone extends LocationBarLayout", phone)
        self.assertIn("public void setRawSUnifiedRowMode(boolean shared, boolean home) {}", layout)
        self.assertIn("@Override\n    public void setRawSUnifiedRowMode", phone)

    def test_home_pill_keeps_native_search_handoff(self):
        ntp = self.read("NewTabPage.java").decode()
        self.assertIn("mNewTabPageCoordinator.usesRawSHomeSearchLauncher()", ntp)
        self.assertIn("hasRawSNativeHomeOmniboxRoute()", ntp)
        page = self.read("NewTabPageCoordinator.java").decode()
        self.assertIn("mNtpSearchBox.getView()", page)
        self.assertIn("launcher.useRawSHomeSearchLauncher", page)
        self.assertIn("RawSHomeSearch", self.read("SearchBoxViewBinder.java").decode())


if __name__ == "__main__":
    unittest.main()
