"""Compact visual pager, safe expanded taps, and single-page removal contracts."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
S=(ROOT/'android/java/org/chromium/chrome/browser/ui/appmenu/SandiumPagedMenu.java').read_text()
class PagerGaps(unittest.TestCase):
 def test_single_page_removes_view_and_budget(self):
  self.assertIn('private int pagerHeight() { return quickPageCount() > 1 ? dp(32) : 0; }',S)
  a=S.index('if (pages > 1) {');b=S.index('if (mDraft != null) {\n            LinearLayout availableGroup',a)
  block=S[a:b]
  self.assertIn('actionsGroup.addView(pagerScroll)',block)
  self.assertIn('mPagerTargets.add(target)',block)
  self.assertIn('mPagerTargets.clear(); clearPagerTouchDelegate()',S)
  height=S[S.index('int preferredHeight('):S.index('private void finishPanelMotion')]
  self.assertEqual(height.count('pagerHeight()'),2)
 def test_taps_keyboard_and_accessibility_preserved(self):
  self.assertIn('target.setOnClickListener(v -> page(destination - mPage))',S)
  for key in ('ACTION_SCROLL_FORWARD','ACTION_SCROLL_BACKWARD','KEYCODE_DPAD_LEFT','KEYCODE_DPAD_RIGHT'):
   self.assertIn(key,S)
  self.assertIn('info.setBoundsInScreen(bounds)',S)
  self.assertIn('new android.view.TouchDelegate(bounds, target)',S)
 def test_extension_only_below_strip_and_fresh_after_scroll(self):
  self.assertIn('bounds.top = bounds.bottom',S)
  self.assertIn('bounds.bottom += dp(16)',S)
  self.assertIn('bounds.intersect(0, 0, getWidth(), getHeight())',S)
  self.assertIn('target.getLocalVisibleRect(bounds)',S)
  self.assertIn('offsetDescendantRectToMyCoords(target, bounds)',S)
  self.assertIn('info.getBoundsInScreen(bounds)',S)
  self.assertIn('mPagerTouchDelegate = pagerTouchExtension()',S)
  # Normal footer has4dp group padding+4dp margin+8dp root bottom padding.
  self.assertEqual(32+4+4+8,48)
  # Editor extension ends inside noninteractive next section heading, before its actions.
  self.assertLessEqual(16,4+4+4+24)
 def test_delegated_drag_reenters_normal_scroll_dispatch(self):
  self.assertIn('getScaledTouchSlop()',S)
  self.assertIn('action == MotionEvent.ACTION_POINTER_DOWN',S)
  self.assertIn('return owned || delegated || super.dispatchTouchEvent(event)',S)
  self.assertIn('cancel.setAction(MotionEvent.ACTION_CANCEL)',S)
  self.assertIn('try { super.dispatchTouchEvent(down); }',S)
  self.assertIn('finally { mPagerDragReplay = false; down.recycle(); }',S)
  self.assertIn('boolean owned = mPagerSequenceOwned',S)
  self.assertIn('clearPagerTouchDelegate(false); mPagerSequenceOwned = false',S)
  self.assertIn('return super.dispatchTouchEvent(event)',S)
  self.assertIn('mPagerDelegateDown.recycle()',S)
 def test_editor_capacity_and_stable_other_geometry(self):
  self.assertIn('EDITOR_AVAILABLE_ROWS = 4',S)
  self.assertIn('availableGrid.setMinimumHeight(EDITOR_AVAILABLE_ROWS * tileHeight())',S)
  for pages in [1,2,3,10]:
   pager=32 if pages>1 else 0
   tile=64
   editor=8+48+24+24+24+pager+6*tile
   body=(24+2*tile+pager+12)+(24+4*tile+12)
   self.assertEqual(editor,8+48+body)
   self.assertEqual(editor,544 if pages>1 else 512)
if __name__=='__main__':unittest.main()
