#!/usr/bin/env python3
"""Pin-guarded Fast Mode UI and startup integration for native page-transition blur."""
from pathlib import Path
import subprocess
import sys

BRAVE_SHA = "44a84b1f89d9a35287289d6a3d493e362f5a5123"
CHROMIUM_SHA = "d331de35ca8ab1358c7a17e4bd41627d55eaef51"
FEATURE = "AndroidNavigationBlurTransitionAnimation"
PREF_KEY = "sandium_page_transition_blur_level"
LEVELS = ("default", "low", "medium", "high")

ROOT_TARGET = Path("chrome/android/java/src/org/chromium/chrome/browser/base/SplitCompatApplication.java")
APPEARANCE_XML = Path("android/java/brave-res/xml/brave_appearance_preferences.xml")
APPEARANCE_JAVA = Path("android/java/org/chromium/chrome/browser/settings/AppearancePreferences.java")
STRINGS_GRD = Path("browser/ui/android/strings/android_brave_strings.grd")
APPEARANCE_TEST = Path("android/javatests/org/chromium/chrome/browser/settings/BraveAppearancePreferencesTest.java")

IMPORT = "import org.chromium.base.CommandLine;\n"
IMPORT_ANCHOR = "import org.chromium.base.CommandLineInitUtil;\n"
INIT_ANCHOR = (
    "            CommandLineInitUtil.initCommandLine(\n"
    "                    COMMAND_LINE_FILE, SplitCompatApplication::shouldUseDebugFlags);\n"
)
OUTER_ON_CREATE_ANCHOR = "    @Override\n    public void onCreate() {\n"

RUNTIME_BEGIN = "            // SANDIUM_FAST_BLUR_TRANSITION_BEGIN"
RUNTIME_END = "            // SANDIUM_FAST_BLUR_TRANSITION_END"
RUNTIME_BLOCK = (
    RUNTIME_BEGIN + "\n"
    "            // Read the saved level and apply feature parameters before native FeatureList init.\n"
    "            enableSandiumNavigationBlurTransition();\n"
    + RUNTIME_END + "\n"
)

HELPER_BEGIN = "    // SANDIUM_FAST_BLUR_HELPER_BEGIN"
HELPER_END = "    // SANDIUM_FAST_BLUR_HELPER_END"
HELPER_BLOCK = (
    HELPER_BEGIN + "\n"
    "    private static void enableSandiumNavigationBlurTransition() {\n"
    "        final CommandLine commandLine = CommandLine.getInstance();\n"
    f'        final String feature = "{FEATURE}";\n'
    f'        String level = ContextUtils.getAppSharedPreferences().getString("{PREF_KEY}", "default");\n'
    "        if (!isSandiumBlurLevelValid(level)) {\n"
    '            level = "default";\n'
    "        }\n"
    "\n"
    "        // Respect an explicit command-line opt-out.\n"
    '        final String disabled = commandLine.getSwitchValue("disable-features", "");\n'
    "        if (containsSandiumFeature(disabled, feature)) {\n"
    "            return;\n"
    "        }\n"
    "\n"
    '        String params = "";\n'
    '        if ("low".equals(level)) {\n'
    '            params = "nav-animation-blur-sigma/1.0/nav-animation-fade-hold-duration-ms/200/nav-animation-fade-out-duration-ms/100";\n'
    '        } else if ("medium".equals(level)) {\n'
    '            params = "nav-animation-blur-sigma/2.0/nav-animation-fade-hold-duration-ms/300/nav-animation-fade-out-duration-ms/150";\n'
    '        } else if ("high".equals(level)) {\n'
    '            params = "nav-animation-blur-sigma/4.0/nav-animation-fade-hold-duration-ms/450/nav-animation-fade-out-duration-ms/200";\n'
    "        }\n"
    '        final String selectedFeature = params.isEmpty() ? feature : feature + ":" + params;\n'
    "\n"
    '        final String enabled = commandLine.getSwitchValue("enable-features", "");\n'
    "        final StringBuilder merged = new StringBuilder();\n"
    "        if (!enabled.isEmpty()) {\n"
    "            for (String entry : enabled.split(\",\")) {\n"
    "                final String trimmed = entry.trim();\n"
    "                if (!trimmed.isEmpty() && !feature.equals(getSandiumFeatureName(trimmed))) {\n"
    "                    if (merged.length() > 0) merged.append(',');\n"
    "                    merged.append(trimmed);\n"
    "                }\n"
    "            }\n"
    "        }\n"
    "        if (merged.length() > 0) merged.append(',');\n"
    "        merged.append(selectedFeature);\n"
    '        commandLine.appendSwitchWithValue("enable-features", merged.toString());\n'
    "    }\n"
    "\n"
    "    private static boolean isSandiumBlurLevelValid(String level) {\n"
    '        return "default".equals(level) || "low".equals(level)\n'
    '                || "medium".equals(level) || "high".equals(level);\n'
    "    }\n"
    "\n"
    "    private static boolean containsSandiumFeature(String featureList, String expected) {\n"
    "        if (featureList.isEmpty()) return false;\n"
    "        for (String entry : featureList.split(\",\")) {\n"
    "            if (expected.equals(getSandiumFeatureName(entry.trim()))) return true;\n"
    "        }\n"
    "        return false;\n"
    "    }\n"
    "\n"
    "    private static String getSandiumFeatureName(String entry) {\n"
    "        int modifier = entry.indexOf('<');\n"
    "        int params = entry.indexOf(':');\n"
    "        if (modifier < 0 || (params >= 0 && params < modifier)) modifier = params;\n"
    "        return modifier < 0 ? entry : entry.substring(0, modifier);\n"
    "    }\n"
    + HELPER_END + "\n"
)

XML_BEGIN = "    <!-- SANDIUM_PAGE_TRANSITION_BLUR_BEGIN -->"
XML_END = "    <!-- SANDIUM_PAGE_TRANSITION_BLUR_END -->"
XML_BLOCK = (
    XML_BEGIN + "\n"
    "    <androidx.preference.ListPreference\n"
    f'        android:key="{PREF_KEY}"\n'
    '        android:persistent="false"\n'
    '        android:defaultValue="default"\n'
    '        android:title="@string/sandium_page_transition_blur_title"\n'
    '        android:summary="@string/sandium_page_transition_blur_summary" />\n'
    + XML_END + "\n"
)
XML_ANCHOR = (
    '    <org.chromium.components.browser_ui.settings.ChromeSwitchPreference\n'
    '        android:key="brave_night_mode_enabled_key"\n'
    '        android:icon="@drawable/ic_theme_dark"\n'
    '        android:title="@string/night_mode_enable"\n'
    '        android:summary="@string/night_mode_summary" />\n'
)

JAVA_IMPORT = "import androidx.preference.ListPreference;\n"
JAVA_IMPORT_ANCHOR = "import androidx.preference.PreferenceGroupAdapter;\n"
JAVA_PREF_BEGIN = "    // SANDIUM_PAGE_TRANSITION_BLUR_PREF_BEGIN"
JAVA_PREF_END = "    // SANDIUM_PAGE_TRANSITION_BLUR_PREF_END"
JAVA_PREF_BLOCK = (
    JAVA_PREF_BEGIN + "\n"
    f'    /* package */ static final String PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL = "{PREF_KEY}";\n'
    + JAVA_PREF_END + "\n"
)
JAVA_PREF_ANCHOR = (
    '    /* package */ static final String PREF_BRAVE_NIGHT_MODE_ENABLED =\n'
    '            "brave_night_mode_enabled_key";\n'
)
JAVA_INIT_BEGIN = "        // SANDIUM_PAGE_TRANSITION_BLUR_INIT_BEGIN"
JAVA_INIT_END = "        // SANDIUM_PAGE_TRANSITION_BLUR_INIT_END"
JAVA_INIT_BLOCK = (
    JAVA_INIT_BEGIN + "\n"
    "        ListPreference pageTransitionBlur =\n"
    "                (ListPreference) findPreference(PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL);\n"
    "        if (pageTransitionBlur != null) {\n"
    "            pageTransitionBlur.setEntries(\n"
    "                    new CharSequence[] {\n"
    "                        getString(R.string.sandium_page_transition_blur_default),\n"
    "                        getString(R.string.sandium_page_transition_blur_low),\n"
    "                        getString(R.string.sandium_page_transition_blur_medium),\n"
    "                        getString(R.string.sandium_page_transition_blur_high)\n"
    "                    });\n"
    '            pageTransitionBlur.setEntryValues(new CharSequence[] {"default", "low", "medium", "high"});\n'
    "            pageTransitionBlur.setValue(getSandiumPageTransitionBlurLevel());\n"
    "            pageTransitionBlur.setOnPreferenceChangeListener(this);\n"
    "        }\n"
    + JAVA_INIT_END + "\n"
)
JAVA_INIT_ANCHOR = (
    "        if (nightModeEnabled instanceof ChromeSwitchPreference) {\n"
    "            ((ChromeSwitchPreference) nightModeEnabled)\n"
    "                    .setChecked(ChromeFeatureList.isEnabled(\n"
    "                            BraveFeatureList.FORCE_WEB_CONTENTS_DARK_MODE));\n"
    "        }\n"
)
JAVA_CHANGE_BEGIN = "        // SANDIUM_PAGE_TRANSITION_BLUR_CHANGE_BEGIN"
JAVA_CHANGE_END = "        // SANDIUM_PAGE_TRANSITION_BLUR_CHANGE_END"
JAVA_CHANGE_BLOCK = (
    JAVA_CHANGE_BEGIN + "\n"
    "        if (PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL.equals(key)) {\n"
    "            if (!(newValue instanceof String)\n"
    "                    || !isValidSandiumPageTransitionBlurLevel((String) newValue)) {\n"
    "                return false;\n"
    "            }\n"
    "            boolean saved =\n"
    "                    ContextUtils.getAppSharedPreferences().edit()\n"
    "                            .putString(PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL, (String) newValue)\n"
    "                            .commit();\n"
    "            if (!saved) return false;\n"
    "            shouldRelaunch = true;\n"
    "        } else if (BravePreferenceKeys.BRAVE_BOTTOM_TOOLBAR_ENABLED_KEY.equals(key)) {\n"
    + JAVA_CHANGE_END + "\n"
)
JAVA_CHANGE_ANCHOR = "        if (BravePreferenceKeys.BRAVE_BOTTOM_TOOLBAR_ENABLED_KEY.equals(key)) {\n"
JAVA_HELPER_BEGIN = "    // SANDIUM_PAGE_TRANSITION_BLUR_HELPER_BEGIN"
JAVA_HELPER_END = "    // SANDIUM_PAGE_TRANSITION_BLUR_HELPER_END"
JAVA_HELPER_BLOCK = (
    JAVA_HELPER_BEGIN + "\n"
    "    private static String getSandiumPageTransitionBlurLevel() {\n"
    "        String value = ContextUtils.getAppSharedPreferences()\n"
    "                .getString(PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL, \"default\");\n"
    "        return isValidSandiumPageTransitionBlurLevel(value) ? value : \"default\";\n"
    "    }\n"
    "\n"
    "    private static boolean isValidSandiumPageTransitionBlurLevel(@Nullable String value) {\n"
    '        return "default".equals(value) || "low".equals(value)\n'
    '                || "medium".equals(value) || "high".equals(value);\n'
    "    }\n"
    + JAVA_HELPER_END + "\n"
)
JAVA_HELPER_ANCHOR = "    private static boolean isSharingHubEnabled() {\n"

JAVA_ORDER_BEGIN = "        // SANDIUM_PAGE_TRANSITION_BLUR_ORDER_BEGIN"
JAVA_ORDER_END = "        // SANDIUM_PAGE_TRANSITION_BLUR_ORDER_END"
JAVA_ORDER_BLOCK = (
    JAVA_ORDER_BEGIN + "\n"
    "        setPreferenceOrder(PREF_BRAVE_DISABLE_SHARING_HUB, 11);\n"
    "        setPreferenceOrder(PREF_SHOW_BRAVE_REWARDS_ICON, 12);\n"
    "        setPreferenceOrder(PREF_ADS_SWITCH, 13);\n"
    "        setPreferenceOrder(AppearanceSettingsFragment.PREF_BOOKMARK_BAR, 14);\n"
    "        setPreferenceOrder(PREF_BRAVE_ENABLE_TAB_GROUPS, 15);\n"
    "        setPreferenceOrder(PREF_SHOW_UNDO_WHEN_TABS_CLOSED, 16);\n"
    + JAVA_ORDER_END + "\n"
)
JAVA_ORDER_ANCHOR = (
    "        setPreferenceOrder(PREF_BRAVE_NIGHT_MODE_ENABLED, 9);\n"
    "        setPreferenceOrder(PREF_BRAVE_DISABLE_SHARING_HUB, 10);\n"
    "        setPreferenceOrder(PREF_SHOW_BRAVE_REWARDS_ICON, 11);\n"
    "        setPreferenceOrder(PREF_ADS_SWITCH, 12);\n"
    "        setPreferenceOrder(AppearanceSettingsFragment.PREF_BOOKMARK_BAR, 13);\n"
    "        setPreferenceOrder(PREF_BRAVE_ENABLE_TAB_GROUPS, 14);\n"
    "        setPreferenceOrder(PREF_SHOW_UNDO_WHEN_TABS_CLOSED, 15);\n"
)

GRD_BEGIN = "      <!-- SANDIUM_PAGE_TRANSITION_BLUR_STRINGS_BEGIN -->"
GRD_END = "      <!-- SANDIUM_PAGE_TRANSITION_BLUR_STRINGS_END -->"
GRD_BLOCK = (
    GRD_BEGIN + "\n"
    '      <message name="IDS_SANDIUM_PAGE_TRANSITION_BLUR_TITLE" desc="Title for Sandium page transition blur preference.">\n'
    "        Page transition blur\n"
    "      </message>\n"
    '      <message name="IDS_SANDIUM_PAGE_TRANSITION_BLUR_SUMMARY" desc="Summary for Sandium page transition blur preference.">\n'
    "        Set how strongly the previous page blurs when opening another website\n"
    "      </message>\n"
    '      <message name="IDS_SANDIUM_PAGE_TRANSITION_BLUR_DEFAULT" desc="Default page transition blur level.">\n'
    "        Default\n"
    "      </message>\n"
    '      <message name="IDS_SANDIUM_PAGE_TRANSITION_BLUR_LOW" desc="Low page transition blur level.">\n'
    "        Low\n"
    "      </message>\n"
    '      <message name="IDS_SANDIUM_PAGE_TRANSITION_BLUR_MEDIUM" desc="Medium page transition blur level.">\n'
    "        Medium\n"
    "      </message>\n"
    '      <message name="IDS_SANDIUM_PAGE_TRANSITION_BLUR_HIGH" desc="High page transition blur level.">\n'
    "        High\n"
    "      </message>\n"
    + GRD_END + "\n"
)
GRD_ANCHOR = (
    '      <message name="IDS_NIGHT_MODE_SUMMARY" desc="Summary for Night Mode, which forces web content into dark mode.">\n'
    "        Force dark mode for web content\n"
    "      </message>\n"
)
TEST_IMPORT = "import androidx.preference.ListPreference;\n"
TEST_IMPORT_ANCHOR = "import androidx.preference.Preference;\n"
TEST_CONTEXT_IMPORT = "import org.chromium.base.ContextUtils;\n"
TEST_CONTEXT_IMPORT_ANCHOR = "import org.chromium.base.BravePreferenceKeys;\n"
TEST_ORDER_ANCHOR = "            AppearancePreferences.PREF_BRAVE_NIGHT_MODE_ENABLED,\n"
TEST_ORDER_INSERT = TEST_ORDER_ANCHOR + "            AppearancePreferences.PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL,\n"
TEST_METHOD_BEGIN = "    // SANDIUM_PAGE_TRANSITION_BLUR_TEST_BEGIN"
TEST_METHOD_END = "    // SANDIUM_PAGE_TRANSITION_BLUR_TEST_END"
TEST_METHOD_BLOCK = (
    TEST_METHOD_BEGIN + "\n"
    "    @Test\n"
    "    @SmallTest\n"
    "    public void testPageTransitionBlurHasFourLevelsAndRestoresSavedChoice() {\n"
    "        String key = AppearancePreferences.PREF_SANDIUM_PAGE_TRANSITION_BLUR_LEVEL;\n"
    '        ContextUtils.getAppSharedPreferences().edit().putString(key, "high").commit();\n'
    "        startSettings();\n"
    "        ListPreference preference = (ListPreference) mAppearancePreferences.findPreference(key);\n"
    "        Assert.assertNotNull(preference);\n"
    "        Assert.assertEquals(4, preference.getEntries().length);\n"
    "        Assert.assertEquals(4, preference.getEntryValues().length);\n"
    '        Assert.assertEquals("default", preference.getEntryValues()[0].toString());\n'
    '        Assert.assertEquals("low", preference.getEntryValues()[1].toString());\n'
    '        Assert.assertEquals("medium", preference.getEntryValues()[2].toString());\n'
    '        Assert.assertEquals("high", preference.getEntryValues()[3].toString());\n'
    '        Assert.assertEquals("high", preference.getValue());\n'
    "        ContextUtils.getAppSharedPreferences().edit().remove(key).commit();\n"
    "    }\n"
    + TEST_METHOD_END + "\n"
)
TEST_METHOD_ANCHOR = "    @Test\n    @SmallTest\n    public void testDynamicColorsPreferenceAvailability() {\n"

def replace_marked(source: str, begin: str, end: str, block: str,
                   anchor: str, label: str, *, before: bool = False) -> str:
    bc, ec = source.count(begin), source.count(end)
    if bc or ec:
        if bc != 1 or ec != 1:
            raise RuntimeError(f"{label}: partial or duplicate marker set")
        a, b = source.index(begin), source.index(end) + len(end)
        if b <= a:
            raise RuntimeError(f"{label}: malformed marker order")
        line_a = source.rfind("\n", 0, a) + 1
        line_b = source.find("\n", b)
        line_b = len(source) if line_b < 0 else line_b + 1
        return source[:line_a] + block + source[line_b:]
    if source.count(anchor) != 1:
        raise RuntimeError(f"{label}: expected one exact anchor; found {source.count(anchor)}")
    replacement = block + anchor if before else anchor + block
    return source.replace(anchor, replacement, 1)

def add_import(source: str, import_line: str, anchor: str, label: str) -> str:
    if source.count(import_line) > 1:
        raise RuntimeError(f"{label}: duplicate import")
    if import_line not in source:
        if source.count(anchor) != 1:
            raise RuntimeError(f"{label}: import anchor missing or ambiguous")
        source = source.replace(anchor, anchor + import_line, 1)
    return source

def transform_chromium_startup(source: str) -> str:
    source = add_import(source, IMPORT, IMPORT_ANCHOR, "startup CommandLine import")
    source = replace_marked(source, RUNTIME_BEGIN, RUNTIME_END, RUNTIME_BLOCK,
                            INIT_ANCHOR, "blur activation")
    source = replace_marked(source, HELPER_BEGIN, HELPER_END, HELPER_BLOCK,
                            OUTER_ON_CREATE_ANCHOR, "blur startup helper", before=True)
    checks = [
        (source.count(IMPORT) == 1, "CommandLine import count"),
        (source.count(FEATURE) == 1, "feature identifier count"),
        (source.index(INIT_ANCHOR) < source.index("enableSandiumNavigationBlurTransition();"),
         "activation must follow command-line initialization"),
        (source.index("enableSandiumNavigationBlurTransition();")
         < source.index("PathUtils.setPrivateDataDirectorySuffix"),
         "activation must precede browser preloading"),
        (source.index(HELPER_BEGIN) < source.index(OUTER_ON_CREATE_ANCHOR),
         "helper must be inside the outer application class"),
    ]
    for ok, label in checks:
        if not ok:
            raise RuntimeError(f"startup validation failed: {label}")
    return source

def transform_appearance_xml(source: str) -> str:
    source = replace_marked(source, XML_BEGIN, XML_END, XML_BLOCK,
                            XML_ANCHOR, "Appearance XML preference")
    if source.count(PREF_KEY) != 1 or source.count("androidx.preference.ListPreference") != 1:
        raise RuntimeError("Appearance XML validation failed: preference must appear exactly once")
    return source

def transform_appearance_java(source: str) -> str:
    source = add_import(source, JAVA_IMPORT, JAVA_IMPORT_ANCHOR, "Appearance ListPreference import")
    source = replace_marked(source, JAVA_PREF_BEGIN, JAVA_PREF_END, JAVA_PREF_BLOCK,
                            JAVA_PREF_ANCHOR, "Appearance preference key")
    source = replace_marked(source, JAVA_INIT_BEGIN, JAVA_INIT_END, JAVA_INIT_BLOCK,
                            JAVA_INIT_ANCHOR, "Appearance preference initialization")
    source = replace_marked(source, JAVA_CHANGE_BEGIN, JAVA_CHANGE_END, JAVA_CHANGE_BLOCK,
                            JAVA_CHANGE_ANCHOR, "Appearance preference handler")
    source = replace_marked(source, JAVA_HELPER_BEGIN, JAVA_HELPER_END, JAVA_HELPER_BLOCK,
                            JAVA_HELPER_ANCHOR, "Appearance preference helpers", before=True)
    source = replace_marked(source, JAVA_ORDER_BEGIN, JAVA_ORDER_END, JAVA_ORDER_BLOCK,
                            JAVA_ORDER_ANCHOR, "Appearance preference ordering")
    if source.count(PREF_KEY) != 1:
        raise RuntimeError("Appearance Java validation failed: preference key count")
    if "BraveRelaunchUtils.askForRelaunch(getActivity());" not in source:
        raise RuntimeError("Appearance Java validation failed: relaunch hook missing")
    if source.count("ContextUtils.getAppSharedPreferences()") < 2:
        raise RuntimeError("Appearance Java validation failed: saved preference wiring missing")
    return source

def transform_grd(source: str) -> str:
    source = replace_marked(source, GRD_BEGIN, GRD_END, GRD_BLOCK,
                            GRD_ANCHOR, "Sandium blur strings")
    for name in (
        "IDS_SANDIUM_PAGE_TRANSITION_BLUR_TITLE",
        "IDS_SANDIUM_PAGE_TRANSITION_BLUR_SUMMARY",
        "IDS_SANDIUM_PAGE_TRANSITION_BLUR_DEFAULT",
        "IDS_SANDIUM_PAGE_TRANSITION_BLUR_LOW",
        "IDS_SANDIUM_PAGE_TRANSITION_BLUR_MEDIUM",
        "IDS_SANDIUM_PAGE_TRANSITION_BLUR_HIGH",
    ):
        if source.count(f'name="{name}"') != 1:
            raise RuntimeError(f"GRD validation failed: {name} must occur exactly once")
    return source

def transform_appearance_test(source: str) -> str:
    source = add_import(source, TEST_IMPORT, TEST_IMPORT_ANCHOR, "Appearance test ListPreference import")
    source = add_import(source, TEST_CONTEXT_IMPORT, TEST_CONTEXT_IMPORT_ANCHOR,
                        "Appearance test ContextUtils import")
    if source.count(TEST_ORDER_INSERT) == 0:
        if source.count(TEST_ORDER_ANCHOR) != 1:
            raise RuntimeError("Appearance test ordering anchor missing or ambiguous")
        source = source.replace(TEST_ORDER_ANCHOR, TEST_ORDER_INSERT, 1)
    source = replace_marked(source, TEST_METHOD_BEGIN, TEST_METHOD_END, TEST_METHOD_BLOCK,
                            TEST_METHOD_ANCHOR, "Appearance four-level preference test")
    if source.count("testPageTransitionBlurHasFourLevelsAndRestoresSavedChoice") != 1:
        raise RuntimeError("Appearance instrumentation test was not added uniquely")
    return source

def git_sha(path: Path) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()

def write_transform(path: Path, transform, label: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"{label}: missing file {path}")
    original = path.read_text(encoding="utf-8")
    updated = transform(original)
    if updated != original:
        path.write_text(updated, encoding="utf-8")
        if path.read_text(encoding="utf-8") != updated:
            raise RuntimeError(f"{label}: post-write verification failed")
        print(f"{label}=APPLIED")
    else:
        print(f"{label}=ALREADY_APPLIED")

def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {Path(sys.argv[0]).name} <chromium-src-root>")
    root = Path(sys.argv[1]).resolve()
    core = root / "brave"
    actual_chromium, actual_brave = git_sha(root), git_sha(core)
    if actual_chromium != CHROMIUM_SHA or actual_brave != BRAVE_SHA:
        raise RuntimeError(
            "pinned source mismatch; refusing Fast Mode overlay: "
            f"chromium={actual_chromium} expected={CHROMIUM_SHA}; "
            f"brave={actual_brave} expected={BRAVE_SHA}"
        )

    # Apply the Chromium startup switch first; it reads the saved setting before native startup.
    write_transform(root / ROOT_TARGET, transform_chromium_startup, "SANDIUM_BLUR_STARTUP")
    write_transform(core / APPEARANCE_XML, transform_appearance_xml, "SANDIUM_BLUR_APPEARANCE_XML")
    write_transform(core / APPEARANCE_JAVA, transform_appearance_java, "SANDIUM_BLUR_APPEARANCE_JAVA")
    write_transform(core / STRINGS_GRD, transform_grd, "SANDIUM_BLUR_STRINGS")
    write_transform(core / APPEARANCE_TEST, transform_appearance_test, "SANDIUM_BLUR_APPEARANCE_TEST")
    print("SANDIUM_BLUR_LEVELS=default,low,medium,high")
    print("SANDIUM_BLUR_COMPILE_SCOPE=Java+Android resources; no native C++ or GN changes")
    print("SANDIUM_BLUR_TRANSITION_GATE=PASS")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"SANDIUM_BLUR_TRANSITION_GATE=FAIL {exc}", file=sys.stderr)
        raise SystemExit(1)
