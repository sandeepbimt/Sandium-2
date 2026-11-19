#!/usr/bin/env python3
"""Offline regression checks for the Sandium first-run UI patcher."""
import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent
PATCHER = runpy.run_path(str(HERE / "apply-sandium-welcome-setup.py"))

activity = Path("android/java/org/chromium/chrome/browser/firstrun/WelcomeOnboardingActivity.java")
source = """    private boolean mSplashAnimationFinished;

    @Override
    public void triggerLayoutInflation() {
        super.triggerLayoutInflation();
        setContentView(R.layout.activity_welcome_onboarding);
    }

    @Override
    public void finishNativeInitialization() {
        super.finishNativeInitialization();
        mStepAdapter.setP3aChecked(true);
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        outState.putInt(KEY_PAGE_INDEX, mOnboardingPager.getCurrentItem());
    }

    @Override
    protected void onRestoreInstanceState(Bundle state) {
        super.onRestoreInstanceState(state);
    }

    private void finalStep() {
        ChromeSharedPreferences.getInstance()
                .writeBoolean(OnboardingPrefManager.SHOULD_SHOW_SEARCH_WIDGET_PROMO, true);
        CustomizeBraveMenu.initDefaultInvisibleItems(getResources());
        OnboardingPrefManager.getInstance().setP3aOnboardingShown(true);
        FirstRunStatus.setFirstRunFlowComplete(true);
        FirstRunUtils.setEulaAccepted();
        launchPendingIntentAndFinish();
    }

    @Override
    public @BackPressResult int handleBackPress() {
        return BackPressResult.SUCCESS;
    }
"""
patched = PATCHER["transform_activity"](source)
assert "new SandiumWelcomeSetupView.Listener()" in patched
assert "this::finalStep" not in patched
assert "prepareForSandiumRestart()" in patched
assert "onPrepareForRestart()" in patched
assert "assumeNonNull(mSandiumSetupView).initialize(profile)" in patched
assert "mSandiumSetupView.destroy()" in patched
assert "SHOULD_SHOW_SEARCH_WIDGET_PROMO, true" not in patched
assert "FirstRunStatus.setFirstRunFlowComplete(true)" in patched
assert "FirstRunUtils.setEulaAccepted()" in patched
assert "mOnboardingPager.getCurrentItem()" not in patched
assert PATCHER["transform_activity"](patched) == patched

restart_source = """            context.startActivity(restartIntent);
        }

        // Kill this process.
"""
restart_patched = PATCHER["transform_restart_activity"](restart_source)
assert "overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);" in restart_patched
assert PATCHER["transform_restart_activity"](restart_patched) == restart_patched

# The pinned Brave checkout does not contain this Sandium-owned Java file yet.
# Verify write() creates both a missing file and its parent directories.
import tempfile

with tempfile.TemporaryDirectory() as temp_dir:
    destination = Path(temp_dir) / "brave" / "android" / "SandiumWelcomeSetupView.java"
    expected = "class SandiumWelcomeSetupView {}\n"
    PATCHER["write"](destination, expected, "welcome-setup-view-test")
    assert destination.is_file()
    assert destination.read_text(encoding="utf-8") == expected
    PATCHER["write"](destination, expected, "welcome-setup-view-idempotence-test")
    assert destination.read_text(encoding="utf-8") == expected

# Verify the real welcome view's restart, expansion, blur and search behavior.
repo_root = HERE.parent.parent
view_source = (repo_root / "android/java/org/chromium/chrome/browser/firstrun/"
               "SandiumWelcomeSetupView.java").read_text(encoding="utf-8")
required_view_markers = (
    "mScrollView.setFillViewport(true)",
    '"↻  Needs a quick restart to apply"',
    "mBlurRestartHint.setVisibility(View.VISIBLE)",
    "row.setPadding(dp(16), dp(12), dp(14), dp(2))",
    "selector.setBackground(outlinedRoundRect(CARD, PRIMARY, 28))",
    "group.addView(mBlurRestartHint, matchWrap())",
    "mBlurRestartHint.setPadding(dp(60), 0, dp(14), dp(4))",
    "mBlurRestartHint.setVisibility(View.VISIBLE)",
    "blurTitle.setSingleLine(true)",
    "new LinearLayout.LayoutParams(dp(92), dp(40))",
    "if (!preferences.contains(PREF_NATIVE_BLUR))",
    "addRestartSwitchRow(card, \"☾\", \"Night Mode\"",
    "addRestartSwitchRow(card, \"◐\", \"Darken transition\"",
    "mListener.onPrepareForRestart()",
    "BraveRelaunchUtils.restart()",
    'R.string.sandium_welcome_restarting_countdown',
    'mActivity.getString(R.string.sandium_welcome_protection_complete)',
    "mTemplateUrlService.setSearchEngine(google.getKeyword())",
    "getOrCreatePrimaryOtrProfile()",
    "TemplateUrlServiceFactory.getForProfile(privateProfile)",
    "privateService.setSearchEngine(privateGoogle.getKeyword())",
    "findGoogleSearchEngine(TemplateUrlService service)",
    "showBlurLevelPicker()",
    "selector.setBackground(outlinedRoundRect(CARD, PRIMARY, 28))",
    "drawable.setStroke(dp(1), strokeColor)",
    "new LinearLayout.LayoutParams(dp(92), dp(40))",
    "group.addView(mBlurRestartHint, matchWrap())",
    "mBlurRestartHint.setPadding(dp(60), 0, dp(14), dp(4))",
)
missing_view_markers = [marker for marker in required_view_markers if marker not in view_source]
assert not missing_view_markers, "welcome view missing: " + ", ".join(missing_view_markers)
assert "TemplateUrlServiceFactory.getForProfile(regularProfile)" in view_source
assert "mGoogleSearchSwitch" not in view_source
assert "addSearchEngineRow" not in view_source
assert "showSearchEnginePickerDialog" not in view_source
assert "setGoogleAsDefaultSearchEngine" not in view_source
assert "Use Google as default search engine" not in view_source
assert 'findGoogleSearchEngine(mTemplateUrlService)' in view_source
assert 'privateService.runWhenLoaded(() -> {' in view_source
assert 'privateService.runWhenLoaded(() -> {' in view_source

print("SANDIUM_WELCOME_SETUP_PATCHER_TEST=PASS")

# Execute the boolean expression extracted from production Java (not a second
# hardcoded count gate). This is logic coverage, not an Android/JVM execution.
import re
expression = re.search(
    r"static boolean allEnabledFiltersDownloaded\(int downloaded, int total\) \{\s*return ([^;]+);",
    view_source).group(1)
assert expression == "total > 0 && downloaded == total"
def downloaded_ready(downloaded, total):
    return eval(expression.replace("&&", "and"), {"__builtins__": {}},
                {"downloaded": downloaded, "total": total})
assert "return ready && allEnabledFiltersDownloaded(downloaded, total);" in view_source
for ready, downloaded, total, expected in [
    (True, 30, 30, True),
    (False, 30, 30, False),
    (True, 29, 30, False),
    (True, 0, 0, False),
    (False, 0, 0, False),
    (True, 29, 29, True),  # One intentionally disabled list.
    (True, 31, 31, True),  # Additional manual subscription.
    (True, 28, 29, False), # Enabled list has no successful download.
    (True, 31, 30, False),
]:
    assert (ready and downloaded_ready(downloaded, total)) == expected
assert "REQUIRED_FILTER_COUNT" not in view_source
assert "29 filters" not in view_source
assert "if (!item.enabled) continue;" in view_source
assert "if (successful > 0) downloaded++;" in view_source
assert "subscriptions == null" in view_source
assert 'mActivity.getString(R.string.sandium_welcome_status_retry)' in view_source
assert "mStartButton.setEnabled(mCanStartBrowsing && !mStartInvoked);" in view_source

# Real apply() over an old generated view must overwrite the obsolete constant,
# and applying again must preserve the new dynamic gate and all existing setup.
with tempfile.TemporaryDirectory() as temp_dir:
    core = Path(temp_dir) / "core"
    src = Path(temp_dir) / "src"
    activity_path = core / PATCHER["ACTIVITY"]
    activity_path.parent.mkdir(parents=True)
    activity_path.write_text(patched)
    (core / "android/BUILD.gn").write_text('    "java/brave-res/values/brave_ids.xml",\n')
    source_list = core / PATCHER["JAVA_SOURCES"]
    source_list.parent.mkdir(parents=True, exist_ok=True)
    source_list.write_text('  "../../brave/android/java/org/chromium/chrome/browser/firstrun/WelcomeOnboardingActivity.java",\n')
    restart_path = src / PATCHER["RESTART_ACTIVITY"]
    restart_path.parent.mkdir(parents=True)
    restart_path.write_text(restart_patched)
    view_path = core / PATCHER["VIEW"]
    view_path.write_text("class SandiumWelcomeSetupView {\n"
                         "private static final int REQUIRED_FILTER_COUNT = 29;\n}\n")
    PATCHER["apply"].__globals__["verify_pins"] = lambda core, src: None
    PATCHER["apply"](core, src, repo_root)
    first = view_path.read_text()
    PATCHER["apply"](core, src, repo_root)
    assert view_path.read_text() == first == view_source
    assert "REQUIRED_FILTER_COUNT" not in first
print("SANDIUM_WELCOME_DYNAMIC_COUNT_TEST=PASS count_cases=9 native_ready_required=true old_view_replaced=true")

# Readiness is the native activation signal, not a promise that every imported
# rule or resource was accepted and executed on every site.
assert "All filter rules applied" not in view_source
assert "loaded and active" not in view_source
assert "R.string.sandium_welcome_downloads_ready" in view_source
assert "R.string.sandium_welcome_final_complete" in view_source

# Profile-card header with Oppo theme and unchanged green readiness signal.
assert 'text("Sandium", 24, TEXT, true)' in view_source
assert 'private static final int BACKGROUND = Color.rgb(0, 0, 0);' in view_source
assert 'private static final int CARD = Color.rgb(26, 26, 26);' in view_source
assert 'private static final int SUCCESS = Color.rgb(70, 200, 120);' in view_source
assert 'private static final int PRIMARY = Color.rgb(25, 140, 255);' in view_source
assert 'private static final int PRIMARY_TEXT = Color.rgb(8, 15, 24);' in view_source
assert 'subtitle.setMaxLines(2)' not in view_source
assert 'params.bottomMargin = dp(8);' in view_source
assert 'logo.setImageDrawable(mLogoTracer);' in view_source
assert 'logo.setScaleType(ImageView.ScaleType.FIT_CENTER);' in view_source
assert 'logo.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);' in view_source
assert 'title.setAccessibilityHeading(true);' in view_source
assert 'Choose your browsing preferences.' in view_source
assert 'logo.setImageTintList' not in view_source
assert 'logo.setColorFilter' not in view_source
assert 'new LinearLayout.LayoutParams(dp(230), dp(52))' not in view_source
assert 'Color.rgb(110, 127, 192)' not in view_source
print("SANDIUM_WELCOME_FROZEN_DESIGN_TEST=PASS")
assert "Color.rgb(168, 183, 248)" not in view_source

# Oppo-reference category icons are decorative, independent from toggle state.
assert 'ICON_GREEN = Color.rgb(2, 190, 18)' in view_source
assert 'ICON_AMBER = Color.rgb(253, 178, 0)' in view_source
assert 'ICON_ORANGE = Color.rgb(255, 119, 1)' in view_source
assert 'text(glyph, 23, welcomeIconColor(glyph), false)' in view_source
assert 'params.setMarginStart(dp(56));' in view_source
assert 'params.setMarginEnd(dp(14));' in view_source
assert 'if (i > 0) addDivider(container);' in view_source  # Picker dividers unchanged.
print("SANDIUM_WELCOME_OPPO_CATEGORY_STYLE=PASS")

# All direct status text is resource-backed without changing runtime behavior.
import json
import xml.etree.ElementTree as ET
resource = Path("android/java/brave-res/values/sandium_welcome_strings.xml")
strings = {el.attrib["name"]: el.text for el in ET.parse(HERE.parent.parent / resource).getroot()}
assert strings["sandium_welcome_start"] == '"Start browsing"'
assert strings["sandium_welcome_restarting_countdown"] == 'Restarting in %1$d…'
assert set(re.findall(r"R.string.(sandium_welcome_\w+)", view_source)) == set(strings)
assert all('"' not in expr for expr in re.findall(r"\.setText\((.*?)\);", view_source, re.S))
assert "Gravity.RIGHT" not in view_source and "Gravity.LEFT" not in view_source
assert 'SuppressLint("SetTextI18n")' not in view_source
assert "Restarting in 5" not in view_source
recipe = json.loads((HERE.parent / "features/removal-recipe.json").read_text())
assert "brave/" + str(resource) in recipe["generated_overwrite"]
print("SANDIUM_WELCOME_LINT_RESOURCE_TEST=PASS")
