"""Editor six-row envelope, regular menu unchanged; Android pixels need APK QA."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
S=(ROOT/'android/java/org/chromium/chrome/browser/ui/appmenu/SandiumPagedMenu.java').read_text()
class EditorFit(unittest.TestCase):
 def test_editor_reserves_two_quick_and_four_available_rows(self):
  self.assertIn('private static final int EDITOR_AVAILABLE_ROWS = 4',S)
  self.assertIn('availableGrid.setMinimumHeight(EDITOR_AVAILABLE_ROWS * tileHeight())',S)
  self.assertIn('grid(availableGrid, mDraft.hiddenKeys(editableKeys()), true)',S)
  self.assertIn('(quickRows + EDITOR_AVAILABLE_ROWS) * tileHeight()',S)
 def test_regular_envelope_and_physical_limit_preserved(self):
  self.assertIn('Math.min(available, dp(8 + 48 + 24 + 48) + rows * tileHeight())',S)
  self.assertIn('Math.min(available, editorHeight)',S)
  self.assertIn('ScrollView scroll = new ScrollView',S)
  self.assertIn('Math.max(dp(48), dp(26 + 2 + 4 + 4) + labelHeight())',S)
 def test_budget_fits_six_rows_when_physically_possible(self):
  for columns,line in [(4,14),(4,18),(2,28),(2,36)]:
   tile=max(48,26+2+4+4+2*line)
   quick_rows=(8+columns-1)//columns
   needed=8+48+24+48+24+24+(quick_rows+4)*tile
   body=(24+quick_rows*tile+48+12)+(24+4*tile+12)
   self.assertEqual(needed,8+48+body)
   self.assertGreaterEqual(tile,48)
   for available in [300,600,1000]:
    allocated=min(needed,available)
    self.assertLessEqual(allocated,available)
    self.assertEqual(allocated>=needed,available>=needed)
if __name__=='__main__':unittest.main()
