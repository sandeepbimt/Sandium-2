"""Source guards for delayed feedback lifecycle; dispatch has an executable harness."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
class PreparingLifecycle(unittest.TestCase):
    def test_dots_stop_when_ready_or_detached(self):
        s=(ROOT/'android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java').read_text()
        dots=s.split('private void updatePreparingDots()',1)[1].split('private void updateStartCountdown()',1)[0]
        for marker in ('mDestroyed || mCanStartBrowsing || mStartInvoked', '!mStartButton.isAttachedToWindow()', 'mHandler.removeCallbacks(mDotsRunnable)', 'if (ValueAnimator.areAnimatorsEnabled()) mHandler.postDelayed(mDotsRunnable, 300)'):
            self.assertIn(marker,dots)
        self.assertIn('new SpannableString(',dots)
        self.assertIn('i * 2, i * 2 + 1',dots)
        detach=s.split('public void onViewDetachedFromWindow(View view)',1)[1].split('});',1)[0]
        self.assertIn('cancelButtonFeedback()',detach)
        cleanup=s.split('private void cancelButtonFeedback()',1)[1].split('private void updateStartButtonState()',1)[0]
        for field in ('mDotsRunnable','mCountdownRunnable','mRestartRunnable'):
            self.assertIn('removeCallbacks('+field+')',cleanup)
        self.assertIn('mRestartAnimator.cancel()',cleanup)
    def test_countdown_is_fixed_clock_not_animation_dispatch(self):
        s=(ROOT/'android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java').read_text()
        self.assertIn('START_FEEDBACK_MS = 1500L',s)
        self.assertIn('elapsed / 300',s)
        self.assertIn('mPendingRestart = mRequiresRestart',s)
        self.assertIn('mCompletionDispatched = true',s)
        self.assertNotIn('onAnimationEnd(',s)
    def test_notification_setup_is_durable_before_dispatch(self):
        s=(ROOT/'android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java').read_text()
        method=s.split('private boolean persistNotificationSetup()',1)[1].split('private String readyButtonLabel()',1)[0]
        for marker in ('getSharedPreferences("sandium_notifications"', 'putBoolean("setup_completed", true)', 'mNotificationsEnabled && !prefs.getBoolean("request_attempted", false)', '.commit()'):
            self.assertIn(marker,method)
        self.assertNotIn('putBoolean("request_attempted"',method)
        perform=s.split('private void performRestart()',1)[1].split('private boolean persistNotificationSetup()',1)[0]
        self.assertLess(perform.index('persistNotificationSetup()'),perform.index('mCompletionDispatched = true'))
        self.assertIn('.getBoolean("enabled", true)',s)
        self.assertNotIn('requestPermissions(',s)
