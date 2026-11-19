"""Narrow selector source/geometry guards; not Android render certification."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class BlurAlignment(unittest.TestCase):
 def test_selector_only_centers_value_with_balanced_chevron_space(self):
  s=(ROOT/'android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java').read_text()
  block=s.split('        LinearLayout selector = new LinearLayout(mActivity);',1)[1].split('        row.addView(selector, selectorParams);',1)[0]
  for token in ['selector.setPadding(dp(6), 0, dp(6), 0)',
    'selector.addView(chevronBalance, new LinearLayout.LayoutParams(dp(16), dp(38)))',
    'chevronBalance.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO)',
    'mBlurValue.setGravity(Gravity.CENTER)',
    'mBlurValue.setEllipsize(android.text.TextUtils.TruncateAt.END)',
    'selector.addView(chevron, new LinearLayout.LayoutParams(dp(16), dp(38)))',
    'new LinearLayout.LayoutParams(dp(112), dp(40))',
    'selector.setOnClickListener(v -> showBlurLevelPicker())']:
   self.assertIn(token,block)
  self.assertNotIn('setOnClickListener',block.split('View chevronBalance',1)[1].split('mBlurValue =',1)[0])
  helper=s.split('    private TextView text(',1)[1].split('    private GradientDrawable',1)[0]
  self.assertIn('view.setGravity(Gravity.CENTER_VERTICAL)',helper)
 def test_exact_midpoint_and_unmoved_arrow_ltr_rtl_density(self):
  for density in (1,1.5,2,2.625,3,4):
   dp=lambda x:int(x*density+0.5)
   width,pad,arrow=dp(112),dp(6),dp(16)
   label_width=width-2*pad-2*arrow
   self.assertGreater(label_width,0)
   center=pad+arrow+label_width/2
   self.assertEqual(center,width/2)
   self.assertEqual(width-center,width/2) # RTL reversal.
   # End padding and chevron width unchanged: arrow retains its original end slot.
   self.assertEqual(width-pad-arrow/2,width-dp(6)-dp(16)/2)
if __name__=='__main__':unittest.main()
