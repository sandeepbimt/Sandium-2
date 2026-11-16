"""Narrow header/tile visual-balance contracts; device render still required."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
S=(ROOT/'android/java/org/chromium/chrome/browser/ui/appmenu/SandiumPagedMenu.java').read_text()
class MenuBalance(unittest.TestCase):
 def test_remove_only_header_top_space_and_keep_touch_floor(self):
  self.assertIn('panel.setPadding(dp(12), 0, dp(12), dp(8))',S)
  self.assertIn('dp(8 + 48 + 24 + 48) + rows * tileHeight()',S)
  self.assertIn('heading.setMinimumHeight(dp(48))',S)
  self.assertIn('heading.setBaselineAligned(false)',S)
  self.assertIn('heading.setGravity(Gravity.CENTER_VERTICAL)',S)
  self.assertIn('((TextView) child).setIncludeFontPadding(false)',S)
  self.assertIn('((TextView) child).setGravity(Gravity.CENTER)',S)
 def test_center_actual_stack_inside_unchanged_tile_envelope(self):
  tile=S[S.index('private LinearLayout tile()'):S.index('private Drawable allMenuIcon()')]
  self.assertIn('tile.setGravity(Gravity.CENTER)',tile)
  self.assertIn('tile.setMinimumHeight(tileHeight())',tile)
  self.assertIn('new LinearLayout.LayoutParams(-1, ViewGroup.LayoutParams.WRAP_CONTENT)',tile)
  self.assertIn('tile.setPadding(dp(3), dp(4), dp(3), dp(4))',tile)
  self.assertIn('Math.max(dp(48), dp(26 + 2 + 4 + 4) + labelHeight())',S)
 def test_single_and_double_line_stack_balanced(self):
  for line in [14,18,24,36]:
   tile=max(48,26+2+4+4+2*line)
   for lines in [1,2]:
    content=26+2+lines*line
    free=tile-content
    self.assertGreaterEqual(free/2,4)
    self.assertEqual(free/2+content/2,tile/2)
if __name__=='__main__':unittest.main()
