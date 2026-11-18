"""Executable draft logic; no claim of Android drag-event/runtime validation."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class EditorStateTest(unittest.TestCase):
 def test_cancel_toggle_reorder_drop_reset(self):
  code='''package org.chromium.chrome.browser.ui.appmenu;import java.util.*;public class EditorStateTest{static void check(boolean b){if(!b)throw new AssertionError();}public static void main(String[]args){
   List<String> original=new ArrayList<>(List.of("a","b","c","d"));Map<String,Boolean> visible=new LinkedHashMap<>();visible.put("a",true);visible.put("b",false);visible.put("c",true);visible.put("d",false);
   RawSMenuEditorState draft=new RawSMenuEditorState(original,visible,original);
   check(draft.selected(true).equals(List.of("a","c")));check(draft.toggle("b"));check(draft.selected(true).equals(List.of("a","c","b")));
   check(draft.move("b",-1));check(draft.selected(true).equals(List.of("a","b","c")));check(!draft.move("a",-1));check(!draft.move("a",0));
   check(draft.drop("d","a"));check(draft.visible("d"));check(draft.selected(true).equals(List.of("d","a","b","c")));
   check(draft.toggle("a"));check(!draft.visible("a"));check(draft.drop("d","a"));check(!draft.visible("d"));check(!draft.drop("fake","a"));check(!draft.toggle("fake"));
   check(original.equals(List.of("a","b","c","d")));check(!visible.get("b"));
   draft.reset();check(draft.resetRequested());check(draft.order().equals(original));check(draft.selected(false).isEmpty());
   draft.order().clear();check(draft.order().size()==4);
  }}'''
  with tempfile.TemporaryDirectory() as tmp:
   test=Path(tmp)/'EditorStateTest.java';test.write_text(code)
   source=ROOT/'sandium/menu/java/org/chromium/chrome/browser/ui/appmenu/RawSMenuEditorState.java'
   r=subprocess.run(['java','com.sun.tools.javac.Main','-Xlint:all','-Werror','-d',tmp,str(source),str(test)],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
   r=subprocess.run(['java','-cp',tmp,'org.chromium.chrome.browser.ui.appmenu.EditorStateTest'],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
