#!/usr/bin/env python3
"""Self-tests for the pinned Sandium first-run bypass patch."""

import unittest

from apply_sandium_first_run_bypass import (
    MARKER,
    patch_activity_source,
    patch_adapter_source,
)

ACTIVITY_FIXTURE = """class WelcomeOnboardingActivity {
    @Override
    public void triggerLayoutInflation() {
        super.triggerLayoutInflation();
        setContentView(R.layout.activity_welcome_onboarding);
        mOnboardingPager.setAdapter(mStepAdapter);
        playAnimatedVectorDrawable();
        checkReferral();
        onInitialLayoutInflationComplete();
    }

    @Override
    public void finishNativeInitialization() {
        super.finishNativeInitialization();
        playAnimatedVectorDrawable();
    }

    private void playAnimatedVectorDrawable() {}

    private void finalStep() {
        ChromeSharedPreferences.getInstance()
                .writeBoolean(OnboardingPrefManager.SHOULD_SHOW_SEARCH_WIDGET_PROMO, true);
        CustomizeBraveMenu.initDefaultInvisibleItems(getResources());
        OnboardingPrefManager.getInstance().setP3aOnboardingShown(true);
        FirstRunStatus.setFirstRunFlowComplete(true);
        FirstRunUtils.setEulaAccepted();
        launchPendingIntentAndFinish();
    }
}
"""

ADAPTER_FIXTURE = """class OnboardingStepAdapter {
    private static final int[] STEPS = {
        R.layout.help_brave_search, R.layout.block_interruptions, R.layout.make_brave_better
    };
}
"""


class FirstRunBypassTest(unittest.TestCase):
    def test_activity_bypasses_visual_onboarding_but_keeps_completion(self):
        patched = patch_activity_source(ACTIVITY_FIXTURE)
        self.assertEqual(patched.count(MARKER), 3)
        self.assertIn("mOnboardingPager.setVisibility(View.GONE);", patched)
        self.assertIn("mBraveSplash.setVisibility(View.GONE);", patched)
        self.assertIn("checkReferral();", patched)
        self.assertIn("onInitialLayoutInflationComplete();", patched)
        self.assertIn("setMetricsReportingConsent(false, true);", patched)
        self.assertIn("setP3aConsent(false);", patched)
        self.assertIn("finalStep();", patched)
        self.assertIn("FirstRunStatus.setFirstRunFlowComplete(true);", patched)
        self.assertIn("FirstRunUtils.setEulaAccepted();", patched)
        self.assertNotIn("SHOULD_SHOW_SEARCH_WIDGET_PROMO, true", patched)
        self.assertEqual(patch_activity_source(patched), patched)

    def test_adapter_exposes_no_brave_onboarding_steps(self):
        patched = patch_adapter_source(ADAPTER_FIXTURE)
        self.assertIn("private static final int[] STEPS = {};", patched)
        self.assertIn(MARKER, patched)
        self.assertEqual(patch_adapter_source(patched), patched)


if __name__ == "__main__":
    unittest.main(verbosity=2)
