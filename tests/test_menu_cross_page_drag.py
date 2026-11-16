from pathlib import Path
import unittest
S=(Path(__file__).resolve().parents[1]/'android/java/org/chromium/chrome/browser/ui/appmenu/SandiumPagedMenu.java').read_text()
class CrossPageDrag(unittest.TestCase):
 def test_sheet_owns_session_across_render(self):
  body=S[S.index('@Override public boolean dispatchDragEvent'):S.index('@Override public boolean dispatchKeyEvent')]
  self.assertIn('mDragging.equals(event.getLocalState())',body)
  self.assertIn('if (!local || mDraft == null) return super.dispatchDragEvent(event)',body)
  self.assertNotIn('setOnDragListener',S)
  self.assertIn('case DragEvent.ACTION_DRAG_LOCATION:',body)
  self.assertIn('mDraft.move(mDragging, destination, quickAvailable())',body)
  self.assertIn('return false; // A drop outside visible action tiles',body)
 def test_hover_cancellation_and_bounds(self):
  self.assertIn('postDelayed(mDragPageTask, 450)',S)
  self.assertIn('if (target == mDragPageTarget) return',S)
  self.assertIn('mDraft == draft && moving != null && moving.equals(mDragging)',S)
  self.assertIn('target >= 0 && target < quickPageCount()',S)
  self.assertIn('getGlobalVisibleRect(bounds)',S)
  self.assertIn('case DragEvent.ACTION_DRAG_EXITED:',S)
  self.assertIn('cancelDragPage(); mDragging = null;',S)
 def test_popup_origin_consistency(self):
  self.assertNotIn('getLocationOnScreen',S)
  self.assertIn('origin.x + (int) x',S)
  # Popup screen origin is irrelevant: both bounds and event are mapped to root.
  for popup_screen_y in [0,400,900]:
   sheet_root=(12,8); tile_root=(32,108,120,204); event=(30,110)
   x,y=sheet_root[0]+event[0],sheet_root[1]+event[1]
   self.assertTrue(tile_root[0]<=x<tile_root[2] and tile_root[1]<=y<tile_root[3])
 def test_no_moving_geometry_during_drag(self):
  self.assertIn('&& !mNativeVisible && mDragging == null',S)
  self.assertIn('if (mResize != null && mDragging == null) post(mResize)',S)
 def test_directory_uses_saved_order_and_same_storage(self):
  self.assertIn('for (String key : mSaved.knownKeys()) if (available.contains(key)) directory.add(key)',S)
  self.assertIn('.getString("layout", ""), mCatalog.keySet(), hidden)',S)
  self.assertIn('.putString("layout", value.serialize()).commit()',S)
if __name__=='__main__':unittest.main()
