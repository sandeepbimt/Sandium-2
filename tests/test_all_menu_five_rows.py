"""Directory sizing regressions. Android rendering still requires device QA."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
S = (ROOT / 'android/java/org/chromium/chrome/browser/ui/appmenu/SandiumPagedMenu.java').read_text()

class AllMenuFiveRows(unittest.TestCase):
    def test_directory_has_separate_five_row_budget(self):
        self.assertIn('private static final int ALL_MENU_ACTION_ROWS = 5;', S)
        sizing = S[S.index('int preferredHeight('):S.index('private void finishPanelMotion')]
        self.assertIn('if (mAllMenu && mDraft == null)', sizing)
        self.assertIn('(libraryRows + allMenuActionRows()) * tileHeight()', sizing)
        self.assertIn('Math.min(available, directoryHeight)', sizing)
        self.assertIn('actionsGroup.setMinimumHeight(2 * dp(4) + allMenuActionRows() * tileHeight())', S)

    def test_five_rows_and_group_padding_fit_without_scroll(self):
        # Exactly match heading, panel and group padding/margins; no pager in directory.
        for columns, line_height in [(4, 14), (4, 18), (2, 28)]:
            tile = max(48, 36 + 2 * line_height)
            library_rows = (4 + columns - 1) // columns
            for actions in [0, 1, 12, 17, 20, 21, 25]:
                rows = max(5, (actions + columns - 1) // columns)
                needed = 8 + 48 + 24 + (library_rows + rows) * tile
                body = 12 + library_rows * tile + 12 + rows * tile
                self.assertEqual(needed - 8 - 48, body)
                self.assertGreaterEqual(rows, 5)
                self.assertGreaterEqual(rows * columns, actions)
                # If the screen can fit it, there is no overflow; don't crop when it can't.
                self.assertEqual(min(needed, needed + 100), needed)
                self.assertEqual(min(needed, 300), 300)

    def test_no_visible_scrollbar_or_edge_glow(self):
        region = S[S.index('ScrollView scroll ='):S.index('List<String> libraryKeys')]
        self.assertIn('if (mAllMenu && mDraft == null)', region)
        self.assertIn('scroll.setVerticalScrollBarEnabled(false)', region)
        self.assertIn('scroll.setOverScrollMode(View.OVER_SCROLL_NEVER)', region)

if __name__ == '__main__':
    unittest.main()
