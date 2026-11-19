import importlib.util
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
def load(name):
 spec=importlib.util.spec_from_file_location(name, ROOT/'experiments/single-handoff'/f'{name}.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
m=load('native_blur');web=load('web')
class Blur158(unittest.TestCase):
 def test_pinned_native_and_dim_only(self):
  s=m.fixture(m.CC);out=m.dim_cc(s)
  for text in ['IsSameDocument()', 'IsServedFromBackForwardCache()', 'GetReloadType()', 'navigation_handle->GetURL().host() == prev_url.host()', 'ResetNavigationState(TransitionExitReason::kAnimationTimerExpired)', 'SkColor4f background_color = SkColors::kWhite;']:
   self.assertIn(text,out)
  for bad in ['SandiumNativeBlurCapture','nav-animation-blur-sigma/', 'GetSandiumDarkPageFlagsForNavigation']:
   self.assertNotIn(bad,out)
  self.assertIn('SetOpacity(0.20f)',out)
 def test_plan_is_atomic_readonly_and_rejects_drift(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d)
   for path in [m.CC,m.H,m.FC,m.FH]:
    p=r/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(m.fixture(path))
   result=m.native_plan(r)
   self.assertEqual((r/m.CC).read_text(),m.fixture(m.CC))
   for p,s in result.items():p.write_text(s)
   self.assertEqual(m.native_plan(r),result)
   (r/m.CC).write_text((r/m.CC).read_text()+'// drift')
   with self.assertRaises(ValueError):m.native_plan(r)
 def test_startup_removes_stale_tuning(self):
  out=web.transform(web.OLD)
  self.assertEqual(web.transform(out),out)
  self.assertIn('blurOn = true',out)
  self.assertIn('"default".equals(legacy)',out)
  self.assertIn('"off".equals(legacy)',out)
  self.assertNotIn('nav-animation-blur-sigma/',out)
  self.assertNotIn('nav-animation-fade-hold-duration-ms/',out)
  with self.assertRaises(ValueError):web.transform(web.OLD+'\n'+web.OLD)
 def test_native_parameters_exact(self):
  s=m.fixture(m.FC)
  for value in ['"nav-animation-fade-hold-duration-ms", 350','"nav-animation-fade-out-duration-ms", 150','"nav-animation-blur-sigma",\n    3.0']:
   self.assertIn(value,s)
if __name__=='__main__':unittest.main()

class SettingsContract(unittest.TestCase):
 def test_composed_markers_nested_darken_init(self):
  def script(name):
   p=ROOT/'.circleci/scripts'/(name+'.py');spec=importlib.util.spec_from_file_location(name,p);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v);return v
  b=script('apply-sandium-blur-transition');f=script('apply-sandium-page-transition-full')
  # Actual production marker blocks: DARKEN_INIT is nested inside BLUR_INIT.
  s='\n'.join([b.JAVA_PREF_BLOCK,b.JAVA_HELPER_BLOCK,b.JAVA_CHANGE_BLOCK,b.JAVA_INIT_BLOCK])
  s=s.replace(b.JAVA_INIT_END,f.JAVA_DARKEN_INIT_BLOCK+b.JAVA_INIT_END)
  s+=f.JAVA_DARKEN_CHANGE_BLOCK
  out=m.settings(s)
  self.assertEqual(m.settings(out),out)
  for name in ('BLUR_INIT','BLUR_CHANGE','DARKEN_CHANGE'):
   self.assertIn('        // SANDIUM_PAGE_TRANSITION_'+name+'_END',out)
  self.assertIn('ChromeSwitchPreference pageTransitionBlur',out)
  self.assertIn('ChromeSwitchPreference pageTransitionDarken',out)
  self.assertNotIn('newValue instanceof String',out)
  self.assertNotIn('setEntries(',out)
  self.assertIn('getBoolean("sandium_page_transition_blur_enabled", true)',out)
  self.assertIn('.putBoolean("sandium_page_transition_blur_enabled", (Boolean) newValue).commit()',out)
 def test_transaction_exact_rollback(self):
  from unittest.mock import patch
  transaction=load('apply')
  with tempfile.TemporaryDirectory() as d:
   r=Path(d)
   for path in [m.CC,m.H,m.FC,m.FH]:
    p=r/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(m.fixture(path))
   before={p:p.read_bytes() for p in r.rglob('*') if p.is_file()}
   with patch.object(transaction,'proposed',side_effect=m.native_plan):
    transaction.execute(r,True);transaction.execute(r,True,verify_only=True)
    transaction.execute(r,False)
   for p,data in before.items():self.assertEqual(p.read_bytes(),data)
