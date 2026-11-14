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
    "parent.addView(mBlurRestartHint, matchWrap())",
    "mBlurRestartHint.setPadding(dp(60), dp(10), dp(14), dp(8))",
    "mBlurRestartHint.setVisibility(View.VISIBLE)",
    "blurTitle.setSingleLine(true)",
    "new LinearLayout.LayoutParams(dp(92), dp(40))",
    "if (!preferences.contains(PREF_BLUR_LEVEL)) editor.putString(PREF_BLUR_LEVEL, \"high\")",
    "addRestartSwitchRow(card, \"☾\", \"Night Mode\"",
    "addRestartSwitchRow(card, \"◐\", \"Darken transition\"",
    "mRoot.animate()",
    "AccelerateDecelerateInterpolator",
    "mListener.onPrepareForRestart()",
    "BraveRelaunchUtils::restart",
    'mStartButton.setText("Restarting")',
    "ValueAnimator.ofInt(0, 10000)",
    '"Ad-blocking protection completed"',
    "mTemplateUrlService.setSearchEngine(google.getKeyword())",
    "getOrCreatePrimaryOtrProfile()",
    "TemplateUrlServiceFactory.getForProfile(privateProfile)",
    "privateService.setSearchEngine(privateGoogle.getKeyword())",
    "findGoogleSearchEngine(TemplateUrlService service)",
    "showBlurLevelPicker()",
    "selector.setBackground(outlinedRoundRect(CARD, PRIMARY, 28))",
    "drawable.setStroke(dp(1), strokeColor)",
    "new LinearLayout.LayoutParams(dp(92), dp(40))",
    "parent.addView(mBlurRestartHint, matchWrap())",
    "mBlurRestartHint.setPadding(dp(60), dp(10), dp(14), dp(8))",
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
assert "Unable to read filter status. Retrying..." in view_source
assert "mStartButton.setEnabled(mCanStartBrowsing && !mStartInvoked);" in view_source

# Real apply() over an old generated view must overwrite the obsolete constant,
# and applying again must preserve the new dynamic gate and all existing setup.
with tempfile.TemporaryDirectory() as temp_dir:
    core = Path(temp_dir) / "core"
    src = Path(temp_dir) / "src"
    activity_path = core / PATCHER["ACTIVITY"]
    activity_path.parent.mkdir(parents=True)
    activity_path.write_text(patched)
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
assert "Enabled lists downloaded; native engine reports ready" in view_source
assert "Finalizing: Native engine reports ready" in view_source

# Frozen no-logo layout with approved neutral charcoal theme and green readiness.
assert 'text("Setup Sandium", 27, TEXT, true)' in view_source
assert 'private static final int BACKGROUND = Color.rgb(0, 0, 0);' in view_source
assert 'private static final int CARD = Color.rgb(33, 33, 33);' in view_source
assert 'private static final int SUCCESS = Color.rgb(230, 244, 232);' in view_source
assert 'private static final int PRIMARY = Color.rgb(245, 245, 245);' in view_source
assert 'private static final int PRIMARY_TEXT = Color.rgb(23, 23, 23);' in view_source
assert 'subtitle.setMaxLines(2)' not in view_source
assert 'dp(6), dp(8), dp(6), dp(28)' in view_source
assert 'ImageView' not in view_source
assert 'new LinearLayout.LayoutParams(dp(230), dp(52))' not in view_source
assert 'Color.rgb(110, 127, 192)' not in view_source
print("SANDIUM_WELCOME_FROZEN_DESIGN_TEST=PASS")
assert "Color.rgb(168, 183, 248)" not in view_source
