"""Source contracts, not proof of Android frame pacing."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
class MenuPressFeedback(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / 'android/java/org/chromium/chrome/browser/ui/appmenu/SandiumPagedMenu.java').read_text()
        self.helper = self.text.split('private void bindPressFeedback(View view) {', 1)[1].split('private TextView button(', 1)[0]
    def test_native_feedback_and_static_fallback(self):
        for token in ('RippleDrawable(', 'StateListDrawable()', 'areAnimatorsEnabled()', 'SysUtils.isLowEndDevice()', 'state_focused', '-android.R.attr.state_enabled', 'shape(Color.WHITE, 12)'):
            self.assertIn(token, self.helper)
        self.assertNotIn('setOnTouchListener', self.helper)
        self.assertNotIn('postDelayed', self.helper)
        self.assertNotIn('setScale', self.helper)
        self.assertNotIn('setTranslation', self.helper)
    def test_controls_have_feedback(self):
        for target in ('t', 'tile', 'target'):
            self.assertIn('bindPressFeedback(' + target + ');', self.text)
if __name__ == '__main__':
    unittest.main()
