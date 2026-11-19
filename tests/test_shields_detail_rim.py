import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('rim',ROOT/'.circleci/scripts/sandium-shields-detail-rim.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Rim(unittest.TestCase):
 def test_detail_only_root(self):
  source='<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android" android:background="?attr/colorSurfaceContainer"><View android:background="?attr/colorSurfaceContainer" /></LinearLayout>'
  out=m.detail(source)
  self.assertEqual(out,m.detail(out));self.assertEqual(out.replace('@android:color/transparent','?attr/colorSurfaceContainer'),source)
  self.assertIn('<View android:background="?attr/colorSurfaceContainer"',out)
 def test_tooltip_rim_preserves_surface_radius_padding(self):
  source='<shape xmlns:android="http://schemas.android.com/apk/res/android"><solid android:color="@color/sandium_shields_tooltip_surface"/><corners android:radius="16dp"/></shape>'
  out=m.tooltip(source);self.assertEqual(out,m.tooltip(out));root=m.ET.fromstring(out)
  self.assertEqual(len(root),4);self.assertEqual(root.get(m.A+'paddingLeft'),'0dp')
  self.assertEqual(root[0][0].find('corners').get(m.A+'radius'),'16dp')
  self.assertEqual(len(root.findall('./item/shape/stroke')),3)
  spec=importlib.util.spec_from_file_location('theme',ROOT/'.circleci/scripts/apply-sandium-native-theme.py')
  theme=importlib.util.module_from_spec(spec);spec.loader.exec_module(theme)
  self.assertEqual(theme.tooltip_style(out,theme.TOOLTIP_BACKGROUND),out)
  self.assertEqual(out.count('@color/sandium_shields_tooltip_surface'),1)
  self.assertEqual(out.count('android:radius="16dp"'),1)
 def test_fail_closed(self):
  for fn in (m.detail,m.tooltip):
   with self.assertRaises((ValueError,AttributeError)):fn('<unknown/>')
if __name__=='__main__':unittest.main()
