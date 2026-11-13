"""Regression tests for the checkpoint-safe Balanced toolbar overlay."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / '.circleci/scripts/apply-sandium-branding-refresh.py'
if not SCRIPT.exists():
    SCRIPT = Path(__file__).with_name('apply-sandium-branding-refresh.py')
spec = importlib.util.spec_from_file_location('branding_balanced', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class BalancedTracerTest(unittest.TestCase):
    def patch(self, root):
        path = root / 'android/java/org/chromium/chrome/browser/toolbar/top/BraveToolbarLayoutImpl.java'
        path.parent.mkdir(parents=True)
        path.write_text('''class BraveToolbarLayoutImpl {
    private void setRewardsLayoutVisibility(int visibility) {
    }
    private void requestToolbarSnapshotCapture() {}
    public void updateBraveShieldsButtonState(Tab tab) {
        // legacy checkpoint halo
        android.graphics.RenderEffect.createBlurEffect();
    }
    private boolean isShieldsOnForTab(Tab tab) { return true; }
}
''')
        mod.replace_toolbar_method(root)
        return path

    def test_reapplication_is_exactly_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path = self.patch(root)
            first = path.read_text()
            mod.replace_toolbar_method(root)
            self.assertEqual(first, path.read_text())
            self.assertEqual(1, first.count('class SandiumShieldsTracer'))
            self.assertNotIn('RenderEffect', first)
            self.assertNotIn('sandium_shields_glow', first)

    def test_shape_and_lifecycle_contract(self):
        with tempfile.TemporaryDirectory() as d:
            text = self.patch(Path(d)).read_text()
            for token in ('outline.close()', 'outline.lineTo(', 'length * 0.35f',
                          '2.0f *', '3200L', 'isAttachedToWindow()', 'isShown()',
                          'hasWindowFocus()', 'ValueAnimator.areAnimatorsEnabled()',
                          'onViewDetachedFromWindow', 'unscheduleSelf(this)',
                          'removeOnGlobalLayoutListener(this)',
                          'removeOnWindowFocusChangeListener(this)'):
                self.assertIn(token, text)
            self.assertNotIn('addCircle', text)
            self.assertNotIn('addOval', text)
            self.assertNotIn('setScaleX', text)
            self.assertIn('tab != null && isShieldsOnForTab(tab)', text)
            self.assertIn('mRewardsLayout.setVisibility(View.GONE)', text)

if __name__ == '__main__':
    unittest.main()
