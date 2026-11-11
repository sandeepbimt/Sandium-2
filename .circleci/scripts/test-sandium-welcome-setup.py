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
    'setBackground(roundRect(CARD, 12))',
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
