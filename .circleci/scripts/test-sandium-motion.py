#!/usr/bin/env python3
"""Pinned transformation/scope contracts; not Android runtime validation."""
import importlib.util
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('theme', Path(__file__).with_name('apply-sandium-native-theme.py'))
theme = importlib.util.module_from_spec(spec); spec.loader.exec_module(theme)
class MotionTests(unittest.TestCase):
    def test_settings_pinned_idempotent(self):
        original = (ROOT / '.circleci/tests/fixtures/motion/BraveSettingsActivity.java').read_text()
        result = theme.settings_motion(original)
        self.assertEqual(result, theme.settings_motion(result))
        self.assertIn('fragment.getParentFragment() == null', result)
        self.assertIn('fragment.getView() == view && view.isAttachedToWindow()', result)
        self.assertIn('ValueAnimator.areAnimatorsEnabled()', result)
        self.assertIn('.setDuration(120).setStartDelay(0)', result)
        self.assertIn('view.setAlpha(1f);', result)
    def test_settings_drift_fails(self):
        with self.assertRaises(ValueError): theme.settings_motion('drift')
    def test_menu_updates_do_not_fade(self):
        text = (ROOT / 'android/java/org/chromium/chrome/browser/ui/appmenu/SandiumPagedMenu.java').read_text()
        self.assertIn('screen != mRenderedScreen || mNativeVisible', text)
        self.assertIn('if (transition) startPanelMotion();', text)
        self.assertIn('mDragging != null || !isAttachedToWindow()', text)
        self.assertIn('panel.setAlpha(mPanelAlpha);', text)
        self.assertIn('mMotionPanel.setAlpha(mPanelAlpha);', text)
        render = text.split('    private void render() {', 1)[1].split('    private void grid(', 1)[0]
        self.assertNotIn('animate().cancel()', render)
        self.assertNotIn('            setAlpha(0f)', render)
        self.assertNotIn('finishPanelMotion();', render)
        self.assertIn('android.animation.ValueAnimator.areAnimatorsEnabled()', text)
    def test_page_slide_lifecycle_and_edit_swipes(self):
        text = (ROOT / 'android/java/org/chromium/chrome/browser/ui/appmenu/SandiumPagedMenu.java').read_text()
        self.assertIn('mPageAnimator.setDuration(180)', text)
        self.assertIn('generation != mPageMotionGeneration || viewport != mPageViewport', text)
        self.assertIn('disableTree(oldPage)', text)
        self.assertIn('IMPORTANT_FOR_ACCESSIBILITY_NO_HIDE_DESCENDANTS', text)
        self.assertIn('finishPanelMotion(); finishPageMotion();', text)
        self.assertIn('mNativeVisible || mDragging != null', text)
        self.assertIn('mSwipeEligible && Math.abs', text)
        self.assertIn('new LinearLayout.LayoutParams(dp(28), dp(32))', text)
        self.assertIn('pager.setContentDescription(s(R.string.sandium_menu_page_description', text)
        self.assertNotIn('button("‹", s(R.string.sandium_menu_previous)', text)
        self.assertNotIn('button("›", s(R.string.sandium_menu_next)', text)
        self.assertIn('if (next == mPage) return;', text)
        self.assertIn('viewport.setMinimumHeight(((PAGE_SIZE + columns() - 1) / columns()) * tileHeight())', text)
        self.assertNotIn('mPageMinimumHeight', text)
    def test_popup_retains_native_lifecycle_and_low_end_guard(self):
        text = Path(__file__).with_name('apply-sandium-paged-menu.py').read_text()
        self.assertIn('popup.setAnimationStyle(0);', text)
        self.assertIn('popup.setEnterTransition(null);', text)
        self.assertIn('popup.setExitTransition(SysUtils.isLowEndDevice() || !ValueAnimator.areAnimatorsEnabled()', text)
        self.assertIn('new android.transition.Fade(android.transition.Fade.OUT).setDuration(80)', text)
        view = (ROOT / 'android/java/org/chromium/chrome/browser/ui/appmenu/SandiumPagedMenu.java').read_text()
        self.assertIn('onAttachedToWindow()', view)
        self.assertIn('org.chromium.base.SysUtils.isLowEndDevice()', view)
        self.assertIn('!android.animation.ValueAnimator.areAnimatorsEnabled()', view)
        self.assertIn('mEntranceAnimator.setDuration(100)', view)
        self.assertIn('if (mEntranceAnimator == animation)', view)
        self.assertIn('onDetachedFromWindow() {\n        finishEntranceMotion();', view)
    def test_welcome_reduced_motion_and_destroy(self):
        text = (ROOT / 'android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java').read_text()
        self.assertIn('if (!ValueAnimator.areAnimatorsEnabled()) return;', text)
        self.assertIn('if (!mDestroyed && view.isAttachedToWindow()', text)
        self.assertIn('if (mExpanded) fadeIn(mAdvancedOptions);', text)
        self.assertIn('fadeIn(mContent);', text)
        self.assertNotIn('fadeIn(mRoot);', text)
if __name__ == '__main__': unittest.main()
