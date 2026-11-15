#!/usr/bin/env python3
import importlib.util
from pathlib import Path
import tempfile, unittest, xml.etree.ElementTree as ET
s=importlib.util.spec_from_file_location('toggles',Path(__file__).with_name('apply-sandium-oppo-toggles.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
FIX=Path(__file__).parents[1]/'tests/fixtures/oppo-toggles'
class Tests(unittest.TestCase):
 def test_pinned_style_idempotence(self):
  old=(FIX/'styles.xml').read_text();new=m.style(old)
  self.assertEqual(new,m.style(new));self.assertIn('switch_pre_scale_min_height',new)
  self.assertIn('material_switch_scale_fraction',new);self.assertIn('thumbIcon',new)
  with self.assertRaises(ValueError):m.style('<resources/>')
 def test_selector_states(self):
  for thumb in [True,False]:
   root=ET.fromstring(m.selector(thumb));a='{http://schemas.android.com/apk/res/android}'
   self.assertEqual(len(root),4);self.assertEqual(root[0].get(a+'state_enabled'),'false')
   self.assertEqual(root[0].get(a+'state_checked'),'true');self.assertEqual(root[1].get(a+'state_enabled'),'false')
   self.assertEqual(root[2].get(a+'state_checked'),'true')
   self.assertEqual(root[2].get(a+'color'),'@android:color/white' if thumb else '#198CFF')
 def test_shields_preserves_geometry_policy(self):
  tag='<com.google.android.material.materialswitch.MaterialSwitch android:minWidth="48dp" android:checked="true" />'
  source='<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android">'+tag*3+'</LinearLayout>'
  new=m.shields(source);self.assertEqual(new,m.shields(new));self.assertEqual(new.count('android:minWidth="48dp"'),3)
  self.assertEqual(new.count('android:checked="true"'),3)
  with self.assertRaises(ValueError):m.shields('<LinearLayout/>')
 def test_full_apply_idempotence(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);brave=root/'brave';(root/m.STYLE).parent.mkdir(parents=True)
   (root/m.STYLE).write_text((FIX/'styles.xml').read_text());(root/m.BUILD).write_text((FIX/'BUILD.gn').read_text())
   (brave/m.SHIELDS).parent.mkdir(parents=True);(brave/m.SHIELDS).write_text('<LinearLayout>'+('<com.google.android.material.materialswitch.MaterialSwitch />'*3)+'</LinearLayout>')
   m.apply(root,brave);before={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()};m.apply(root,brave)
   self.assertEqual(before,{str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()})
 def test_actual_selector_contrast(self):
  a='{http://schemas.android.com/apk/res/android}'
  track=ET.fromstring(m.selector(False))[2].get(a+'color')
  def luminance(c):
   v=[int(c[i:i+2],16)/255 for i in (1,3,5)]
   v=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in v]
   return sum(x*w for x,w in zip(v,(.2126,.7152,.0722)))
  self.assertGreaterEqual(1.05/(luminance(track)+.05),3)
  self.assertNotIn('?attr/',m.selector(False))
 def test_welcome(self):
  root=Path(__file__).resolve().parents[2]
  s=(root/'android/java/org/chromium/chrome/browser/firstrun/SandiumWelcomeSetupView.java').read_text()
  thumb=s[s.index('toggle.setThumbTintList'):s.index('toggle.setTrackTintList')]
  self.assertIn('Color.WHITE',thumb);self.assertNotIn('                    PRIMARY,',thumb)
  self.assertIn('Color.rgb(25, 140, 255)',s)
  self.assertIn('toggle.setOnCheckedChangeListener',s)
if __name__=='__main__':unittest.main()
