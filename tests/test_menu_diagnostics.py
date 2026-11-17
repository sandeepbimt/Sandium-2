"""Numeric diagnostic boundary and extracted real presenter edit/reopen method tests.
Host Java only: not Android view lifecycle or actual SharedPreferences process death.
"""
from pathlib import Path
import re, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[1]
JAVA=ROOT/'android/java/org/chromium/chrome/browser/ui/appmenu'
class MenuDiagnostics(unittest.TestCase):
 def test_numeric_boundary_and_actual_edit_methods(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   sources={
'org/chromium/ui/modelutil/PropertyModel.java':'package org.chromium.ui.modelutil; public class PropertyModel {}',
'org/chromium/ui/modelutil/MVCListAdapter.java':'package org.chromium.ui.modelutil; public class MVCListAdapter {public static class ModelList {}}',
'android/widget/Toast.java':'package android.widget; public class Toast {public static final int LENGTH_LONG=1; public static Toast makeText(Object c,int r,int d){return new Toast();} public void show(){}}',
   }
   source=(JAVA/'SandiumPagedMenu.java').read_text()
   methods=source[source.index('    private boolean writeLayout('):source.index('    boolean handleBack()')]
   harness='''package org.chromium.chrome.browser.ui.appmenu;
import java.nio.file.*;import java.util.*;
public class DiagnosticTest {
 static class R {static class string {static int sandium_menu_save_failed=1;}}
 static class Store {Path path;Store(Path p){path=p;} boolean save(String s){try{Files.writeString(path,s);return true;}catch(Exception e){return false;}}}
 Store mPreferences;SandiumMenuState mSaved,mPersisted,mDraft;long mDiagnosticSequence;
 org.chromium.ui.modelutil.MVCListAdapter.ModelList mModels=new org.chromium.ui.modelutil.MVCListAdapter.ModelList();
 Object getContext(){return null;}
 DiagnosticTest(Path path)throws Exception {mPreferences=new Store(path);mSaved=SandiumMenuState.load(Files.exists(path)?Files.readString(path):null,List.of("exit_id","share_menu_id","print_id"),Set.of());mPersisted=mSaved.copy();}
 '''+methods+'''
 static void eq(Object a,Object b){if(!a.equals(b))throw new AssertionError(a+" != "+b);}
 public static void main(String[] args)throws Exception {
  Path path=Path.of(args[0]);DiagnosticTest a=new DiagnosticTest(path);
  a.mDraft=a.mSaved.copy();a.mDraft.hide("share_menu_id");a.mDraft.move("print_id",0,Set.of("exit_id","share_menu_id","print_id"));a.persistDraft();
  // Outside-dismiss/reopen: completed edits were saved, without Done.
  DiagnosticTest b=new DiagnosticTest(path);eq(List.of("print_id","exit_id"),b.mSaved.visibleKeys(Set.of("exit_id","share_menu_id","print_id")));
  b.mDraft=b.mSaved.copy();b.mDraft.show("share_menu_id");b.persistDraft();b.finishEditing();
  DiagnosticTest c=new DiagnosticTest(path);eq(false,c.mSaved.isHidden("share_menu_id"));
  // Explicit Cancel persists entry snapshot, unlike dismiss.
  c.mDraft=c.mSaved.copy();c.mDraft.hide("exit_id");c.persistDraft();if(c.writeLayout(c.mSaved))c.mDraft=null;
  eq(false,new DiagnosticTest(path).mSaved.isHidden("exit_id"));
  long h=SandiumMenuMetadata.diagnosticFingerprint(List.of("exit_id"),null);
  eq(h,SandiumMenuMetadata.diagnosticFingerprint(List.of("exit_id","unknown.private.identifier"),null));
  if(h==SandiumMenuMetadata.diagnosticFingerprint(List.of("share_menu_id"),null))throw new AssertionError();
  int[] count={0};SandiumMenuMetadata.diagnostic(a.mModels,16,1,1,1,1,h);eq(0,count[0]);
  SandiumMenuMetadata.diagnostics(a.mModels,(event,values)->{eq(16,event);eq(5,values.length);count[0]++;});
  SandiumMenuMetadata.diagnostic(a.mModels,16,1,1,1,1,h);eq(1,count[0]);
  SandiumMenuMetadata.diagnostics(a.mModels,null);SandiumMenuMetadata.diagnostic(a.mModels,16,1,1,1,1,h);eq(1,count[0]);
 }
}'''
   sources['org/chromium/chrome/browser/ui/appmenu/DiagnosticTest.java']=harness
   paths=[]
   for name,text in sources.items():
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text);paths.append(str(p))
   subprocess.run(['java','com.sun.tools.javac.Main','-d',str(root),*paths,str(JAVA/'SandiumMenuState.java'),str(JAVA/'SandiumMenuMetadata.java')],check=True,capture_output=True)
   subprocess.run(['java','-cp',str(root),'org.chromium.chrome.browser.ui.appmenu.DiagnosticTest',str(root/'prefs')],check=True,capture_output=True)
 def test_events_do_not_export_layout_strings(self):
  source=(JAVA/'SandiumPagedMenu.java').read_text()
  for event in (16,17,18):self.assertIn('SandiumMenuMetadata.diagnostic(mModels, '+str(event),source)
  self.assertNotIn('hashCode()', (JAVA/'SandiumMenuMetadata.java').read_text())
  self.assertIn('if (id == 0) continue;', (JAVA/'SandiumMenuMetadata.java').read_text())
if __name__=='__main__':unittest.main()
