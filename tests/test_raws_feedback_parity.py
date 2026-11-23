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
        feed = self.read("FeedSurfaceCoordinator.java").decode()
        self.assertIn("if (!mRawSHomeWallpaperIncludesBrand", feed)
        self.assertIn("width, height, wallpaper.getWidth(), wallpaper.getHeight()", feed)
        self.assertIn("mRawSHomeWallpaperIncludesBrand, mRawSHomeWallpaperCandidate", feed)
        self.assertEqual(hashlib.sha256(self.read("raws_home_wallpaper.webp")).hexdigest(),
                         "c4a3f16fc676e3202b68064dc5e526cec3d2985f513c44ddc202395dca03514f")

    def test_home_chrome_paint_never_changes_geometry_or_shortcut_state(self):
        home = self.read("NewTabPage.java").decode()
        tray = home[home.index("// Same alpha as the Google search pill"):]
        tray = tray[:tray.index("coordinator.useRawSHomeWallpaper")]
        self.assertIn("tray.setBackgroundTintList(ColorStateList.valueOf(0xb81c1815))", tray)
        self.assertNotIn("setBackground(", tray)
        self.assertNotIn("setLayoutParams", tray)
        self.assertNotIn("setPadding", tray)
        self.assertIn("0xb827211d", self.read("SearchBoxContainerView.java").decode())
        tile = self.read("SuggestionsTileView.java").decode()
        self.assertIn("return mData.isCustomLink() || mData.isAiMode();", tile)
        self.assertRegex(tile, r'showPinnedShortcutBadge =\s+\(!"io.github.sandeepbimt.raws"')
        feed = self.read("FeedSurfaceCoordinator.java").decode()
        publish = feed.split("private boolean updateRawSHomeWallpaper()", 1)[1]
        publish = publish.split("private boolean updateRawSHomeWallpaperGeometry()", 1)[0]
        self.assertIn("mRawSHomePublishedWallpaperPainting != mRawSHomeWallpaperPainting", publish)
        self.assertIn("invalidate.run()", publish)
        self.assertIn("? 0xff020202 : nativeColor", publish)
        for method in ("requestLayout(", "setLayoutParams(", "setPadding(", "postDelayed("):
            self.assertNotIn(method, publish)

    def test_exit_and_save_are_native_menu_actions(self):
        ids = ET.fromstring(self.read("raws_main_settings_strings.xml"))
        self.assertIsNotNone(ids.find("item[@name='raws_exit_menu_id']"))
        delegate = self.read("TabbedAppMenuPropertiesDelegate.java").decode()
        self.assertLess(delegate.index("R.id.raws_exit_menu_id"),
                        delegate.index("if (NewTabPage.isRawSHomeMenu(mContext, currentTab))"))
        self.assertIn("iconModels.add(buildDownloadActionModel(currentTab))", delegate)
        self.assertIn("if (shouldShowTranslateMenuItem(currentTab))", delegate)
        browser = self.read("ChromeTabbedActivity.java").decode()
        exit_case = browser.split("if (id == R.id.raws_exit_menu_id)", 1)[1]
        exit_case = exit_case.split("final Tab currentTab = getActivityTab()", 1)[0]
        self.assertIn("fromMenu", exit_case)
        self.assertIn("finishAndRemoveTask()", exit_case)
        self.assertNotIn("killProcess", exit_case)
        catalog = self.read("RawSParityMenuCatalog.java").decode()
        self.assertIn('case "raws_exit_menu_id" -> "exit_id";', catalog)
        self.assertIn('case "offline_page_id" -> "download_page_id";', catalog)
        panel = self.read("SandiumPagedMenu.java").decode()
        self.assertIn("if (hasFixedExit()) keys.remove(EXIT)", panel)
        self.assertIn("PAGE_SIZE - 1, EMPTY_SLOT", panel)
        self.assertIn("return pinExit(mSaved.visibleKeys(editableKeys()));", panel)
        self.assertIn("entry.model != captured || !enabled(entry.model)", panel)

    def test_status_bar_uses_existing_surface_owners(self):
        home = self.read("NewTabPage.java").decode()
        change = home.split("private void updateRawSHomeStatusBarColor()", 1)[1]
        change = change.split("public @ColorInt int getRawSHomeStatusBarColor", 1)[0]
        self.assertIn("mActivityTabProvider.get() != mTab", change)
        self.assertIn("mTab.getNativePage() != this", change)
        self.assertIn("getStatusBarColorController().updateStatusBarColor()", change)
        controller = self.read("StatusBarColorController.java").decode()
        self.assertIn("page.getRawSHomeStatusBarColor(mBackgroundColorForNtp)", controller)
        self.assertIn("return rawsOpaqueStatusColor(tab.getBackgroundColor())", controller)
        self.assertNotIn("requestLayout(", controller)
        settings = self.read("SettingsActivity.java").decode()
        self.assertEqual(settings.count("getRawSSettingsTopSurfaceColor()"), 4)
        self.assertIn("helper.setStatusBarColor(getRawSSettingsTopSurfaceColor())", settings)
        self.assertIn("findViewById(R.id.app_bar_layout).setBackgroundColor(backgroundColor)",
                      settings)

    def test_appearance_rows_bind_native_configuration(self):
        prefs = ET.fromstring(self.read("appearance_preferences.xml"))
        rows = {row.get(ANDROID + "key"): row for row in prefs.iter()
                if row.get(ANDROID + "key")}
        wanted = ["raws_parity_transition_blur", "raws_parity_night_mode"]
        self.assertNotIn("raws_parity_darken_transition", rows)
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
        self.assertLess(int(rows[wanted[1]].get(ANDROID + "order")),
                        int(rows[wanted[0]].get(ANDROID + "order")))
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

    def test_deamp_routes_existing_pref_to_script_only_on_fresh_primary_documents(self):
        client = self.read("chrome_content_browser_client.cc").decode()
        self.assertIn("kRawSGoogleDeAmpPref, true", client)
        for owner in ("RawSGoogleAmpSwap", "RawSGoogleAmpNavigationThrottle",
                      "RawSBraveDeAmpBodyHandler", "BodySnifferThrottle"):
            self.assertNotIn(owner, client)
        scoped = client.split("class RawSDisableAmpObserver", 1)[1].split(
            "constexpr char kSandiumPendingPopupKey", 1)[0]
        self.assertIn("RawSDisableAmpObserver::DOMContentLoaded", scoped)
        self.assertIn("frame != web_contents()->GetPrimaryMainFrame()", scoped)
        self.assertIn("kRawSGoogleDeAmpPref", scoped)
        # BrowserContext::ShutdownStarted() is not const in M158.
        self.assertIn("auto* profile = Profile::FromBrowserContext(frame->GetBrowserContext());", scoped)
        self.assertNotIn("const auto* profile", scoped)
        self.assertIn("profile->ShutdownStarted()", scoped)
        self.assertNotIn("PrefChangeRegistrar", scoped)
        self.assertNotIn("OpenURL(", scoped)
        self.assertLess(scoped.index("if (mode == AmpMode::kOff)"),
                        scoped.index("endpoint->SetRawSDisableAmp("))
        renderer = self.read("chrome_render_frame_observer.cc").decode()
        scoped = renderer.split("void ChromeRenderFrameObserver::SetRawSDisableAmp(", 1)[1]
        scoped = scoped.split("void ChromeRenderFrameObserver::SetRawSProceduralCosmetic(", 1)[0]
        self.assertIn("frame->GetEmbeddingToken() != token", scoped)
        self.assertIn("GURL(doc.Url()) != expected_url", scoped)
        self.assertIn("ISOLATED_WORLD_ID_RAWS_DISABLE_AMP", scoped)
        self.assertNotIn("ISOLATED_WORLD_ID_CHROME_INTERNAL", scoped)


    def test_popup_marker_uses_native_mutable_handle_before_consumption(self):
        client = self.read("chrome_content_browser_client.cc").decode()
        popup = client.split("class SandiumPopupNavigationThrottle final", 1)[1]
        popup = popup.split("  SandiumPopupNavigationThrottle(", 1)[0]
        self.assertIn("auto& handle = registry.GetNavigationHandle();", popup)
        marker = popup.index("contents->GetUserData(kSandiumPendingPopupKey)")
        create = popup.index("registry.AddThrottle(std::make_unique<SandiumPopupNavigationThrottle>")
        consume = popup.index("contents->RemoveUserData(kSandiumPendingPopupKey)")
        self.assertLess(marker, create)
        self.assertLess(create, consume)
        registry = client.split("void ChromeContentBrowserClient::CreateThrottlesForNavigation(", 1)[1]
        registry = registry.split("void ChromeContentBrowserClient::CreateThrottlesForCommitWithoutUrlLoader(", 1)[0]
        self.assertEqual(1, registry.count("SandiumPopupNavigationThrottle::MaybeCreateAndAdd(registry)"))


    def test_procedural_cosmetic_binding_closes_the_native_quoted_nonce(self):
        binding = self.read("raws_procedural_cosmetic_binding.h").decode()
        observer = self.read("chrome_render_frame_observer.cc").decode()
        # StrCat opens the final JavaScript string argument before the nonce.
        # The header must escape the C++ quote so emitted JS can close it.
        self.assertIn(r'kRawSProcedureCallAfter[] = "\");";', binding)
        self.assertIn(r'cosmetic::kAmazonRuleConfig, ",\"", nonce,', observer)
        self.assertIn("cosmetic::kRawSProcedureCallAfter});", observer)

    def test_element_color_observer_uses_pinned_blink_ascii_constructor(self):
        cpp = self.read("sandium_element_colors.cc").decode()
        # M158's WTF String exposes FromUtf8, not FromUTF8. These are literal
        # ASCII HTML attribute names, so the direct String constructor avoids
        # the byte-span conversion and preserves the observer's exact filter.
        self.assertIn(
            '#include "third_party/blink/renderer/platform/wtf/text/wtf_string.h"', cpp)
        self.assertIn(
            'Vector<String>{String("id"), String("class"), String("role")}', cpp)
        self.assertNotIn("String::FromUTF8", cpp)

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
