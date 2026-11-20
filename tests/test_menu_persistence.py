"""Persistence call-site guards plus state roundtrip across separate JVMs.
The latter uses real files, not Android SharedPreferences/device process death.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest
import shutil
ROOT = Path(__file__).resolve().parents[1]
JAVA = ROOT/'android/java/org/chromium/chrome/browser/ui/appmenu'
S = (JAVA/'SandiumPagedMenu.java').read_text()
P = (JAVA/'SandiumMenuPreferences.java').read_text()
class MenuPersistence(unittest.TestCase):
    def test_all_edit_paths_save_before_render(self):
        for fragment in [
            'mDraft.move(mDragging, destination, quickAvailable()); persistDraft(); render();',
            'SandiumMenuState.quickDefaultHidden(java.util.Collections.emptySet(), mRecentTabs));\n'
            '                    persistDraft(); mPage = 0; render();',
        ]: self.assertIn(fragment, S)
        options = S[S.index('private void editOptions'):S.index('@Override public boolean dispatchDragEvent')]
        self.assertIn('persistDraft(); render();', options)
    def test_explicit_cancel_restores_and_back_keeps(self):
        self.assertIn('if (writeLayout(mSaved)) { mDraft = null; render(); }', S)
        self.assertIn('if (mDraft != null) { finishEditing(); render(); return true; }', S)
        self.assertIn('if (writeLayout(mDraft)) { mSaved = mDraft; mDraft = null; }', S)
    def test_disk_acknowledgement_and_failure(self):
        self.assertIn('mPreferences.save(value.serialize(), mRecentTabs)', S)
        self.assertIn('boolean committed = editor.commit()', P)
        self.assertNotIn('.apply()', S)
        self.assertIn('android.os.StrictMode.setThreadPolicy(policy);', P)
        self.assertIn('if (mDraft != null && !writeLayout(mDraft)) mDraft = mPersisted.copy();', S)
        self.assertIn('R.string.sandium_menu_save_failed', S)
    @unittest.skipUnless(shutil.which('java'), 'Java runtime unavailable')
    def test_restart_remove_readd_order_cancel_and_file_isolation(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            source = td/'Restart.java'
            source.write_text('''import java.nio.file.*; import java.util.*;
import org.chromium.chrome.browser.ui.appmenu.SandiumMenuState;
public class Restart {
 static List<String> keys=List.of("a","b","c"); static Set<String> all=Set.copyOf(keys);
 static void eq(Object a,Object b) {if(!a.equals(b))throw new AssertionError(a+" != "+b);}
 public static void main(String[] args) throws Exception {
  Path p=Path.of(args[1]); String text=Files.exists(p)?Files.readString(p):null;
  SandiumMenuState s=SandiumMenuState.load(text,keys,Set.of());
  switch(args[0]) {
   case "edit": s.move("c",0,all); s.hide("b"); Files.writeString(p,s.serialize()); break;
   case "check": eq(List.of("c","a"),s.visibleKeys(all)); eq(List.of("b"),s.hiddenKeys(all)); break;
   case "readd": s.show("b"); Files.writeString(p,s.serialize()); break;
   case "checkReadd": eq(List.of("c","a","b"),s.visibleKeys(all)); break;
   case "cancel": SandiumMenuState before=s.copy(); s.hide("a"); Files.writeString(p,s.serialize()); Files.writeString(p,before.serialize()); break;
   case "defaults": eq(keys,s.visibleKeys(all)); break;
  }
 }
}''')
            subprocess.run(['java','com.sun.tools.javac.Main','-d',str(td),str(JAVA/'SandiumMenuState.java'),str(source)],check=True,capture_output=True)
            # Android preference XML may carry its closing-tag indentation into
            # the value of a legacy multiline save. Simulate a fresh process read.
            legacy = td/'legacy'
            legacy.write_text('sandium-menu-v1\nc\t0\na\t0\nb\t1\n    ')
            subprocess.run(['java','-cp',str(td),'Restart','check',str(legacy)],check=True)
            for action in ['edit','check','readd','checkReadd','cancel','checkReadd']:
                subprocess.run(['java','-cp',str(td),'Restart',action,str(td/'normal')],check=True,capture_output=True)
            self.assertFalse((td/'normal').read_text().endswith('\n'))
            corrupt = td/'corrupt'
            for value in ('sandium-menu-v1\nc\t0 \na\t0\nb\t1',
                          'sandium-menu-v1\nc\t0\n    \na\t0\nb\t1',
                          'sandium-menu-v1\nc\t0\na\t0\nb\t1\n    junk'):
                corrupt.write_text(value)
                subprocess.run(['java','-cp',str(td),'Restart','defaults',str(corrupt)],check=True)
            subprocess.run(['java','-cp',str(td),'Restart','defaults',str(td/'other')],check=True,capture_output=True)
if __name__ == '__main__': unittest.main()
