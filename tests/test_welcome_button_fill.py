"""Source/composition guards for the in-capsule restart countdown."""
from pathlib import Path
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[1]
VIEW = ROOT / 'android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java'


class WelcomeButtonFill(unittest.TestCase):
    def test_fill_reuses_capsule_without_separate_progress_row(self):
        source = VIEW.read_text()
        self.assertNotIn('mRestartProgress', source)
        self.assertIn('private ClipDrawable mRestartButtonFill;', source)
        self.assertIn('roundRect(START_PROGRESS, 28), Gravity.LEFT, ClipDrawable.HORIZONTAL', source)
        self.assertIn('roundRect(START_TRACK, 28), mRestartButtonFill', source)
        self.assertIn('mStartButton.setBackgroundTintList(null)', source)
        self.assertIn('ViewGroup.LayoutParams.MATCH_PARENT, dp(52)', source)
        self.assertIn('mStartButton.setText("Restarting in a moment…")', source)
        self.assertIn('mRestartButtonFill.setLevel(0)', source)
        self.assertIn('ValueAnimator.ofInt(0, 10000)', source)
        self.assertIn('mRestartButtonFill.setLevel(10000)', source)
        # Setup download progress is independent and remains visible as before.
        self.assertIn('mProgress.setProgress(percent)', source)

    def test_reference_green_and_text_progress_contrast(self):
        import re
        source = VIEW.read_text()
        def color(name):
            match = re.search(r"int " + name + r" = Color.rgb\((\d+), (\d+), (\d+)\)", source)
            return tuple(map(int, match.groups()))
        def luminance(rgb):
            values = [v / 255 for v in rgb]
            linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
            return sum(v * weight for v, weight in zip(linear, (.2126, .7152, .0722)))
        def contrast(a, b):
            high, low = sorted((luminance(a), luminance(b)), reverse=True)
            return (high + .05) / (low + .05)
        self.assertEqual(color('START_BUTTON'), (36, 169, 50))
        self.assertGreaterEqual(contrast(color('START_PROGRESS'), color('START_TRACK')), 3)
        self.assertGreaterEqual(contrast(color('PRIMARY_TEXT'), color('START_BUTTON')), 4.5)
        for background in ('START_TRACK', 'START_PROGRESS'):
            self.assertGreaterEqual(contrast(color('TEXT'), color(background)), 4.5)
        self.assertIn('mStartButton.setTextColor(TEXT)', source)
        self.assertIn('mCanStartBrowsing ? START_BUTTON : DISABLED_BUTTON, 28', source)
        self.assertIn('mCanStartBrowsing ? PRIMARY_TEXT : DISABLED_BUTTON_TEXT', source)
        # Do not recolor unrelated controls.
        self.assertEqual(color('PRIMARY'), (25, 140, 255))

    def test_dark_page_owner_preserves_fill_and_restart_dispatch(self):
        patch = runpy.run_path(str(ROOT / '.circleci/scripts/apply-sandium-dark-pages.py'))['welcome']
        source = patch(VIEW.read_text())
        self.assertEqual(source, patch(source))
        self.assertIn('mRestartButtonFill.setLevel((Integer) animation.getAnimatedValue())', source)
        self.assertIn('mHandler.postDelayed(mRestartRunnable, 1000)', source)
        self.assertIn('if (!mRestartInProgress)', source)
        self.assertNotIn('mRestartProgress', source)


if __name__ == '__main__':
    unittest.main()
