import importlib.util
from pathlib import Path
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
def load(name):
 spec=importlib.util.spec_from_file_location(name, ROOT/'experiments/single-handoff'/f'{name}.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
m=load('native_blur');web=load('web')
class Blur156(unittest.TestCase):
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

class Real156Settings(unittest.TestCase):
 def test_pinned_settings_and_journal_replay(self):
  from unittest.mock import patch
  def script(name):
   p=ROOT/'.circleci/scripts'/(name+'.py');spec=importlib.util.spec_from_file_location(name,p);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v);return v
  b=script('apply-sandium-blur-transition');f=script('apply-sandium-page-transition-full')
  raw=(m.FIX/'AppearancePreferences.java').read_bytes()
  import hashlib
  self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),'3081a2777a6dd226417cd0284035f2117b8de973')
  src=raw.decode()
  before=f.transform_appearance_java(b.transform_appearance_java(src))
  # Legacy base/full reorders independent handlers once on replay; settle its
  # existing canonical postimage before checking outer transaction exactness.
  before=f.transform_appearance_java(b.transform_appearance_java(before))
  transaction=load('apply')
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);p=r/m.SETTINGS;p.parent.mkdir(parents=True);p.write_text(before)
   planner=lambda root:{root/m.SETTINGS:m.settings((root/m.SETTINGS).read_text())}
   with patch.object(transaction,'proposed',side_effect=planner):
    transaction.execute(r,True);first=p.read_text()
    transaction.execute(r,True,verify_only=True)
    transaction.execute(r,False)
    self.assertEqual(p.read_text(),before)
    replay=f.transform_appearance_java(b.transform_appearance_java(p.read_text()))
    self.assertEqual(replay,before);p.write_text(replay)
    transaction.execute(r,True);self.assertEqual(p.read_text(),first)

class NativeBaselineComposition(unittest.TestCase):
 def test_real_frozen156_reversal_then_blur(self):
  import gzip,json
  p=ROOT/'experiments/native-navigation/apply.py';spec=importlib.util.spec_from_file_location('native156',p);n=importlib.util.module_from_spec(spec);spec.loader.exec_module(n)
  data=json.loads(gzip.decompress((ROOT/'tests/fixtures/native-navigation.json.gz').read_bytes()))
  with tempfile.TemporaryDirectory() as d:
   r=Path(d)
   for path,text in data['frozen'].items():
    f=r/path;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(text)
   for path,text in n.transform(r).items():path.write_text(text)
   result=m.native_plan(r)
   self.assertEqual(result[r/m.CC],m.dim_cc(m.fixture(m.CC)))
   self.assertEqual(result[r/m.H],m.dim_h(m.fixture(m.H)))
 def test_prepare_unwinds_journals_before_source_preparation(self):
  s=(ROOT/'.circleci/scripts/prepare-brave-source.sh').read_text()
  self.assertLess(s.index('apply-sandium-native-navigation.py'),s.index('BRAVE_SOURCE_REUSE'))
  c=(ROOT/'experiments/single-handoff/composition.py').read_text()
  self.assertLess(c.index('handoff.execute(root, False)'),c.index('native.execute(root, native_enabled)'))

class DiagnosticComposition(unittest.TestCase):
 def test_exact_reviewed_probes_preserved_and_unknown_rejected(self):
  p=ROOT/'experiments/native-navigation/diagnostics.py';spec=importlib.util.spec_from_file_location('native_probe_test',p);probes=importlib.util.module_from_spec(spec);spec.loader.exec_module(probes)
  with tempfile.TemporaryDirectory() as d:
   r=Path(d)
   for path in (m.CC,m.H,m.FC,m.FH):
    target=r/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(m.fixture(path))
   cc=r/m.CC;cc.write_text(probes.apply(m.CC,m.fixture(m.CC)))
   expected=probes.apply(m.CC,m.dim_cc(m.fixture(m.CC)))
   result=m.native_plan(r)
   self.assertEqual(result[cc],expected)
   self.assertIn('IsSandiumNavigationDiagnosticsEnabled',expected)
   self.assertEqual(expected.count('SANDIUM_TRANSITION_RING_V1'),cc.read_text().count('SANDIUM_TRANSITION_RING_V1'))
   cc.write_text(expected);self.assertEqual(m.native_plan(r)[cc],expected)
   cc.write_text(expected.replace('depth < 16','depth < 17'))
   with self.assertRaises(ValueError):m.native_plan(r)

class OwnedBlurResources(unittest.TestCase):
 def test_nested_darken_xml_remains_bound_to_all_three_lint_resources(self):
  import xml.etree.ElementTree as ET
  def script(name):
   p=ROOT/'.circleci/scripts'/(name+'.py');spec=importlib.util.spec_from_file_location(name,p);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v);return v
  b=script('apply-sandium-blur-transition');f=script('apply-sandium-page-transition-full')
  before=f.transform_appearance_xml(b.XML_BLOCK)
  after=m.xml(before)
  self.assertIn(f.XML_DARKEN_BLOCK,after)
  android='{http://schemas.android.com/apk/res/android}'
  root=ET.fromstring('<PreferenceScreen xmlns:android="http://schemas.android.com/apk/res/android">'+after+'</PreferenceScreen>')
  self.assertEqual([n.attrib[android+'key'] for n in root],
                   ['sandium_page_transition_blur_enabled','sandium_page_transition_darken'])
  self.assertEqual(root[1].attrib[android+'icon'],'@drawable/ic_sandium_page_transition_darken')
  self.assertEqual(root[1].attrib[android+'title'],'@string/sandium_page_transition_darken_title')
  self.assertEqual(root[1].attrib[android+'summary'],'@string/sandium_page_transition_darken_summary')
  with self.assertRaisesRegex(ValueError,'Darken XML anchor drift'):
   m.xml(before.replace(f.XML_DARKEN_BLOCK,''))
 def test_remove_only_owned_levels_keep_consumed_summary(self):
  p=ROOT/'.circleci/scripts/apply-sandium-blur-transition.py';spec=importlib.util.spec_from_file_location('baseblurresources',p);b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
  out=m.strings(b.GRD_BLOCK+'\n<!-- unrelated -->')
  for name in ('DEFAULT','LOW','MEDIUM','HIGH'):
   self.assertNotIn('IDS_SANDIUM_PAGE_TRANSITION_BLUR_'+name,out)
  for name in ('TITLE','SUMMARY'):self.assertIn('IDS_SANDIUM_PAGE_TRANSITION_BLUR_'+name,out)
  self.assertTrue(out.endswith('<!-- unrelated -->'))
  self.assertIn('Chromium native transition. Restart to apply',out)
  with self.assertRaises(ValueError):m.strings(b.GRD_BLOCK.replace('Low page transition','unknown page transition'))

class Actual156Grd(unittest.TestCase):
 def test_pinned_actual_grd_only_owned_changes(self):
  import gzip,hashlib
  raw=gzip.decompress((m.FIX/'android_brave_strings.grd.gz').read_bytes())
  self.assertEqual(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest(),'bcd14d6b52ced4daa395a52cbe8ace36bd4d8d5d')
  def script(name):
   p=ROOT/'.circleci/scripts'/(name+'.py');spec=importlib.util.spec_from_file_location(name,p);v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v);return v
  b=script('apply-sandium-blur-transition');f=script('apply-sandium-page-transition-full')
  before=f.transform_grd(b.transform_grd(raw.decode()))
  after=m.strings(before)
  prefix,suffix=before.split(b.GRD_BEGIN)[0],before.split(b.GRD_END)[1]
  self.assertTrue(after.startswith(prefix));self.assertTrue(after.endswith(suffix))
  self.assertIn('IDS_SANDIUM_PAGE_TRANSITION_DARKEN_TITLE',after)
