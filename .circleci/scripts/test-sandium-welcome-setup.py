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
assert "new SandiumWelcomeSetupView(this, this::finalStep)" in patched
assert "mSandiumSetupView.initialize(profile)" in patched
assert "mSandiumSetupView.destroy()" in patched
assert "SHOULD_SHOW_SEARCH_WIDGET_PROMO, true" not in patched
assert "FirstRunStatus.setFirstRunFlowComplete(true)" in patched
assert "FirstRunUtils.setEulaAccepted()" in patched
assert "mOnboardingPager.getCurrentItem()" not in patched
assert PATCHER["transform_activity"](patched) == patched
print("SANDIUM_WELCOME_SETUP_PATCHER_TEST=PASS")
