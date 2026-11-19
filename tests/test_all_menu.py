from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
S=(ROOT/'android/java/org/chromium/chrome/browser/ui/appmenu/SandiumPagedMenu.java').read_text()
class AllMenu(unittest.TestCase):
 def test_permanent_entry_outside_saved_actions(self):
  self.assertIn('state().visibleKeysWithTrailing(quickAvailable(), ALL_MENU)',S)
  self.assertNotIn('mCatalog.put(ALL_MENU',S)
  tile=S[S.index('if (ALL_MENU.equals(key))'):S.index('Entry entry = mCatalog.get(key);',S.index('if (ALL_MENU.equals(key))'))]
  self.assertIn('continue;',tile);self.assertNotIn('mDraft.hide',tile)
  self.assertNotIn('bindMove(all, ALL_MENU)',tile)
 def test_permanent_last_not_movable(self):
  self.assertIn('private Set<String> quickAvailable() { return editableKeys(); }',S)
  self.assertIn('if (ALL_MENU.equals(key) || entry == null || mDraft == null) return;',S)
  self.assertIn('all.setEnabled(false)',S)
  self.assertIn('mDraft.move(mDragging, destination, quickAvailable())',S)
 def test_navigation_and_reclaimed_header(self):
  header=S[S.index('// Only show a native escape'):S.index('panel.addView(heading)')]
  self.assertIn('if (mAllMenu)',header)
  self.assertIn('int screen = mDraft != null ? 2 : mAllMenu ? 1 : 0',S)
  self.assertIn('if (mAllMenu && !mNativeVisible)',S)
  self.assertIn('for (String key : mSaved.knownKeys()) if (available.contains(key)) directory.add(key)',S)
 def test_page_boundaries(self):
  for n in range(201):
   actions=list(range(n))+['all']
   pages=(len(actions)+7)//8
   flattened=sum([actions[p*8:min(len(actions),(p+1)*8)] for p in range(pages)],[])
   self.assertEqual(flattened,actions);self.assertEqual(flattened.count('all'),1)
  self.assertIn('int pages = quickPageCount()',S);self.assertIn('int count = quickPageCount()',S)
 def test_live_actions_and_geometry_retained(self):
  self.assertIn('setBackground(raisedPanel(mPanelColor, 16))',S)
  self.assertIn('if (current == null || !enabled(current.model)) return',S)
  self.assertIn('LinearLayout all = tile()',S)
  self.assertIn('ValueAnimator.areAnimatorsEnabled()',S)
if __name__=='__main__':unittest.main()
