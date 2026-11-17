import importlib.util,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('status',HERE/'apply.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
AUDIT=Path('/workspace/scratch/40acbbeff193/brave-core-audit')
class Status(unittest.TestCase):
 def test_actual_sources_apply_repeat_reset(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)
   for n in [m.JAVA,m.SETTINGS,m.NATIVE,m.LAYOUT,m.BUILD]:
    p=root/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((AUDIT/n).read_bytes())
   before={n:(root/n).read_bytes() for n in [m.JAVA,m.SETTINGS,m.NATIVE,m.LAYOUT,m.BUILD]}
   m.apply(root);first={n:(root/n).read_bytes() for n in before};m.apply(root)
   self.assertEqual(first,{n:(root/n).read_bytes() for n in before})
   self.assertIn(b'Engine: Brave fallback',first[m.JAVA])
   self.assertIn(b'Engine unavailable: restart Sandium',first[m.JAVA])
   self.assertIn(b'getSandiumBlockingEngineStatus(Profile profile)',first[m.SETTINGS])
   self.assertIn(b'sandium_engine_status',first[m.LAYOUT])
   build=first[m.BUILD].decode()
   owner=build.split('source_set("android_browser_process") {',1)[1].split('\nsource_set(',1)[0]
   self.assertIn('"//brave/browser/extensions/api:sandium_ubo_bridge"',owner)
   self.assertIn('"//brave/components/sandium_ubo_routing"',owner)
   self.assertNotIn('"//brave/browser/extensions"',owner)
   self.assertNotIn('"//brave/browser:core"',owner)
   m.reset(root);self.assertEqual(before,{n:(root/n).read_bytes() for n in before})
 def test_read_only_and_bounded_visible_refresh(self):
  text=(HERE/'native_status.cc').read_text()
  self.assertIn('MustBlockAdRequest(profile)',text)
  self.assertIn('IsNativeFallbackComplete(profile)',text)
  self.assertIn('IsRuntimeStartupAborted(profile)',text)
  self.assertNotIn('PrepareUboOwner',text)
  self.assertNotIn('SetBoolean',text)
  java=(HERE/'java_status.txt').read_text()
  self.assertIn('if (isShowing())',java)
  self.assertIn('removeCallbacks',java)
  self.assertIn('contentEquals',java)
 def test_grouped_phone_popup_composition(self):
  script=HERE.parents[2]/'.circleci/scripts/apply-sandium-shields-popup.py'
  sp=importlib.util.spec_from_file_location('popup',script);popup=importlib.util.module_from_spec(sp);sp.loader.exec_module(popup)
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)
   for n in [m.JAVA,m.SETTINGS,m.NATIVE,m.LAYOUT,m.BUILD]:
    p=root/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((AUDIT/n).read_bytes())
   (root/m.JAVA).write_text(popup.java((root/m.JAVA).read_text()))
   (root/m.LAYOUT).write_text(popup.layout((root/m.LAYOUT).read_text()))
   m.apply(root)
   self.assertIn('updateSandiumBlockedCount',(root/m.JAVA).read_text())
   self.assertIn('sandium_engine_status',(root/m.LAYOUT).read_text())
if __name__=='__main__':unittest.main()
