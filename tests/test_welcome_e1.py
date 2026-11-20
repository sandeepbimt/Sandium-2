"""E1 experiment-only contracts, not the frozen production presentation."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
class E1(unittest.TestCase):
 def test_detail_visibility_and_retry(self):
  s=(R/'android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java').read_text()
  self.assertIn('mProtectionDetails.setVisibility(View.GONE)',s)
  self.assertIn('mProtectionDetails.setVisibility(mExpanded ? View.VISIBLE : View.GONE)',s)
  for name in ('progressRow','mEngineState','mFilterCount','mFinalizing'):
   self.assertIn('mProtectionDetails.addView('+name+', matchWrap())',s)
  self.assertEqual(s.count('mProtectionSubtitle.setText(R.string.sandium_welcome_status_retry)'),2)
 def test_readiness_and_accessibility(self):
  s=(R/'android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java').read_text()
  for guard in ('return ready && allEnabledFiltersDownloaded(downloaded, total);','return total > 0 && downloaded == total;','more.setMinimumHeight(dp(48))','option.setMinimumHeight(dp(48))','Math.max(13f, originalSizeSp * 0.94f)'):
   self.assertIn(guard,s)
  self.assertNotIn('START_FEEDBACK_MS',s)
  self.assertNotIn('mRestartAnimator',s)
if __name__=='__main__':unittest.main()
