from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
class ShortcutDraw(unittest.TestCase):
 def test_chevron_reuses_path_and_rtl_end(self):
  text=(R/'android/java/org/chromium/chrome/browser/suggestions/mostvisited/SandiumHomeShortcuts.java').read_text()
  draw=text.split('@Override protected void onDraw(android.graphics.Canvas canvas) {',1)[1].split('    private void finishDrag()',1)[0]
  self.assertNotIn('new android.graphics.Path',draw)
  self.assertIn('chevronPath.reset()',draw)
  self.assertIn('canvas.drawPath(chevronPath,paint)',draw)
  self.assertIn('Gravity.TOP|Gravity.END',text)
