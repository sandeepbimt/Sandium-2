"""Compact menu contracts plus real-JVM last-item projection/persistence checks."""
from pathlib import Path
import unittest, tempfile, subprocess, shutil
ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/'android/java/org/chromium/chrome/browser/ui/appmenu'
S=(JAVA/'SandiumPagedMenu.java').read_text()
class MenuCompact(unittest.TestCase):
 def test_normal_geometry_target_and_editor_budget(self):
  # Nominal 12sp Android label line is about14dp. Font metrics scale both layouts.
  line=14
  old_tile=26+4+28+10+max(48+line,2*line)
  new_tile=max(48,26+2+4+4+2*line)
  old=16+48+36+48+3*old_tile
  new=16+48+24+48+3*new_tile
  self.assertAlmostEqual(new/old,.61,delta=.02)
  editor_body=(2*new_tile+24+48+12)+(24+new_tile+12)
  self.assertLessEqual(editor_body+16+48,new+48)
  self.assertIn('dp(16 + 48 + 24 + 48) + rows * tileHeight() + editorExtra',S)
  self.assertIn('int editorExtra = mDraft != null ? dp(48) : 0',S)
 def test_compact_pager_has_single_accessible_control(self):
  self.assertIn('new FrameLayout.LayoutParams(dp(20), dp(3), Gravity.CENTER)',S)
  self.assertIn('new LinearLayout.LayoutParams(dp(28), dp(48))',S)
  self.assertNotIn('if (pages == 2)',S)
  for x in ('ACTION_SCROLL_FORWARD','ACTION_SCROLL_BACKWARD','KEYCODE_DPAD_LEFT','KEYCODE_DPAD_RIGHT','RangeInfo.obtain'):
   self.assertIn(x,S)
  self.assertIn('pager.setMinimumWidth(dp(48))',S)
  self.assertIn('View destination = findViewWithTag("pager")',S)
 def test_editor_and_toggle_keep_full_tile_targets(self):
  self.assertIn('tile.setOnClickListener(v -> editOptions(key))',S)
  self.assertIn('if (!available) bindMove(tile, key)',S)
  self.assertIn('if (mDraft == null) {\n            LinearLayout libraryGroup',S)
  self.assertIn('this::resetLayout',S)
  self.assertIn('tile.setEnabled(enabled(entry.model) && enabled(action))',S)
  self.assertIn('handler.onItemClick(liveAction, null)',S)
  self.assertIn('showNative(current.row)',S)
 @unittest.skipUnless(shutil.which('java'),'Java unavailable')
 def test_all_menu_trails_across_catalog_order_hide_reload_and_move(self):
  with tempfile.TemporaryDirectory() as folder:
   d=Path(folder);p=d/'Trailing.java'
   p.write_text('''import java.util.*; import org.chromium.chrome.browser.ui.appmenu.SandiumMenuState;
public class Trailing {
 static String all="sandium:all-menu";
 static void eq(Object a,Object b){if(!a.equals(b))throw new AssertionError(a+" != "+b);}
 public static void main(String[] args){
  var state=SandiumMenuState.load(null,List.of("a",all,"b","c"),Set.of());
  var live=Set.of("a","b","c"); var home=Set.of("a","c");
  String original=state.serialize();
  eq(List.of("a","b","c",all),state.visibleKeysWithTrailing(live,all));
  eq(List.of("a","c",all),state.visibleKeysWithTrailing(home,all));
  eq(original,state.serialize());
  state.hide(all); state.hide("b");
  eq(List.of("a","c",all),state.visibleKeysWithTrailing(live,all));
  state=SandiumMenuState.load(state.serialize(),List.of("d"),Set.of());
  eq(List.of("a","c","d",all),state.visibleKeysWithTrailing(Set.of("a","b","c","d"),all));
  state.show("b"); state.move("c",0,live);
  eq(List.of("c","a","b",all),state.visibleKeysWithTrailing(live,all));
  state.move("c",3,live); // Dropping onto fixed trailing tile moves user action to last editable position.
  eq(List.of("a","b","c",all),state.visibleKeysWithTrailing(live,all));
  eq(List.of(all),state.visibleKeysWithTrailing(Set.of(),all));
  eq(false,state.move(all,0,live));
 }
}''')
   subprocess.run(['java','com.sun.tools.javac.Main','-d',str(d),str(JAVA/'SandiumMenuState.java'),str(p)],check=True,capture_output=True)
   subprocess.run(['java','-cp',str(d),'Trailing'],check=True,capture_output=True)
if __name__=='__main__':unittest.main()
