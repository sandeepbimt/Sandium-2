import gzip, hashlib, importlib.util, json, subprocess, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'experiments/single-handoff'
spec=importlib.util.spec_from_file_location('ui_gate',BASE/'ui_gate.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
STUB='''
public class Gate {
 static class Supplier<T> { T value; Runnable hook; Supplier(T v){value=v;} T get(){if(hook!=null)hook.run();return value;} }
 static class Activity { boolean finishing,destroyed; boolean isFinishing(){return finishing;} boolean isDestroyed(){return destroyed;} }
 static class Obscuring { boolean content,toolbar; boolean isTabContentObscured(){return content;} boolean isToolbarObscured(){return toolbar;} }
 static class Modal { boolean showing; boolean isShowing(){return showing;} }
 static class SheetState { static final int NONE=-1,HIDDEN=0,PEEK=1,HALF=2,FULL=3,SCROLLING=4; }
 static class Sheet { int current=0,target=-1; boolean hiding; int getTargetSheetState(){return target;} int getSheetState(){return current;} boolean isSheetHiding(){return hiding;} }
 static class Scrim { Supplier<Boolean> visible=new Supplier<>(false); Supplier<Boolean> getScrimVisibilitySupplier(){return visible;} }
 static class Menu { boolean showing; Menu getAppMenuHandler(){return this;} boolean isAppMenuShowing(){return showing;} }
 Activity mActivity=new Activity();
 Supplier<Obscuring> mTabObscuringHandlerSupplier=new Supplier<>(new Obscuring());
 Supplier<Modal> mModalDialogManagerSupplier=new Supplier<>(new Modal());
 Supplier<Sheet> mBottomSheetControllerSupplier=new Supplier<>(new Sheet());
 Supplier<Scrim> mScrimManagerSupplier=new Supplier<>(new Scrim());
 Menu mAppMenuCoordinator=new Menu();
'''
MAIN='''
 static void ok(boolean b){if(!b)throw new AssertionError();}
 public static void main(String[] args){
  Gate g=new Gate();ok(g.isSandiumNativeHandoffUiClear());
  g.mTabObscuringHandlerSupplier.value.content=true;ok(!g.isSandiumNativeHandoffUiClear());g.mTabObscuringHandlerSupplier.value.content=false;
  g.mTabObscuringHandlerSupplier.value.toolbar=true;ok(!g.isSandiumNativeHandoffUiClear());g.mTabObscuringHandlerSupplier.value.toolbar=false;
  g.mModalDialogManagerSupplier.value.showing=true;ok(!g.isSandiumNativeHandoffUiClear());g.mModalDialogManagerSupplier.value.showing=false;
  for(int s:new int[]{-1,1,2,3,4,999}){g.mBottomSheetControllerSupplier.value.current=s;ok(!g.isSandiumNativeHandoffUiClear());}
  g.mBottomSheetControllerSupplier.value.current=0;
  for(int s:new int[]{1,2,3,4,999}){g.mBottomSheetControllerSupplier.value.target=s;ok(!g.isSandiumNativeHandoffUiClear());}
  g.mBottomSheetControllerSupplier.value.target=0;ok(g.isSandiumNativeHandoffUiClear());
  g.mBottomSheetControllerSupplier.value.hiding=true;ok(!g.isSandiumNativeHandoffUiClear());g.mBottomSheetControllerSupplier.value.hiding=false;
  g.mScrimManagerSupplier.value.visible.value=true;ok(!g.isSandiumNativeHandoffUiClear());
  g.mScrimManagerSupplier.value.visible.value=null;ok(!g.isSandiumNativeHandoffUiClear());g.mScrimManagerSupplier.value.visible.value=false;
  g.mAppMenuCoordinator.showing=true;ok(!g.isSandiumNativeHandoffUiClear());g.mAppMenuCoordinator.showing=false;
  g.mActivity.finishing=true;ok(!g.isSandiumNativeHandoffUiClear());g.mActivity.finishing=false;
  g.mActivity.destroyed=true;ok(!g.isSandiumNativeHandoffUiClear());g.mActivity.destroyed=false;
  Gate unknown=new Gate();unknown.mBottomSheetControllerSupplier.value=null;ok(!unknown.isSandiumNativeHandoffUiClear());
  Gate destroyed=new Gate();destroyed.mScrimManagerSupplier.hook=()->destroyed.mSandiumNativeHandoffUiDestroyed=true;ok(!destroyed.isSandiumNativeHandoffUiClear());
  Gate replaced=new Gate();replaced.mScrimManagerSupplier.hook=()->replaced.mModalDialogManagerSupplier.value=new Modal();ok(!replaced.isSandiumNativeHandoffUiClear());
 }
}
'''
class UiGate(unittest.TestCase):
 def test_exact_transform(self):
  f=json.loads(gzip.decompress((BASE/'fixtures/root-ui-handoff-gate.json.gz').read_bytes()));s=f['source'];self.assertEqual(hashlib.sha256(s.encode()).hexdigest(),f['sha256'])
  out=m.transform(s);self.assertEqual(m.transform(out),out)
  self.assertIn('public void onDestroy() {\n        mSandiumNativeHandoffUiDestroyed = true;',out)
  with self.assertRaises(ValueError):m.transform(out.replace('mSandiumNativeHandoffUiDestroyed = true;',''))
  with self.assertRaises(ValueError):m.transform('unknown')
 def run_methods(self,method):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'Gate.java').write_text(STUB+m.FIELD+method+MAIN);q=p/'org/chromium/base/ThreadUtils.java';q.parent.mkdir(parents=True);q.write_text('package org.chromium.base; public class ThreadUtils { public static void assertOnUiThread(){} }')
   r=subprocess.run(['java','--module','jdk.compiler/com.sun.tools.javac.Main','-Xlint:all','-Werror','-d',d,str(q),str(p/'Gate.java')],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
   return subprocess.run(['java','-cp',d,'Gate'],capture_output=True,text=True)
 def test_actual_method_gate_matrix(self):
  r=self.run_methods(m.METHOD);self.assertEqual(r.returncode,0,r.stderr)
 def test_peek_regression_rejects_unsafe_policy(self):
  mutated=m.METHOD.replace('sheet.getSheetState() == SheetState.HIDDEN','sheet.getSheetState() <= SheetState.PEEK')
  r=self.run_methods(mutated);self.assertNotEqual(r.returncode,0);self.assertIn('AssertionError',r.stderr)
if __name__=='__main__':unittest.main()
