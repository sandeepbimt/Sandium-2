import importlib.util
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('capture',ROOT/'.circleci/scripts/apply-sandium-capture-coherence.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
FIX=ROOT/'tests/fixtures/capture-coherence'

class Capture(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name)
  for f in FIX.glob('*.java'):
   p=self.root/m.BASE/f.name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(f.read_bytes())
 def test_apply_reapply_and_readback(self):
  result=m.plan(self.root)
  for p,s in result.items():p.write_text(s)
  self.assertEqual(result,m.plan(self.root))
  self.assertIn('mHomeButton.getImageAlpha()',result[self.root/m.BASE/'ToolbarPhone.java'])
 def test_drift_rejects_before_writes(self):
  p=self.root/m.BASE/'ToolbarControlContainer.java';p.write_text(p.read_text().replace('private boolean shouldCaptureWhileHidden()', 'private boolean drifted()'))
  before={p:p.read_bytes() for p in self.root.rglob('*.java')}
  with self.assertRaises(RuntimeError):m.plan(self.root)
  self.assertEqual(before,{p:p.read_bytes() for p in before})
 def test_composes_with_shipping_phone_and_homepage(self):
  def module(file):
   spec=importlib.util.spec_from_file_location(file,ROOT/'.circleci/scripts'/file)
   value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
  bottom=module('apply-sandium-bottom-toolbar.py');unified=module('apply-sandium-unified-address.py');refine=module('apply-sandium-toolbar-refinements.py');home=module('apply-sandium-homepage-surround.py')
  source=(FIX/'ToolbarPhone.java').read_text();source=bottom.phone(source)
  for fn in [unified.phone,unified.phone_leading_shield,unified.phone_shield_state,unified.responsive,refine.phone,refine.capsule_color]:source=fn(source)
  # Apply only this class's actual shipping homepage paint transformations.
  for name,old,new in home.CHANGES:
   if name=='ToolbarPhone.java': source=m.replace(source,old,new)
  result=m.phone(source)
  self.assertIn('mHomeButton.getImageAlpha()',result)
  self.assertIn('setSandiumToolbarWallpaperPaintColor',result)
  self.assertIn('SANDIUM_ADDRESS_SHADE_V1',result)
  self.assertEqual(result,m.phone(result))
 def test_no_native_capture_suppression_bypass(self):
  original=(FIX/'ToolbarControlContainer.java').read_text();modified=m.container(original)
  self.assertIn('mBrowserControlsStateProvider.getBrowserControlHiddenRatio() >= 1f',modified)
  for anchor in ('TopToolbarBlockCaptureReason.BROWSER_CONTROLS_LOCKED','TopToolbarBlockCaptureReason.COMPOSITOR_IN_MOTION','return checkCaptureReadinessResult();','mNeedCaptureAfterPageLoad = true;'):
   self.assertEqual(original.count(anchor),modified.count(anchor))
 @unittest.skipUnless(shutil.which('java'),'Java unavailable')
 def test_exact_token_and_hidden_predicate_compile_execute(self):
  s=m.token((FIX/'PhoneCaptureStateToken.java').read_text())
  s=re.sub(r'^package .*;\n|^import .*;\n','',s,flags=re.M)
  s=re.sub(r'@\w+','',s)
  constants=sorted(set(re.findall(r'ToolbarSnapshotDifference\.(\w+)',s)))
  pre='import java.util.Objects;\nclass ColorStateList {int c;ColorStateList(int x){c=x;}int getDefaultColor(){return c;}}\nclass ButtonData {}\nclass VisibleUrlText {String s;VisibleUrlText(String v){s=v;}static boolean isVisuallyEquivalent(VisibleUrlText a,VisibleUrlText b){return a.s.equals(b.s);}}\nclass ToolbarSnapshotDifference {'+''.join('static final int '+c+'='+str(i)+';' for i,c in enumerate(constants))+'}\n'
  container=m.container((FIX/'ToolbarControlContainer.java').read_text())
  a=container.index('        private boolean shouldCaptureWhileHidden()');b=container.index('\n        }',a)+10
  hidden=container[a:b]
  test=r'''
class CaptureHarness {
 static PhoneCaptureStateToken make(boolean enabled,int alpha,String url){
 return new PhoneCaptureStateToken(1,2,3,null,0,new VisibleUrlText(url),4,new ColorStateList(5),true,false,false,0,100,1,90,enabled,alpha);
 }
 static void check(boolean b){if(!b)throw new AssertionError();}
 static class Flag {boolean enabled=true;boolean isEnabled(){return enabled;}}
 static class ChromeFeatureList {static Flag sToolbarCaptureFixForSPAs=new Flag();}
 static class Provider {boolean bottom;float topRatio,bottomRatio;float getBrowserControlHiddenRatio(){return bottom?bottomRatio:topRatio;}}
 boolean mIsDestroyed;Provider mBrowserControlsStateProvider=new Provider();
 HIDDEN
 public static void main(String[] args){
  PhoneCaptureStateToken on=make(true,255,"same"),off=make(false,97,"same");
  check(PhoneCaptureStateToken.getAnyDifference(on,make(true,255,"same"))==ToolbarSnapshotDifference.NONE);
  check(PhoneCaptureStateToken.getAnyDifference(on,off)==ToolbarSnapshotDifference.HOME_BUTTON);
  check(PhoneCaptureStateToken.getAnyDifference(on,make(false,255,"same"))==ToolbarSnapshotDifference.HOME_BUTTON);
  check(PhoneCaptureStateToken.getAnyDifference(on,make(true,97,"same"))==ToolbarSnapshotDifference.HOME_BUTTON);
  check(PhoneCaptureStateToken.getAnyDifference(off,on)==ToolbarSnapshotDifference.HOME_BUTTON);
  check(PhoneCaptureStateToken.getAnyDifference(on,make(true,255,"new"))==ToolbarSnapshotDifference.URL_TEXT);
  PhoneCaptureStateToken legacy=new PhoneCaptureStateToken(1,2,3,null,0,new VisibleUrlText("same"),4,new ColorStateList(5),true,false,false,0,100,1,90);
  check(PhoneCaptureStateToken.getAnyDifference(legacy,on)==ToolbarSnapshotDifference.NONE);
  CaptureHarness h=new CaptureHarness();Provider p=h.mBrowserControlsStateProvider;p.bottom=true;p.topRatio=0;p.bottomRatio=1;check(h.shouldCaptureWhileHidden());
  p.topRatio=1;p.bottomRatio=0;check(!h.shouldCaptureWhileHidden());p.bottomRatio=.5f;check(!h.shouldCaptureWhileHidden());
  p.bottom=false;check(h.shouldCaptureWhileHidden());p.topRatio=0;check(!h.shouldCaptureWhileHidden());
  p.topRatio=1;h.mIsDestroyed=true;check(!h.shouldCaptureWhileHidden());h.mIsDestroyed=false;
  ChromeFeatureList.sToolbarCaptureFixForSPAs.enabled=false;check(!h.shouldCaptureWhileHidden());ChromeFeatureList.sToolbarCaptureFixForSPAs.enabled=true;
  h.mBrowserControlsStateProvider=null;check(!h.shouldCaptureWhileHidden());
 }
}
'''.replace('HIDDEN',hidden)
  path=self.root/'CaptureHarness.java';path.write_text(pre+s+test)
  cmd=['javac'] if shutil.which('javac') else ['java','-m','jdk.compiler/com.sun.tools.javac.Main']
  p=subprocess.run(cmd+[str(path)],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
  subprocess.run(['java','-cp',str(self.root),'CaptureHarness'],check=True,capture_output=True,text=True)

if __name__=='__main__':unittest.main()
